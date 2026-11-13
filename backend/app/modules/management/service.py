"""Unified management: scoped read views, staff access and exports (#10; MG-01, MG-03, MG-08; DDR-114).

Deny by default. Every view is filtered to the caller's scope: a Regional Manager sees assigned regions
only, a Central Administrator everything; anything outside scope reads as not found. Actions that change
operations reuse the owning modules' services (kitchen settings, delivery, orders, menu); this module
adds staff access (users, role assignments, sessions) and read models.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.permissions import Grant, Permission, Principal, Role, can
from app.core.request_context import current_request_id
from app.modules.delivery import service as delivery
from app.modules.identity import service as identity
from app.modules.kitchen_ops import service as kitchens
from app.modules.management import repository as repo
from app.modules.orders import domain as order_domain
from app.shared.audit import write_event

P = Permission
OrderListRow = repo.OrderListRow
StaffGrantRow = repo.StaffGrantRow
PAGE_SIZE = 50
MAX_RANGE_DAYS = 31  # DDR-114 (7): bounded date ranges (#10 §14); not a business value
EXPORT_MAX = 5_000  # DDR-114 (8)
REASON_MAX = 500
KITCHEN_ROLES = (Role.KITCHEN_STAFF, Role.KITCHEN_MANAGER)
STAFF_ROLES_RM = (Role.KITCHEN_STAFF, Role.KITCHEN_MANAGER, Role.DELIVERY_AGENT)


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class Invalid(Exception):
    pass


# ---------------------------------------------------------------- scope
def scope(principal: Principal, permission: Permission) -> repo.Regions:
    """None = every region (CA); else the regions the permission is granted in; Forbidden if none."""
    if can(principal, permission):  # only a global grant covers "no scope"
        return None
    regions = sorted(
        {
            g.region_id
            for g in principal.grants
            if g.region_id and can(principal, permission, region_id=g.region_id)
        }
    )
    if not regions:
        raise Forbidden
    return regions


def _role(principal: Principal, permission: Permission, region_id: uuid.UUID | None = None) -> str:
    for g in principal.grants:
        alone = Principal(principal.user_id, (Grant(g.role, g.region_id, g.kitchen_id),))
        if can(alone, permission, region_id=region_id) if region_id else can(alone, permission):
            return g.role.value
    raise Forbidden


def _reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if not text or len(text) > REASON_MAX:
        raise Invalid(f"A reason of 1 to {REASON_MAX} characters is required")
    return text


def date_range(date_from: datetime | None, date_to: datetime | None) -> tuple[datetime, datetime]:
    end = date_to or datetime.now(UTC) + timedelta(minutes=1)
    start = date_from or end - timedelta(days=7)
    if start >= end:
        raise Invalid("The start must be before the end")
    if end - start > timedelta(days=MAX_RANGE_DAYS):
        raise Invalid(f"Choose a range of at most {MAX_RANGE_DAYS} days")
    return start, end


# ---------------------------------------------------------------- overview (#10 §13; DDR-114 (10))
@dataclass(frozen=True)
class KitchenStatus:
    kitchen: repo.KitchenRow
    intake: Any


@dataclass(frozen=True)
class Overview:
    orders_by_status: dict[str, int]
    overdue_incoming: int
    pending: dict[str, int]
    kitchens: list[KitchenStatus]


def _kitchen_statuses(conn: Any, regions: repo.Regions) -> list[KitchenStatus]:
    out = []
    for k in repo.kitchens(conn, regions):
        try:
            intake = kitchens.intake_for(conn, k.id)
        except kitchens.MissingSetting:
            intake = None  # capacity not configured for this kitchen: shown as such, never guessed
        out.append(KitchenStatus(k, intake))
    return out


def overview(principal: Principal) -> Overview:
    regions = scope(principal, P.MGMT_OPERATIONS_VIEW)
    with get_engine().connect() as conn:
        return Overview(
            orders_by_status=repo.order_counts(conn, regions),
            overdue_incoming=repo.overdue_incoming(conn, regions),
            pending=repo.pending_counts(conn, regions),
            kitchens=_kitchen_statuses(conn, regions),
        )


def kitchen_list(principal: Principal) -> list[KitchenStatus]:
    regions = scope(principal, P.MGMT_OPERATIONS_VIEW)
    with get_engine().connect() as conn:
        return _kitchen_statuses(conn, regions)


def region_list(principal: Principal) -> list[tuple[uuid.UUID, str, str]]:
    regions = scope(principal, P.MGMT_OPERATIONS_VIEW)
    with get_engine().connect() as conn:
        return repo.regions(conn, regions)


# ---------------------------------------------------------------- orders (#10 §7; DDR-114 (8), (9))
def _order_filter(principal: Principal, **f: Any) -> repo.OrderFilter:
    regions = scope(principal, P.MGMT_OPERATIONS_VIEW)
    start, end = date_range(f.pop("date_from", None), f.pop("date_to", None))
    return repo.OrderFilter(regions=regions, date_from=start, date_to=end, **f)


def order_list(principal: Principal, *, page: int, **filters: Any) -> tuple[list[repo.OrderListRow], int]:
    f = _order_filter(principal, **filters)
    with get_engine().connect() as conn:
        return repo.orders(conn, f, limit=PAGE_SIZE, offset=max(page - 1, 0) * PAGE_SIZE)


@dataclass(frozen=True)
class OrderDetail:
    head: repo.OrderListRow
    items: list[tuple[str, int]]
    timeline: list[repo.TimelineRow]


def order_detail(principal: Principal, order_id: uuid.UUID) -> OrderDetail:
    regions = scope(principal, P.MGMT_OPERATIONS_VIEW)
    with get_engine().connect() as conn:
        head = repo.order_head(conn, order_id, regions)
        if head is None:
            raise NotFound
        return OrderDetail(head, repo.order_items(conn, order_id), repo.timeline(conn, order_id))


def management_label(status: str) -> str:
    return order_domain.display(order_domain.Fulfilment(status), False).management


def _csv(header: list[str], rows: list[list[Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    for r in rows:
        # Neutralise spreadsheet formulas in exported text (CSV injection).
        writer.writerow([f"'{v}" if isinstance(v, str) and v[:1] in "=+-@" else v for v in r])
    return out.getvalue()


def _audit_export(
    principal: Principal, permission: Permission, what: str, count: int, filters: dict[str, Any]
) -> None:
    with get_engine().begin() as conn:
        write_event(
            conn,
            action=f"management.export.{what}",
            actor_user_id=principal.user_id,
            actor_role=_role(principal, permission) if can(principal, permission) else _first_role(principal),
            target_type="export",
            target_id=what,
            correlation_id=current_request_id(),
            after={"rows": count, **{k: str(v) for k, v in filters.items() if v is not None}},
        )


def _first_role(principal: Principal) -> str:
    return principal.grants[0].role.value if principal.grants else "UNKNOWN"


def orders_csv(principal: Principal, **filters: Any) -> str:
    f = _order_filter(principal, **filters)
    with get_engine().connect() as conn:
        rows, total = repo.orders(conn, f, limit=EXPORT_MAX, offset=0)
    if total > EXPORT_MAX:
        raise Invalid(f"The export is limited to {EXPORT_MAX} rows; narrow the filters")
    _audit_export(principal, P.MGMT_OPERATIONS_VIEW, "orders", len(rows), filters)
    return _csv(
        [
            "order_id",
            "placed_at",
            "status",
            "test",
            "kitchen",
            "payable_paise",
            "payment_method",
            "payment_status",
            "agent",
            "assignment_status",
            "exception_open",
        ],
        [
            [
                r.id,
                r.placed_at.isoformat(),
                management_label(r.fulfilment_status),
                r.is_test_fixture,
                r.kitchen_name,
                r.payable_paise,
                r.payment_method,
                r.payment_status,
                r.agent_name,
                r.assignment_status,
                r.delivery_exception_open,
            ]
            for r in rows
        ],
    )


# ---------------------------------------------------------------- delivery, refunds, inventory
def delivery_board(principal: Principal) -> list[repo.DeliveryRow]:
    regions = scope(principal, P.MGMT_OPERATIONS_VIEW)
    with get_engine().connect() as conn:
        return repo.deliveries(conn, regions)


def refund_list(principal: Principal) -> list[repo.RefundRow]:
    regions = scope(principal, P.MGMT_OPERATIONS_VIEW)
    with get_engine().connect() as conn:
        return repo.refunds(conn, regions, limit=200)


@dataclass(frozen=True)
class Inventory:
    kitchen_id: uuid.UUID
    stock: list[repo.StockRow]
    movements: list[repo.MovementRow]


def inventory(principal: Principal, kitchen_id: uuid.UUID) -> Inventory:
    """DDR-114 (12): read-only stock, reservations, thresholds and the ledger, within scope."""
    regions = scope(principal, P.MGMT_INVENTORY_VIEW)
    with get_engine().connect() as conn:
        region = repo.kitchen_region(conn, kitchen_id)
        if region is None or (regions is not None and region not in regions):
            raise NotFound
        return Inventory(kitchen_id, repo.stock(conn, kitchen_id), repo.movements(conn, kitchen_id, 100))


# ---------------------------------------------------------------- audit (#10 §12; DDR-114 (7), (8))
def _audit_filter(principal: Principal, **f: Any) -> repo.AuditFilter:
    if can(principal, P.MGMT_AUDIT_GLOBAL):
        regions, unscoped = None, True
    else:
        regions, unscoped = scope(principal, P.MGMT_AUDIT_REGIONAL), False
    start, end = date_range(f.pop("date_from", None), f.pop("date_to", None))
    return repo.AuditFilter(regions=regions, include_unscoped=unscoped, date_from=start, date_to=end, **f)


def audit_list(principal: Principal, *, page: int, **filters: Any) -> tuple[list[repo.AuditRow], int]:
    f = _audit_filter(principal, **filters)
    with get_engine().connect() as conn:
        return repo.audit(conn, f, limit=PAGE_SIZE, offset=max(page - 1, 0) * PAGE_SIZE)


def audit_csv(principal: Principal, **filters: Any) -> str:
    f = _audit_filter(principal, **filters)
    with get_engine().connect() as conn:
        rows, total = repo.audit(conn, f, limit=EXPORT_MAX, offset=0)
    if total > EXPORT_MAX:
        raise Invalid(f"The export is limited to {EXPORT_MAX} rows; narrow the filters")
    permission = P.MGMT_AUDIT_GLOBAL if can(principal, P.MGMT_AUDIT_GLOBAL) else P.MGMT_AUDIT_REGIONAL
    _audit_export(principal, permission, "audit", len(rows), filters)
    return _csv(
        [
            "occurred_at",
            "actor_role",
            "actor",
            "action",
            "target_type",
            "target_id",
            "region_id",
            "outcome",
            "reason",
            "correlation_id",
        ],
        [
            [
                r.occurred_at.isoformat(),
                r.actor_role,
                r.actor_name,
                r.action,
                r.target_type,
                r.target_id,
                r.region_id,
                r.outcome,
                r.reason,
                r.correlation_id,
            ]
            for r in rows
        ],
    )


# ---------------------------------------------------------------- staff access (#10 §4; DDR-114 (3)–(5))
def _may_manage(principal: Principal, role: str, region_id: uuid.UUID | None) -> bool:
    if role == Role.REGIONAL_MANAGER:
        return can(principal, P.MGMT_RM_MANAGE)  # CA only
    if role in STAFF_ROLES_RM and region_id is not None:
        return can(principal, P.MGMT_STAFF_MANAGE, region_id=region_id)
    return False  # CA and customer roles are never granted or removed here


def staff_list(principal: Principal) -> list[repo.StaffGrantRow]:
    regions = scope(principal, P.MGMT_STAFF_MANAGE)
    with get_engine().connect() as conn:
        rows = repo.staff(conn, regions)
    # An RM sees the staff they may manage; CA sees every staff grant.
    return [r for r in rows if regions is None or _may_manage(principal, r.role, r.region_id)]


def _actor_role(principal: Principal, role: str, region_id: uuid.UUID | None) -> str:
    if role == Role.REGIONAL_MANAGER:
        return _role(principal, P.MGMT_RM_MANAGE)
    return _role(principal, P.MGMT_STAFF_MANAGE, region_id)


def add_staff(
    principal: Principal,
    *,
    display_name: str,
    mobile: str,
    role: Role,
    region_id: uuid.UUID,
    kitchen_id: uuid.UUID | None,
    reason: str,
) -> repo.StaffGrantRow:
    if not _may_manage(principal, role, region_id):
        raise Forbidden
    text_reason = _reason(reason)
    name = " ".join(display_name.split())
    if not 1 <= len(name) <= 80:
        raise Invalid("Enter a name of 1 to 80 characters")
    try:
        e164 = identity.normalize(get_settings(), mobile)
    except identity.InvalidMobile:
        raise Invalid("Enter a valid Indian mobile number") from None
    if (role in KITCHEN_ROLES) != (kitchen_id is not None):
        raise Invalid("Kitchen roles need a kitchen; other roles must not have one")
    with get_engine().begin() as conn:
        if not repo.region_exists(conn, region_id):
            raise Invalid("Unknown region")
        if kitchen_id is not None and not repo.kitchen_in_region(conn, kitchen_id, region_id):
            raise Invalid("The kitchen is not in this region")
        existing = repo.user_by_mobile(conn, e164)
        if existing is not None and existing[0] == principal.user_id:
            raise Forbidden  # no self-escalation (MG-01)
        if existing is not None and existing[1] != "ACTIVE":
            raise Conflict("This account is deactivated; reactivate it first")
        user_id = existing[0] if existing else repo.create_user(conn, name, e164)
        try:
            with conn.begin_nested():
                grant_id = repo.insert_grant(
                    conn,
                    user_id,
                    role.value,
                    region_id,
                    kitchen_id if role in KITCHEN_ROLES else None,
                    principal.user_id,
                )
        except IntegrityError:
            raise Conflict("This person already has this role here") from None
        write_event(
            conn,
            action="management.staff.role_granted",
            actor_user_id=principal.user_id,
            actor_role=_actor_role(principal, role, region_id),
            target_type="user",
            target_id=str(user_id),
            region_id=region_id,
            kitchen_id=kitchen_id,
            reason=text_reason,
            correlation_id=current_request_id(),
            after={"role": role.value, "new_user": existing is None},
        )
        row = repo.grant(conn, grant_id)
    if row is None:  # pragma: no cover - inserted above
        raise NotFound
    return row


def _stop_agent_work(principal: Principal, user_id: uuid.UUID, reason: str) -> None:
    """MG-01: an accepted delivery blocks the change; an open offer is expired and re-offered."""
    try:
        delivery.force_offline(principal, user_id, reason)
    except delivery.Conflict:
        raise Conflict("The agent has an active delivery; reassign or resolve it first") from None
    except (delivery.NotFound, delivery.Forbidden):
        raise Forbidden from None


def remove_role(principal: Principal, assignment_id: uuid.UUID, reason: str) -> None:
    text_reason = _reason(reason)
    with get_engine().connect() as conn:
        g = repo.grant(conn, assignment_id)
    if g is None or not _may_manage(principal, g.role, g.region_id):
        raise NotFound
    if g.user_id == principal.user_id:
        raise Forbidden
    if g.role == Role.DELIVERY_AGENT:
        _stop_agent_work(principal, g.user_id, text_reason)
    with get_engine().begin() as conn:
        locked = repo.grant(conn, assignment_id, lock=True)
        if locked is None:
            raise NotFound
        if locked.role == Role.DELIVERY_AGENT and repo.active_delivery(conn, locked.user_id):
            raise Conflict("The agent has an active delivery; reassign or resolve it first")
        repo.revoke_grant(conn, assignment_id)
        repo.revoke_access(conn, locked.user_id, "role removed")
        write_event(
            conn,
            action="management.staff.role_removed",
            actor_user_id=principal.user_id,
            actor_role=_actor_role(principal, locked.role, locked.region_id),
            target_type="user",
            target_id=str(locked.user_id),
            region_id=locked.region_id,
            kitchen_id=locked.kitchen_id,
            reason=text_reason,
            correlation_id=current_request_id(),
            before={"role": locked.role},
        )


def set_active(principal: Principal, user_id: uuid.UUID, *, active: bool, reason: str) -> None:
    """Deactivate or reactivate a staff account the caller may fully manage (MG-01)."""
    text_reason = _reason(reason)
    if user_id == principal.user_id:
        raise Forbidden
    with get_engine().connect() as conn:
        grants = repo.user_grants(conn, user_id)
    staff_grants = [g for g in grants if g.role in repo.STAFF_ROLES]
    if not staff_grants or not all(_may_manage(principal, g.role, g.region_id) for g in staff_grants):
        raise NotFound  # not staff the caller may manage (incl. a CA, or someone in another region)
    if not active and any(g.role == Role.DELIVERY_AGENT for g in staff_grants):
        _stop_agent_work(principal, user_id, text_reason)
    with get_engine().begin() as conn:
        status = repo.user_status(conn, user_id)
        target = "ACTIVE" if active else "DEACTIVATED"
        if status == target:
            raise Conflict(f"The account is already {target.lower()}")
        if not active and repo.active_delivery(conn, user_id):
            raise Conflict("The agent has an active delivery; reassign or resolve it first")
        repo.set_user_status(conn, user_id, target)
        if not active:
            repo.revoke_access(conn, user_id, "account deactivated")
        first = staff_grants[0]
        write_event(
            conn,
            action="management.staff.reactivated" if active else "management.staff.deactivated",
            actor_user_id=principal.user_id,
            actor_role=_actor_role(principal, first.role, first.region_id),
            target_type="user",
            target_id=str(user_id),
            region_id=first.region_id,
            reason=text_reason,
            correlation_id=current_request_id(),
            before={"status": status},
            after={"status": target},
        )
