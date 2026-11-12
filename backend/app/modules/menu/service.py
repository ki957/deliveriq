"""Menu publication (DDR-11, DDR-31, DDR-48, DDR-50, DDR-107) and the customer menu read.

CA publishes in any region; RM only in assigned regions; every other role is refused. Both must pass
the readiness checklist with an ACTIVE recipe version, enforced by the database trigger, which also
writes the publication audit (actor, role, region, time, item, action). Unpublished items never
reach the customer view; in production, fixture items are filtered as defence in depth.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Connection
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.permissions import Permission, Principal, can
from app.core.request_context import current_request_id
from app.modules.menu import domain as d
from app.modules.menu import repository as repo
from app.shared.actor import set_actor

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


def customer_menu() -> list[repo.MenuItemRow]:
    with get_engine().connect() as conn:
        return repo.published(conn, include_fixtures=get_settings().app_env != "production")


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
