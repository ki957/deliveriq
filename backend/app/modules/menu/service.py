"""Menu publication (DDR-11, DDR-31, DDR-48, DDR-50, DDR-107) and the customer menu read.

CA publishes in any region; RM only in assigned regions; every other role is refused. Both must pass
the readiness checklist with an ACTIVE recipe version, enforced by the database trigger, which also
writes the publication audit (actor, role, region, time, item, action). Unpublished items never
reach the customer view; in production, fixture items are filtered as defence in depth.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.permissions import Permission, Principal, can
from app.core.request_context import current_request_id
from app.modules.menu import domain as d
from app.modules.menu import repository as repo
from app.shared.actor import set_actor
from app.shared.audit import write_event

P = Permission
# Actions in 5B (DDR-107). Unavailability (Task 8) and retirement come with their tasks.
ACTIONS: dict[str, tuple[d.Publication, d.Publication]] = {
    "mark_ready": (d.Publication.DRAFT, d.Publication.READY_FOR_PUBLICATION),
    "publish": (d.Publication.READY_FOR_PUBLICATION, d.Publication.PUBLISHED),
}


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def _include_fixtures() -> bool:
    # Leak control 4: production menus never show fixture rows (defence in depth).
    return get_settings().app_env != "production"


def customer_menu(
    *,
    q: str | None = None,
    category: str | None = None,
    veg: bool | None = None,
    spice: str | None = None,
    min_price_paise: int | None = None,
    max_price_paise: int | None = None,
    bestseller: bool | None = None,
) -> list[repo.MenuItemRow]:
    with get_engine().connect() as conn:
        return repo.published_filtered(
            conn,
            include_fixtures=_include_fixtures(),
            q=q,
            category=category,
            veg=veg,
            spice=spice,
            min_price_paise=min_price_paise,
            max_price_paise=max_price_paise,
            bestseller=bestseller,
        )


def menu_filters() -> dict[str, object]:
    with get_engine().connect() as conn:
        return repo.filter_options(conn, include_fixtures=_include_fixtures())


def dish(item_id: uuid.UUID) -> tuple[repo.MenuItemRow, list[str]]:
    with get_engine().connect() as conn:
        item = repo.published_item(conn, item_id, include_fixtures=_include_fixtures())
        if item is None:
            raise NotFound
        return item, repo.active_ingredient_names(conn, item.recipe_id)


def _scope(principal: Principal) -> frozenset[uuid.UUID] | None:
    """None = every region (CA); else the RM's assigned regions; Forbidden for everyone else."""
    if can(principal, P.MENU_PUBLISH):
        return None
    regions = frozenset(
        g.region_id
        for g in principal.grants
        if g.region_id is not None and can(principal, P.MENU_PUBLISH, region_id=g.region_id)
    )
    if not regions:
        raise Forbidden
    return regions


def list_items(principal: Principal) -> list[repo.MenuItemRow]:
    regions = _scope(principal)
    with get_engine().connect() as conn:
        return repo.list_items(conn, regions)


def _role_for(principal: Principal, region_id: uuid.UUID) -> str:
    for grant in principal.grants:
        if can(Principal(principal.user_id, (grant,)), P.MENU_PUBLISH, region_id=region_id):
            return grant.role.value
    raise Forbidden


def _visible(conn: Connection, principal: Principal, item_id: uuid.UUID) -> repo.MenuItemRow:
    regions = _scope(principal)
    item = repo.find_item(conn, item_id, lock=True)
    if item is None or (regions is not None and item.region_id not in regions):
        raise NotFound
    return item


def transition(principal: Principal, item_id: uuid.UUID, action: str, reason: str | None) -> repo.MenuItemRow:
    with get_engine().begin() as conn:
        item = _visible(conn, principal, item_id)
        role = _role_for(principal, item.region_id)
        source, target = ACTIONS[action]
        if item.publication_status != source:
            raise Conflict(f"Cannot {action.replace('_', ' ')} an item in status {item.publication_status}")
        set_actor(
            conn, role=role, user_id=principal.user_id, reason=reason, correlation_id=current_request_id()
        )
        try:
            with conn.begin_nested():
                repo.set_status(conn, item_id, target.value)
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) == "42501":
                raise Forbidden from None
            diag = getattr(exc.orig, "diag", None)
            raise Conflict(str(getattr(diag, "message_primary", "") or "Rule violated")) from None
        updated = repo.find_item(conn, item_id)
    if updated is None:
        raise NotFound
    return updated


# ---------------------------------------------------- dish availability (KI-24; DDR-11, DDR-111 (7))
# The kitchen requests; the RM (own region) or CA decides. Only an approval changes the customer menu.
AVAILABILITY_KINDS: dict[str, tuple[d.Publication, d.Publication]] = {
    "MAKE_UNAVAILABLE": (d.Publication.PUBLISHED, d.Publication.TEMPORARILY_UNAVAILABLE),
    "MAKE_AVAILABLE": (d.Publication.TEMPORARILY_UNAVAILABLE, d.Publication.PUBLISHED),
}
AVAILABILITY_REASON_MAX = 500
_KITCHEN_ROLES = ("KITCHEN_STAFF", "KITCHEN_MANAGER")


class Invalid(Exception):
    pass


def _reason(reason: str | None, *, required: bool) -> str | None:
    cleaned = (reason or "").strip()
    if required and not cleaned:
        raise Invalid("A reason is required")
    if len(cleaned) > AVAILABILITY_REASON_MAX:
        raise Invalid(f"The reason can be at most {AVAILABILITY_REASON_MAX} characters")
    return cleaned or None


def _role_with(
    principal: Principal, permission: Permission, *, kitchen_id: uuid.UUID, region_id: uuid.UUID
) -> str:
    for grant in principal.grants:
        if can(
            Principal(principal.user_id, (grant,)), permission, kitchen_id=kitchen_id, region_id=region_id
        ):
            return grant.role.value
    raise Forbidden


def kitchen_dishes(principal: Principal, kitchen_id: uuid.UUID) -> list[repo.MenuItemRow]:
    if not can(principal, P.KITCHEN_UNAVAILABILITY_REQUEST, kitchen_id=kitchen_id):
        raise NotFound
    with get_engine().connect() as conn:
        return repo.kitchen_dishes(conn, kitchen_id)


def request_availability(
    principal: Principal, menu_item_id: uuid.UUID, kind: str, reason: str
) -> repo.AvailabilityRequestRow:
    text_reason = _reason(reason, required=True)
    source, _target = AVAILABILITY_KINDS[kind]
    with get_engine().begin() as conn:
        item = repo.find_item(conn, menu_item_id, lock=True)
        if item is None or not can(principal, P.KITCHEN_UNAVAILABILITY_REQUEST, kitchen_id=item.kitchen_id):
            raise NotFound
        role = _role_with(
            principal, P.KITCHEN_UNAVAILABILITY_REQUEST, kitchen_id=item.kitchen_id, region_id=item.region_id
        )
        if item.publication_status != source:
            raise Conflict(f"The dish is {item.publication_status}; this request does not apply")
        try:
            with conn.begin_nested():
                request_id = repo.insert_request(
                    conn, item=item, kind=kind, reason=text_reason or "", requested_by=principal.user_id,
                    requested_role=role,
                )  # fmt: skip
        except IntegrityError as exc:
            if "dish_availability_one_pending_uq" not in str(exc.orig):
                raise
            raise Conflict("A request for this dish is already waiting for a decision") from None
        write_event(
            conn,
            action="menu.availability.requested",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_type="menu_item",
            target_id=str(item.id),
            region_id=item.region_id,
            kitchen_id=item.kitchen_id,
            reason=text_reason,
            correlation_id=current_request_id(),
            after={"request_id": str(request_id), "kind": kind},
        )
        found = repo.find_request(conn, request_id)
    if found is None:  # pragma: no cover - inserted above
        raise NotFound
    return found


def availability_requests(principal: Principal, *, pending_only: bool) -> list[repo.AvailabilityRequestRow]:
    """Kitchen roles see their kitchen's requests; RM their regions; CA every region."""
    kitchens = frozenset(
        g.kitchen_id
        for g in principal.grants
        if g.role.value in _KITCHEN_ROLES and g.kitchen_id
        and can(principal, P.KITCHEN_UNAVAILABILITY_REQUEST, kitchen_id=g.kitchen_id)
    )  # fmt: skip
    everywhere = can(principal, P.MGMT_UNAVAILABILITY_APPROVE)  # CA: no scope needed
    regions = frozenset(
        g.region_id
        for g in principal.grants
        if g.region_id is not None and can(principal, P.MGMT_UNAVAILABILITY_APPROVE, region_id=g.region_id)
    )
    if not (everywhere or kitchens or regions):
        raise Forbidden
    with get_engine().connect() as conn:
        if everywhere:
            return repo.list_requests(conn, kitchens=None, regions=None, pending_only=pending_only)
        return repo.list_requests(conn, kitchens=kitchens, regions=regions, pending_only=pending_only)


def decide_availability(
    principal: Principal, request_id: uuid.UUID, *, approve: bool, reason: str | None
) -> repo.AvailabilityRequestRow:
    """Approve (the menu changes) or reject with a reason. RM in the dish's region, or CA."""
    text_reason = _reason(reason, required=not approve)
    with get_engine().begin() as conn:
        request = repo.find_request(conn, request_id, lock=True)
        if request is None or not can(principal, P.MGMT_UNAVAILABILITY_APPROVE, region_id=request.region_id):
            if request is not None and can(
                principal, P.KITCHEN_UNAVAILABILITY_REQUEST, kitchen_id=request.kitchen_id
            ):
                raise Forbidden  # the kitchen can see its request but never decide it (KI-24)
            raise NotFound
        role = _role_with(
            principal,
            P.MGMT_UNAVAILABILITY_APPROVE,
            kitchen_id=request.kitchen_id,
            region_id=request.region_id,
        )
        if request.status != "PENDING":
            raise Conflict(f"This request is already {request.status.lower()}")
        source, target = AVAILABILITY_KINDS[request.kind]
        if approve:
            item = repo.find_item(conn, request.menu_item_id, lock=True)
            if item is None or item.publication_status != source:
                raise Conflict(
                    "The dish changed since the request; reject it and ask the kitchen to request again"
                )
            # The menu transition needs a reason (DDR-11): the kitchen's request reason.
            set_actor(
                conn, role=role, user_id=principal.user_id, reason=request.reason,
                correlation_id=current_request_id(),
            )  # fmt: skip
            try:
                with conn.begin_nested():
                    repo.set_status(conn, item.id, target.value)
            except DBAPIError as exc:
                diag = getattr(exc.orig, "diag", None)
                raise Conflict(str(getattr(diag, "message_primary", "") or "Rule violated")) from None
        repo.decide_request(
            conn, request_id, status="APPROVED" if approve else "REJECTED", by=principal.user_id, role=role,
            reason=text_reason,
        )  # fmt: skip
        write_event(
            conn,
            action="menu.availability.decided",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_type="menu_item",
            target_id=str(request.menu_item_id),
            region_id=request.region_id,
            kitchen_id=request.kitchen_id,
            reason=text_reason,
            correlation_id=current_request_id(),
            after={"request_id": str(request_id), "kind": request.kind, "approved": approve},
        )
        decided = repo.find_request(conn, request_id)
    if decided is None:  # pragma: no cover - updated above
        raise NotFound
    return decided
