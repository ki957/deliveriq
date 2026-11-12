"""Recipe approval workflow, release sign-offs and the review queue (DDR-10, DDR-30, DDR-50, DDR-54,
DDR-103, DDR-105–DDR-107).

Deny by default. The Kitchen Manager runs the workflow for their own kitchen and records four
sign-offs; a Central Administrator records the product-owner sign-off; Kitchen Staff view only.
The database enforces the same rules again: legal transitions, KM-only activation, five sign-offs,
no open review items on submit, and no SOP recipe ever ACTIVE. Out-of-scope rows read as not found.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Connection
from sqlalchemy.exc import DBAPIError

from app.core.db import get_engine
from app.core.permissions import Permission, Principal, can
from app.core.request_context import current_request_id
from app.modules.recipes import domain as d
from app.modules.recipes import repository as repo
from app.shared.actor import set_actor
from app.shared.audit import write_event

P = Permission
REVIEW_PAGE = 500


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


@dataclass(frozen=True)
class VersionDetail:
    version: repo.VersionRow
    ingredients: list[repo.IngredientLineRow]
    signoffs: list[repo.SignoffRow]
    missing_signoffs: list[d.SignoffType]
    review_items: list[repo.ReviewItemRow]


# ---------------------------------------------------------------- scope
def _kitchens_with(principal: Principal, permission: Permission) -> frozenset[uuid.UUID]:
    return frozenset(
        g.kitchen_id
        for g in principal.grants
        if g.kitchen_id is not None and can(principal, permission, kitchen_id=g.kitchen_id)
    )


def _read_scope(principal: Principal) -> tuple[frozenset[uuid.UUID] | None, bool]:
    """(kitchens, test_only). KS/KM read their kitchens; a CA reads TEST recipes to sign them."""
    kitchens = _kitchens_with(principal, P.KITCHEN_RECIPES_VIEW)
    if kitchens:
        return kitchens, False
    if can(principal, P.RECIPES_PRODUCT_OWNER_SIGNOFF):
        return None, True
    raise Forbidden


def _visible(
    conn: Connection, principal: Principal, version_id: uuid.UUID, *, lock: bool = False
) -> repo.VersionRow:
    kitchens, test_only = _read_scope(principal)
    version = repo.find_version(conn, version_id, lock=lock)
    if (
        version is None
        or (kitchens is not None and version.kitchen_id not in kitchens)
        or (test_only and not version.is_test_fixture)
    ):
        raise NotFound
    return version


def _role_for(principal: Principal, permission: Permission, kitchen_id: uuid.UUID) -> str:
    for grant in principal.grants:
        if can(Principal(principal.user_id, (grant,)), permission, kitchen_id=kitchen_id):
            return grant.role.value
    raise Forbidden


def _db_conflict(exc: DBAPIError) -> Conflict | Forbidden:
    """Map the database's own rule violations to a refusal; the message names the rule, never data."""
    sqlstate = getattr(exc.orig, "sqlstate", None)
    message = str(getattr(getattr(exc.orig, "diag", None), "message_primary", "") or "Rule violated")
    if sqlstate == "42501":  # insufficient_privilege: role may not perform this transition
        return Forbidden()
    return Conflict(message)


# ---------------------------------------------------------------- reads
def list_versions(principal: Principal, status: str | None) -> list[repo.VersionRow]:
    kitchens, test_only = _read_scope(principal)
    with get_engine().connect() as conn:
        return repo.list_versions(conn, kitchens, status, test_only)


def version_detail(principal: Principal, version_id: uuid.UUID) -> VersionDetail:
    with get_engine().connect() as conn:
        version = _visible(conn, principal, version_id)
        signed = repo.signoffs(conn, version_id)
        recorded = {d.SignoffType(s.signoff_type) for s in signed}
        return VersionDetail(
            version=version,
            ingredients=repo.ingredient_lines(conn, version_id),
            signoffs=signed,
            missing_signoffs=sorted(d.missing_signoffs(recorded)),
            review_items=repo.review_items(
                conn, frozenset({version.kitchen_id}), status=None, version_id=version_id, limit=REVIEW_PAGE
            ),
        )


def review_items(principal: Principal, status: str | None, limit: int) -> list[repo.ReviewItemRow]:
    kitchens = _kitchens_with(principal, P.KITCHEN_REVIEW_VIEW)
    if not kitchens:
        raise Forbidden
    with get_engine().connect() as conn:
        return repo.review_items(conn, kitchens, status=status, version_id=None, limit=limit)


# ---------------------------------------------------------------- workflow (KM, own kitchen)
def transition(principal: Principal, version_id: uuid.UUID, action: str, reason: str) -> repo.VersionRow:
    with get_engine().begin() as conn:
        version = _visible(conn, principal, version_id, lock=True)
        role = _role_for(
            principal,
            P.KITCHEN_RECIPES_ACTIVATE if action == "activate" else P.KITCHEN_RECIPES_WORKFLOW,
            version.kitchen_id,
        )
        current = d.RecipeStatus(version.status)
        target = d.action_target(action, current)
        if target is None:
            raise Conflict(f"Cannot {action} a recipe in status {current}")
        if action == "submit" and version.open_review_items:
            raise Conflict(f"{version.open_review_items} open review item(s) must be acknowledged first")
        if action == "activate":
            if not version.is_test_fixture:
                raise Conflict("No SOP recipe is activated in this POC (DDR-50)")
            missing = d.missing_signoffs(
                {d.SignoffType(s.signoff_type) for s in repo.signoffs(conn, version_id)}
            )
            if missing:
                raise Conflict(f"Missing sign-offs: {', '.join(sorted(missing))}")
        set_actor(
            conn, role=role, user_id=principal.user_id, reason=reason, correlation_id=current_request_id()
        )
        try:
            with conn.begin_nested():
                repo.set_status(conn, version_id, target.value)
        except DBAPIError as exc:
            raise _db_conflict(exc) from None
        write_event(
            conn,
            action=f"recipe.{action}",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_type="recipe_version",
            target_id=str(version_id),
            region_id=version.region_id,
            kitchen_id=version.kitchen_id,
            reason=reason,
            correlation_id=current_request_id(),
            before={"status": current.value},
            after={"status": target.value},
        )
        updated = repo.find_version(conn, version_id)
    if updated is None:
        raise NotFound
    return updated


def record_signoff(principal: Principal, version_id: uuid.UUID, signoff_type: str, note: str | None) -> None:
    kind = d.SignoffType(signoff_type)
    with get_engine().begin() as conn:
        version = _visible(conn, principal, version_id, lock=True)
        if kind in d.CA_SIGNOFFS:
            if not can(principal, P.RECIPES_PRODUCT_OWNER_SIGNOFF):
                raise Forbidden
            role = "CENTRAL_ADMIN"
        else:
            role = _role_for(principal, P.KITCHEN_RECIPES_SIGNOFF, version.kitchen_id)
        if not version.is_test_fixture:
            raise Conflict("Release sign-offs apply to TEST recipes only in this POC (DDR-54)")
        if d.RecipeStatus(version.status) not in d.SIGNOFF_STATUSES:
            raise Conflict(f"Sign-offs are recorded during validation, not in status {version.status}")
        if not repo.insert_signoff(conn, version_id, kind.value, principal.user_id, note):
            raise Conflict(f"{kind.value} sign-off is already recorded")
        write_event(
            conn,
            action="recipe.signoff",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_type="recipe_version",
            target_id=str(version_id),
            region_id=version.region_id,
            kitchen_id=version.kitchen_id,
            reason=note,
            correlation_id=current_request_id(),
            after={"signoff_type": kind.value},
        )


def acknowledge(principal: Principal, item_id: uuid.UUID, note: str) -> repo.ReviewItemRow:
    with get_engine().begin() as conn:
        item = repo.find_review_item(conn, item_id, lock=True)
        if item is None or item.kitchen_id not in _kitchens_with(principal, P.KITCHEN_REVIEW_VIEW):
            raise NotFound
        role = _role_for(principal, P.KITCHEN_REVIEW_ACKNOWLEDGE, item.kitchen_id)
        if item.status != "OPEN":
            raise Conflict("Review item is already acknowledged")
        repo.acknowledge_review_item(conn, item_id, principal.user_id, note)
        write_event(
            conn,
            action="recipe.review.acknowledge",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_type="recipe_review_item",
            target_id=str(item_id),
            region_id=item.region_id,
            kitchen_id=item.kitchen_id,
            reason=note,
            correlation_id=current_request_id(),
            after={"reason_code": item.reason_code, "subject": item.subject},
        )
        updated = repo.find_review_item(conn, item_id)
    if updated is None:
        raise NotFound
    return updated
