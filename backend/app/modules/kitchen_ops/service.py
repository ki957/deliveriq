"""Kitchen mode, capacity and intake (#4 §3; KI-12–KI-15; DDR-42, DDR-111 (1)–(3), (14)).

- `intake` runs in the caller's transaction: checkout and kitchen acceptance both use it.
- `lock` serialises acceptance per kitchen, so capacity holds under concurrent acceptance.
- Mode and capacity changes need a reason and are audited (no approved event type, DDR-109 (6)).

Deny by default: kitchen roles act on their own kitchen; RM within assigned regions; CA everywhere.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Connection

from app.core.db import get_engine
from app.core.permissions import Grant, Permission, Principal, Role, can
from app.core.request_context import current_request_id
from app.modules.kitchen_ops import domain as d
from app.modules.kitchen_ops import repository as repo
from app.shared.audit import write_event

P = Permission
KitchenRow = repo.KitchenRow
SettingRow = repo.SettingRow
_KITCHEN_ROLES = (Role.KITCHEN_STAFF, Role.KITCHEN_MANAGER)


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Invalid(Exception):
    """The request breaks a settings rule (422)."""


class MissingSetting(Exception):
    """A capacity value is not configured for this kitchen; never replaced by a guessed default."""


# ---------------------------------------------------------------- scope helpers (used by other modules)
def resolve(conn: Connection, principal: Principal, kitchen_id: uuid.UUID | None) -> KitchenRow:
    """The kitchen named, or the caller's own kitchen when they hold exactly one kitchen grant."""
    if kitchen_id is None:
        own = {g.kitchen_id for g in principal.grants if g.role in _KITCHEN_ROLES and g.kitchen_id}
        if len(own) != 1:
            raise NotFound
        kitchen_id = next(iter(own))
    kitchen = repo.find(conn, kitchen_id)
    if kitchen is None:
        raise NotFound
    return kitchen


def acting_role(
    principal: Principal, permission: Permission, *, kitchen_id: uuid.UUID, region_id: uuid.UUID
) -> str:
    """The role of the first grant that allows the action here (recorded as the actor); else Forbidden."""
    for grant in principal.grants:
        alone = Principal(principal.user_id, (Grant(grant.role, grant.region_id, grant.kitchen_id),))
        if can(alone, permission, kitchen_id=kitchen_id, region_id=region_id):
            return grant.role.value
    raise Forbidden


def allowed(principal: Principal, permission: Permission, kitchen: KitchenRow) -> bool:
    return can(principal, permission, kitchen_id=kitchen.id, region_id=kitchen.region_id)


# ---------------------------------------------------------------- intake (checkout and acceptance)
def _capacity(conn: Connection, key: str, kitchen: KitchenRow) -> repo.SettingRow:
    row = repo.setting(conn, key, kitchen)
    if row is None:
        raise MissingSetting(key)
    return row


_MODE_KEY = {d.KitchenMode.NORMAL: repo.KEY_NORMAL, d.KitchenMode.BUSY: repo.KEY_BUSY}


def intake(conn: Connection, kitchen: KitchenRow) -> d.Intake:
    """Only the active mode's capacity is read; a Paused kitchen needs none."""
    mode = d.KitchenMode(kitchen.mode)
    key = _MODE_KEY.get(mode)
    capacity = int(_capacity(conn, key, kitchen).value) if key else None
    return d.intake(mode, capacity=capacity, active=repo.active_count(conn, kitchen.id))


def find(conn: Connection, kitchen_id: uuid.UUID) -> KitchenRow:
    kitchen = repo.find(conn, kitchen_id)
    if kitchen is None:
        raise NotFound
    return kitchen


def intake_for(conn: Connection, kitchen_id: uuid.UUID) -> d.Intake:
    return intake(conn, find(conn, kitchen_id))


def lock(conn: Connection, kitchen_id: uuid.UUID) -> KitchenRow:
    """Row lock on the kitchen for the rest of the caller's transaction (one acceptance at a time)."""
    kitchen = repo.find(conn, kitchen_id, lock=True)
    if kitchen is None:
        raise NotFound
    return kitchen


def acceptance_timeout_minutes(conn: Connection, kitchen: KitchenRow) -> int | None:
    row = repo.setting(conn, repo.KEY_TIMEOUT, kitchen)
    return int(row.value) if row else None


# ---------------------------------------------------------------- settings (KI-12, KI-15)
@dataclass(frozen=True)
class Settings:
    kitchen: KitchenRow
    normal_capacity: repo.SettingRow
    busy_capacity: repo.SettingRow
    acceptance_timeout_minutes: repo.SettingRow | None
    intake: d.Intake
    can_change: bool


def _settings(conn: Connection, principal: Principal, kitchen: KitchenRow) -> Settings:
    return Settings(
        kitchen=kitchen,
        normal_capacity=_capacity(conn, repo.KEY_NORMAL, kitchen),
        busy_capacity=_capacity(conn, repo.KEY_BUSY, kitchen),
        acceptance_timeout_minutes=repo.setting(conn, repo.KEY_TIMEOUT, kitchen),
        intake=intake(conn, kitchen),
        can_change=allowed(principal, P.KITCHEN_MODE_CHANGE, kitchen),
    )


def get_settings(principal: Principal, kitchen_id: uuid.UUID | None) -> Settings:
    with get_engine().connect() as conn:
        kitchen = resolve(conn, principal, kitchen_id)
        if not (
            allowed(principal, P.KITCHEN_ORDERS_VIEW, kitchen)
            or allowed(principal, P.MGMT_OPERATIONS_VIEW, kitchen)
        ):
            raise NotFound  # another kitchen reads as not found
        return _settings(conn, principal, kitchen)


def update_settings(
    principal: Principal,
    kitchen_id: uuid.UUID | None,
    *,
    mode: d.KitchenMode,
    normal_capacity: int,
    busy_capacity: int,
    reason: str,
) -> Settings:
    with get_engine().begin() as conn:
        kitchen = resolve(conn, principal, kitchen_id)
        if not allowed(principal, P.KITCHEN_MODE_CHANGE, kitchen):
            if allowed(principal, P.KITCHEN_ORDERS_VIEW, kitchen):
                raise Forbidden  # own kitchen, but not a manager
            raise NotFound
        reason = reason.strip()
        if not reason:
            raise Invalid("A reason is required to change the kitchen mode or capacity")
        if len(reason) > d.REASON_MAX:
            raise Invalid(f"The reason can be at most {d.REASON_MAX} characters")
        error = d.capacity_error(normal_capacity, busy_capacity)
        if error:
            raise Invalid(error)
        role = acting_role(
            principal, P.KITCHEN_MODE_CHANGE, kitchen_id=kitchen.id, region_id=kitchen.region_id
        )
        kitchen = lock(conn, kitchen.id)
        before = _settings(conn, principal, kitchen)
        repo.set_mode(conn, kitchen.id, mode.value)
        # Only a changed value becomes a configured value; untouched test defaults keep their label.
        if int(before.normal_capacity.value) != normal_capacity:
            repo.set_kitchen_value(conn, repo.KEY_NORMAL, kitchen.id, normal_capacity, "orders")
        if int(before.busy_capacity.value) != busy_capacity:
            repo.set_kitchen_value(conn, repo.KEY_BUSY, kitchen.id, busy_capacity, "orders")
        write_event(
            conn,
            action="kitchen.settings.changed",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_type="kitchen",
            target_id=str(kitchen.id),
            region_id=kitchen.region_id,
            kitchen_id=kitchen.id,
            reason=reason,
            correlation_id=current_request_id(),
            before={
                "mode": before.kitchen.mode,
                "normal_capacity": int(before.normal_capacity.value),
                "busy_capacity": int(before.busy_capacity.value),
            },
            after={"mode": mode.value, "normal_capacity": normal_capacity, "busy_capacity": busy_capacity},
        )
        updated = repo.find(conn, kitchen.id)
        if updated is None:  # pragma: no cover - locked above
            raise NotFound
        return _settings(conn, principal, updated)
