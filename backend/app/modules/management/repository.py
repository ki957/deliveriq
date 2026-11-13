"""Read-only SQL for the management views, plus staff access writes (users, role assignments, sessions).

Parameterised; callers own the transaction. `regions` is None for every region (CA) or the caller's
assigned regions (RM); every query filters by it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

Regions = list[uuid.UUID] | None


def _scope(regions: Regions) -> dict[str, Any]:
    return {"all_regions": regions is None, "regions": regions or []}


_IN_SCOPE = "(CAST(:all_regions AS boolean) OR {col} = ANY(:regions))"


def in_scope(col: str) -> str:
    return _IN_SCOPE.format(col=col)


# ---------------------------------------------------------------- kitchens and overview
@dataclass(frozen=True)
class KitchenRow:
    id: uuid.UUID
    code: str
    name: str
    region_id: uuid.UUID
    region_name: str
    mode: str


def kitchens(conn: Connection, regions: Regions) -> list[KitchenRow]:
    rows = conn.execute(
        text(
            "SELECT k.id, k.code, k.name, k.region_id, r.name, k.mode FROM app.kitchens k "  # noqa: S608 - fixed column names, values bound
            "JOIN app.regions r ON r.id = k.region_id WHERE k.status = 'ACTIVE' AND "
            f"{in_scope('k.region_id')} "
            "ORDER BY k.code"
        ),
        _scope(regions),
    ).all()
    return [KitchenRow(*r) for r in rows]


def order_counts(conn: Connection, regions: Regions) -> dict[str, int]:
    rows = conn.execute(
        text(
            "SELECT fulfilment_status, count(*) FROM app.orders o "  # noqa: S608 - fixed column names, values bound
            f"WHERE {in_scope('o.region_id')} AND fulfilment_status NOT IN "
            "('DELIVERED', 'CANCELLED', 'REJECTED', 'DELIVERY_FAILED') GROUP BY 1"
        ),
        _scope(regions),
    ).all()
    return {str(r[0]): int(r[1]) for r in rows}


def overdue_incoming(conn: Connection, regions: Regions) -> int:
    """Incoming longer than the kitchen's acceptance timeout (KI-02; a DDR-42 test default)."""
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM app.orders o WHERE o.fulfilment_status = 'PENDING_KITCHEN' "  # noqa: S608 - fixed column names, values bound
            f"AND {in_scope('o.region_id')} AND (SELECT max(h.changed_at) FROM app.status_history h "
            "WHERE h.machine = 'fulfilment' AND h.entity_id = o.id AND h.to_status = 'PENDING_KITCHEN') "
            "< now() - make_interval(mins => coalesce((SELECT c.value FROM app.config_settings c "
            "WHERE c.key = 'KITCHEN_ACCEPTANCE_TIMEOUT' AND c.kitchen_id = o.kitchen_id), 5)::integer)"
        ),
        _scope(regions),
    ).scalar_one()
    return count


def pending_counts(conn: Connection, regions: Regions) -> dict[str, int]:
    row = conn.execute(
        text(
            "SELECT "  # noqa: S608 - fixed column names, values bound
            "(SELECT count(*) FROM app.dish_availability_requests r WHERE r.status = 'PENDING' "
            f"AND {in_scope('r.region_id')}), "
            "(SELECT count(*) FROM app.delivery_assignments a JOIN app.orders o ON o.id = a.order_id "
            f"WHERE a.status = 'FAILURE_REQUESTED' AND {in_scope('o.region_id')}), "
            "(SELECT count(*) FROM app.orders o WHERE o.delivery_exception_open "
            f"AND {in_scope('o.region_id')}), "
            "(SELECT count(*) FROM app.agent_availability v JOIN app.role_assignments ra ON "
            "ra.user_id = v.agent_user_id "
            "AND ra.role = 'DELIVERY_AGENT' AND ra.revoked_at IS NULL WHERE v.status = 'ONLINE' "
            f"AND {in_scope('ra.region_id')}), "
            "(SELECT count(*) FROM app.delivery_assignments a JOIN app.orders o ON o.id = a.order_id "
            f"WHERE a.status IN ('ACCEPTED', 'FAILURE_REQUESTED') AND {in_scope('o.region_id')})"
        ),
        _scope(regions),
    ).one()
    keys = (
        "availability_requests",
        "failure_requests",
        "delivery_exceptions",
        "online_agents",
        "active_deliveries",
    )
    return dict(zip(keys, (int(v) for v in row), strict=True))


# ---------------------------------------------------------------- orders (#10 §7; DDR-114 (9))
@dataclass(frozen=True)
class OrderFilter:
    regions: Regions
    date_from: datetime
    date_to: datetime
    status: str | None = None
    kitchen_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    exception: bool | None = None


@dataclass(frozen=True)
class OrderListRow:
    id: uuid.UUID
    placed_at: datetime
    fulfilment_status: str
    is_test_fixture: bool
    kitchen_name: str
    region_id: uuid.UUID
    payable_paise: int | None
    payment_method: str | None
    payment_status: str | None
    agent_name: str | None
    assignment_status: str | None
    delivery_exception_open: bool


_ORDERS = """
    SELECT o.id, o.placed_at, o.fulfilment_status, o.is_test_fixture, k.name, o.region_id, o.payable_paise,
           p.method, p.status, ag.display_name, a.status, o.delivery_exception_open
      FROM app.orders o JOIN app.kitchens k ON k.id = o.kitchen_id
      LEFT JOIN app.payments p ON p.order_id = o.id
      LEFT JOIN LATERAL (SELECT x.agent_user_id, x.status FROM app.delivery_assignments x
                          WHERE x.order_id = o.id
                          ORDER BY x.offered_at DESC LIMIT 1) a ON true
      LEFT JOIN app.users ag ON ag.id = a.agent_user_id
"""


def _order_where(f: OrderFilter) -> tuple[str, dict[str, Any]]:
    where = [in_scope("o.region_id"), "o.placed_at >= :df", "o.placed_at < :dt"]
    params: dict[str, Any] = {**_scope(f.regions), "df": f.date_from, "dt": f.date_to}
    if f.status:
        where.append("o.fulfilment_status = :st")
        params["st"] = f.status
    if f.kitchen_id:
        where.append("o.kitchen_id = :k")
        params["k"] = f.kitchen_id
    if f.agent_id:
        where.append("a.agent_user_id = :ag")
        params["ag"] = f.agent_id
    if f.exception is not None:
        where.append("o.delivery_exception_open = :ex")
        params["ex"] = f.exception
    return " WHERE " + " AND ".join(where), params


def orders(conn: Connection, f: OrderFilter, *, limit: int, offset: int) -> tuple[list[OrderListRow], int]:
    where, params = _order_where(f)
    total: int = conn.execute(text("SELECT count(*) FROM (" + _ORDERS + where + ") t"), params).scalar_one()  # noqa: S608
    rows = conn.execute(
        text(_ORDERS + where + " ORDER BY o.placed_at DESC, o.id LIMIT :lim OFFSET :off"),
        {**params, "lim": limit, "off": offset},
    ).all()
    return [OrderListRow(*r) for r in rows], total


def order_head(conn: Connection, order_id: uuid.UUID, regions: Regions) -> OrderListRow | None:
    row = conn.execute(
        text(_ORDERS + f" WHERE o.id = :id AND {in_scope('o.region_id')}"),
        {**_scope(regions), "id": order_id},
    ).first()
    return OrderListRow(*row) if row else None


@dataclass(frozen=True)
class TimelineRow:
    machine: str
    from_status: str | None
    to_status: str
    actor_role: str
    actor_name: str | None
    reason: str | None
    changed_at: datetime


def timeline(conn: Connection, order_id: uuid.UUID) -> list[TimelineRow]:
    """Fulfilment, item, payment and assignment history of one order (who, when, why)."""
    rows = conn.execute(
        text(
            "SELECT h.machine, h.from_status, h.to_status, h.actor_role, u.display_name, "
            "h.reason, h.changed_at "
            "FROM app.status_history h LEFT JOIN app.users u ON u.id = h.actor_user_id "
            "WHERE (h.machine = 'fulfilment' AND h.entity_id = :o) "
            "OR (h.machine = 'payment' AND h.entity_id IN (SELECT id FROM app.payments WHERE order_id = :o)) "
            "OR (h.machine = 'assignment' AND h.entity_id IN (SELECT id FROM "
            "app.delivery_assignments WHERE order_id = :o)) "
            "OR (h.machine = 'item' AND h.entity_id IN (SELECT id FROM app.order_items WHERE order_id = :o)) "
            "ORDER BY h.changed_at, h.id"
        ),
        {"o": order_id},
    ).all()
    return [TimelineRow(*r) for r in rows]


def order_items(conn: Connection, order_id: uuid.UUID) -> list[tuple[str, int]]:
    rows = conn.execute(
        text(
            "SELECT coalesce(item_name, 'Item'), quantity FROM app.order_items WHERE order_id = :o "
            "ORDER BY created_at, id"
        ),
        {"o": order_id},
    ).all()
    return [(str(r[0]), int(r[1])) for r in rows]


# ---------------------------------------------------------------- deliveries (#10 §6; DDR-114 (11))
@dataclass(frozen=True)
class DeliveryRow:
    order_id: uuid.UUID
    assignment_id: uuid.UUID
    assignment_status: str
    fulfilment_status: str
    is_test_fixture: bool
    agent_id: uuid.UUID
    agent_name: str
    delivery_address: str | None
    delivery_exception_open: bool
    lat: float | None
    lng: float | None
    recorded_at: datetime | None
    source: str | None


def deliveries(conn: Connection, regions: Regions) -> list[DeliveryRow]:
    rows = conn.execute(
        text(
            "SELECT o.id, a.id, a.status, o.fulfilment_status, o.is_test_fixture, u.id, u.display_name, "  # noqa: S608 - fixed column names, values bound
            "o.delivery_address, o.delivery_exception_open, ST_Y(l.location::geometry), "
            "ST_X(l.location::geometry), "
            "l.recorded_at, l.source FROM app.delivery_assignments a JOIN app.orders o ON o.id = a.order_id "
            "JOIN app.users u ON u.id = a.agent_user_id "
            "LEFT JOIN LATERAL (SELECT x.location, x.recorded_at, x.source FROM app.delivery_locations x "
            "WHERE x.assignment_id = a.id ORDER BY x.recorded_at DESC LIMIT 1) l ON true "
            f"WHERE a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED') AND {in_scope('o.region_id')} "
            "ORDER BY a.offered_at"
        ),
        _scope(regions),
    ).all()
    return [DeliveryRow(*r) for r in rows]


# ---------------------------------------------------------------- refunds (MG-05; DDR-114 (6))
@dataclass(frozen=True)
class RefundRow:
    order_id: uuid.UUID
    is_test_fixture: bool
    amount_paise: int | None
    method: str
    status: str
    reason: str | None
    actor_role: str | None
    actor_name: str | None
    changed_at: datetime | None
    pending_decision: bool


def refunds(conn: Connection, regions: Regions, limit: int) -> list[RefundRow]:
    """Refunds made (who, why, when) and failed deliveries whose prepaid payment awaits a decision."""
    rows = conn.execute(
        text(
            "SELECT o.id, o.is_test_fixture, p.amount_paise, p.method, p.status, h.reason, "  # noqa: S608 - fixed column names, values bound
            "h.actor_role, u.display_name, "
            "h.changed_at, (o.fulfilment_status = 'DELIVERY_FAILED' AND p.status = 'SUCCEEDED') AS pending "
            "FROM app.payments p JOIN app.orders o ON o.id = p.order_id "
            "LEFT JOIN LATERAL (SELECT y.reason, y.actor_role, y.actor_user_id, y.changed_at "
            "FROM app.status_history y "
            "WHERE y.machine = 'payment' AND y.entity_id = p.id AND y.to_status = 'REFUND_PENDING' "
            "ORDER BY y.id DESC LIMIT 1) h ON true LEFT JOIN app.users u ON u.id = h.actor_user_id "
            f"WHERE {in_scope('o.region_id')} AND (p.status IN ('REFUND_PENDING', 'REFUNDED') "
            "OR (o.fulfilment_status = 'DELIVERY_FAILED' AND p.status = 'SUCCEEDED')) "
            "ORDER BY coalesce(h.changed_at, o.updated_at) DESC LIMIT :lim"
        ),
        {**_scope(regions), "lim": limit},
    ).all()
    return [RefundRow(*r) for r in rows]


# ---------------------------------------------------------------- inventory, read-only (DDR-114 (12))
@dataclass(frozen=True)
class StockRow:
    ingredient_id: uuid.UUID
    name: str
    unit: str
    on_hand: Decimal
    reserved: Decimal
    low_stock_threshold: Decimal | None
    is_test_fixture: bool


@dataclass(frozen=True)
class MovementRow:
    created_at: datetime
    ingredient_name: str
    unit: str
    delta: Decimal
    kind: str
    reason: str | None
    actor_role: str
    order_id: uuid.UUID | None
    is_test_fixture: bool


def stock(conn: Connection, kitchen_id: uuid.UUID) -> list[StockRow]:
    rows = conn.execute(
        text(
            "SELECT s.ingredient_id, i.name, i.unit, s.on_hand, s.reserved, "
            "s.low_stock_threshold, s.is_test_fixture "
            "FROM app.ingredient_stock s JOIN app.ingredients i ON i.id = s.ingredient_id WHERE "
            "s.kitchen_id = :k "
            "ORDER BY i.name"
        ),
        {"k": kitchen_id},
    ).all()
    return [StockRow(*r) for r in rows]


def movements(conn: Connection, kitchen_id: uuid.UUID, limit: int) -> list[MovementRow]:
    rows = conn.execute(
        text(
            "SELECT m.created_at, i.name, i.unit, m.delta, m.kind, m.reason, m.actor_role, "
            "m.order_id, m.is_test_fixture "
            "FROM app.stock_movements m JOIN app.ingredients i ON i.id = m.ingredient_id WHERE "
            "m.kitchen_id = :k "
            "ORDER BY m.id DESC LIMIT :lim"
        ),
        {"k": kitchen_id, "lim": limit},
    ).all()
    return [MovementRow(*r) for r in rows]


def kitchen_region(conn: Connection, kitchen_id: uuid.UUID) -> uuid.UUID | None:
    region: uuid.UUID | None = conn.execute(
        text("SELECT region_id FROM app.kitchens WHERE id = :k"), {"k": kitchen_id}
    ).scalar_one_or_none()
    return region


# ---------------------------------------------------------------- audit (#10 §12; DDR-114 (7))
@dataclass(frozen=True)
class AuditFilter:
    regions: Regions
    include_unscoped: bool
    date_from: datetime
    date_to: datetime
    action: str | None = None
    target_type: str | None = None
    actor_role: str | None = None


@dataclass(frozen=True)
class AuditRow:
    occurred_at: datetime
    actor_role: str
    actor_name: str | None
    action: str
    target_type: str
    target_id: str | None
    region_id: uuid.UUID | None
    outcome: str
    reason: str | None
    correlation_id: str | None
    before_summary: Any
    after_summary: Any


def _audit_where(f: AuditFilter) -> tuple[str, dict[str, Any]]:
    scope = "(CAST(:all_regions AS boolean) OR e.region_id = ANY(:regions)"
    scope += " OR (CAST(:unscoped AS boolean) AND e.region_id IS NULL))"
    where = [scope, "e.occurred_at >= :df", "e.occurred_at < :dt"]
    params: dict[str, Any] = {
        **_scope(f.regions),
        "unscoped": f.include_unscoped,
        "df": f.date_from,
        "dt": f.date_to,
    }
    if f.action:
        where.append("e.action ILIKE :act")
        params["act"] = f.action.replace("%", "").replace("_", r"\_") + "%"
    if f.target_type:
        where.append("e.target_type = :tt")
        params["tt"] = f.target_type
    if f.actor_role:
        where.append("e.actor_role = :ar")
        params["ar"] = f.actor_role
    return " WHERE " + " AND ".join(where), params


_AUDIT = """
    SELECT e.occurred_at, e.actor_role, u.display_name, e.action, e.target_type, e.target_id, e.region_id,
           e.outcome, e.reason, e.correlation_id, e.before_summary, e.after_summary
      FROM audit.events e LEFT JOIN app.users u ON u.id = e.actor_user_id
"""


def audit(conn: Connection, f: AuditFilter, *, limit: int, offset: int) -> tuple[list[AuditRow], int]:
    where, params = _audit_where(f)
    total: int = conn.execute(text("SELECT count(*) FROM audit.events e" + where), params).scalar_one()  # noqa: S608
    rows = conn.execute(
        text(_AUDIT + where + " ORDER BY e.occurred_at DESC, e.id LIMIT :lim OFFSET :off"),
        {**params, "lim": limit, "off": offset},
    ).all()
    return [AuditRow(*r) for r in rows], total


# ---------------------------------------------------------------- staff (#10 §4; DDR-114 (3)–(5))
@dataclass(frozen=True)
class StaffGrantRow:
    assignment_id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    mobile: str
    user_status: str
    role: str
    region_id: uuid.UUID | None
    kitchen_id: uuid.UUID | None
    granted_at: datetime


STAFF_ROLES = ("KITCHEN_STAFF", "KITCHEN_MANAGER", "DELIVERY_AGENT", "REGIONAL_MANAGER", "CENTRAL_ADMIN")


def staff(conn: Connection, regions: Regions) -> list[StaffGrantRow]:
    """Active staff grants in scope (CA: all, incl. CA grants without a region)."""
    rows = conn.execute(
        text(
            "SELECT r.id, u.id, u.display_name, u.mobile_e164, u.status, r.role, r.region_id, "  # noqa: S608 - fixed column names, values bound
            "r.kitchen_id, r.granted_at "
            "FROM app.role_assignments r JOIN app.users u ON u.id = r.user_id "
            f"WHERE r.revoked_at IS NULL AND r.role = ANY(:roles) AND {in_scope('r.region_id')} "
            "ORDER BY u.display_name, r.role"
        ),
        {**_scope(regions), "roles": list(STAFF_ROLES)},
    ).all()
    return [StaffGrantRow(*r) for r in rows]


def grant(conn: Connection, assignment_id: uuid.UUID, *, lock: bool = False) -> StaffGrantRow | None:
    sql = (
        "SELECT r.id, u.id, u.display_name, u.mobile_e164, u.status, r.role, r.region_id, "
        "r.kitchen_id, r.granted_at "
        "FROM app.role_assignments r JOIN app.users u ON u.id = r.user_id WHERE r.id = :id AND "
        "r.revoked_at IS NULL"
    )
    row = conn.execute(text(sql + (" FOR UPDATE OF r" if lock else "")), {"id": assignment_id}).first()
    return StaffGrantRow(*row) if row else None


def user_grants(conn: Connection, user_id: uuid.UUID) -> list[StaffGrantRow]:
    rows = conn.execute(
        text(
            "SELECT r.id, u.id, u.display_name, u.mobile_e164, u.status, r.role, r.region_id, "
            "r.kitchen_id, r.granted_at "
            "FROM app.role_assignments r JOIN app.users u ON u.id = r.user_id "
            "WHERE r.user_id = :u AND r.revoked_at IS NULL"
        ),
        {"u": user_id},
    ).all()
    return [StaffGrantRow(*r) for r in rows]


def user_by_mobile(conn: Connection, mobile: str) -> tuple[uuid.UUID, str] | None:
    row = conn.execute(
        text("SELECT id, status FROM app.users WHERE mobile_e164 = :m FOR UPDATE"), {"m": mobile}
    ).first()
    return (row[0], row[1]) if row else None


def user_status(conn: Connection, user_id: uuid.UUID) -> str | None:
    status: str | None = conn.execute(
        text("SELECT status FROM app.users WHERE id = :u FOR UPDATE"), {"u": user_id}
    ).scalar_one_or_none()
    return status


def create_user(conn: Connection, name: str, mobile: str) -> uuid.UUID:
    user_id: uuid.UUID = conn.execute(
        text("INSERT INTO app.users (display_name, mobile_e164) VALUES (:n, :m) RETURNING id"),
        {"n": name, "m": mobile},
    ).scalar_one()
    return user_id


def insert_grant(
    conn: Connection,
    user_id: uuid.UUID,
    role: str,
    region_id: uuid.UUID | None,
    kitchen_id: uuid.UUID | None,
    by: uuid.UUID,
) -> uuid.UUID:
    assignment_id: uuid.UUID = conn.execute(
        text(
            "INSERT INTO app.role_assignments (user_id, role, region_id, kitchen_id, granted_by) "
            "VALUES (:u, :r, :reg, :k, :by) RETURNING id"
        ),
        {"u": user_id, "r": role, "reg": region_id, "k": kitchen_id, "by": by},
    ).scalar_one()
    return assignment_id


def revoke_grant(conn: Connection, assignment_id: uuid.UUID) -> None:
    conn.execute(
        text("UPDATE app.role_assignments SET revoked_at = now() WHERE id = :id"), {"id": assignment_id}
    )


def set_user_status(conn: Connection, user_id: uuid.UUID, status: str) -> None:
    conn.execute(text("UPDATE app.users SET status = :s WHERE id = :u"), {"s": status, "u": user_id})


def revoke_access(conn: Connection, user_id: uuid.UUID, reason: str) -> int:
    """End every session and trusted device of the user at once (#10 §4)."""
    sessions: int = conn.execute(
        text(
            "UPDATE app.sessions SET revoked_at = now(), revoke_reason = :r WHERE user_id = :u "
            "AND revoked_at IS NULL"
        ),
        {"u": user_id, "r": reason[:120]},
    ).rowcount
    conn.execute(
        text(
            "UPDATE app.trusted_devices SET revoked_at = now(), revoke_reason = :r "
            "WHERE user_id = :u AND revoked_at IS NULL"
        ),
        {"u": user_id, "r": reason[:120]},
    )
    return sessions


def active_delivery(conn: Connection, user_id: uuid.UUID) -> bool:
    found: bool = conn.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM app.delivery_assignments WHERE agent_user_id = :u "
            "AND status IN ('ACCEPTED', 'FAILURE_REQUESTED'))"
        ),
        {"u": user_id},
    ).scalar_one()
    return found


def kitchen_in_region(conn: Connection, kitchen_id: uuid.UUID, region_id: uuid.UUID) -> bool:
    found: bool = conn.execute(
        text("SELECT EXISTS (SELECT 1 FROM app.kitchens WHERE id = :k AND region_id = :r)"),
        {"k": kitchen_id, "r": region_id},
    ).scalar_one()
    return found


def region_exists(conn: Connection, region_id: uuid.UUID) -> bool:
    found: bool = conn.execute(
        text("SELECT EXISTS (SELECT 1 FROM app.regions WHERE id = :r AND status = 'ACTIVE')"),
        {"r": region_id},
    ).scalar_one()
    return found


def regions(conn: Connection, scope: Regions) -> list[tuple[uuid.UUID, str, str]]:
    rows = conn.execute(
        text(
            "SELECT id, code, name FROM app.regions r WHERE r.status = 'ACTIVE' AND "  # noqa: S608 - fixed column names, values bound
            f"{in_scope('r.id')} ORDER BY code"
        ),
        _scope(scope),
    ).all()
    return [(r[0], r[1], r[2]) for r in rows]
