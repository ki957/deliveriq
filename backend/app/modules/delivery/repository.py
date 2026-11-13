"""SQL for delivery assignments, agent availability, delivery codes and GPS points.

Parameterised; callers own the transaction. Orders and users are read here, never written (the orders
module owns every order status change).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, Row, text


@dataclass(frozen=True)
class LiveAssignment:
    order_id: uuid.UUID
    assignment_id: uuid.UUID
    status: str
    agent_user_id: uuid.UUID
    agent_name: str


@dataclass(frozen=True)
class AssignmentRow:
    id: uuid.UUID
    order_id: uuid.UUID
    agent_user_id: uuid.UUID
    status: str
    offered_at: datetime
    responded_at: datetime | None
    region_id: uuid.UUID
    kitchen_id: uuid.UUID
    is_test_fixture: bool
    fulfilment_status: str


@dataclass(frozen=True)
class WorkOrder:
    """What an agent sees for an offer or an accepted delivery (DL-08)."""

    order_id: uuid.UUID
    fulfilment_status: str
    is_test_fixture: bool
    special_instructions: str | None
    delivery_address: str | None
    lat: float | None
    lng: float | None
    kitchen_name: str
    kitchen_lat: float
    kitchen_lng: float
    kitchen_location_is_synthetic: bool
    customer_mobile: str
    payment_method: str | None
    payment_status: str | None
    payable_paise: int | None
    customer_unavailable_since: datetime | None
    delivery_exception_open: bool
    otp_failed_attempts: int | None
    otp_verified: bool


@dataclass(frozen=True)
class AgentRow:
    id: uuid.UUID
    name: str
    status: str
    changed_at: datetime | None
    live_status: str | None
    live_order_id: uuid.UUID | None


@dataclass(frozen=True)
class OtpRow:
    order_id: uuid.UUID
    nonce: str
    failed_attempts: int
    verified_at: datetime | None


@dataclass(frozen=True)
class PointRow:
    lat: float
    lng: float
    accuracy_m: Decimal | None
    recorded_at: datetime
    source: str


@dataclass(frozen=True)
class HistoryRow:
    order_id: uuid.UUID
    status: str
    fulfilment_status: str
    is_test_fixture: bool
    offered_at: datetime
    picked_up_at: datetime | None
    delivered_at: datetime | None


_LIVE = """
    SELECT a.order_id, a.id, a.status, a.agent_user_id, u.display_name
      FROM app.delivery_assignments a JOIN app.users u ON u.id = a.agent_user_id
     WHERE a.order_id = ANY(:ids) AND a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED')
"""
_ASSIGNMENT = """
    SELECT a.id, a.order_id, a.agent_user_id, a.status, a.offered_at, a.responded_at, o.region_id,
           o.kitchen_id, o.is_test_fixture, o.fulfilment_status
      FROM app.delivery_assignments a JOIN app.orders o ON o.id = a.order_id
"""


def _assignment(row: Row[Any] | None) -> AssignmentRow | None:
    return AssignmentRow(**row._mapping) if row else None


# ---------------------------------------------------------------- offers and assignments
def offer_next(conn: Connection, order_id: uuid.UUID) -> uuid.UUID | None:
    """The single re-offer rule (migration 0011, DDR-113 (3))."""
    result: uuid.UUID | None = conn.execute(text("SELECT app.offer_next(:o)"), {"o": order_id}).scalar_one()
    return result


def live(
    conn: Connection, order_ids: list[uuid.UUID], *, lock: bool = False
) -> dict[uuid.UUID, LiveAssignment]:
    sql = _LIVE + (" FOR UPDATE OF a" if lock else "")
    rows = conn.execute(text(sql), {"ids": order_ids}).all()
    return {r[0]: LiveAssignment(*r) for r in rows}


def find(conn: Connection, assignment_id: uuid.UUID, *, lock: bool = False) -> AssignmentRow | None:
    sql = _ASSIGNMENT + " WHERE a.id = :id" + (" FOR UPDATE OF a" if lock else "")
    return _assignment(conn.execute(text(sql), {"id": assignment_id}).first())


def live_for_order(conn: Connection, order_id: uuid.UUID, *, lock: bool = False) -> AssignmentRow | None:
    sql = _ASSIGNMENT + " WHERE a.order_id = :o AND a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED')"
    return _assignment(
        conn.execute(text(sql + (" FOR UPDATE OF a" if lock else "")), {"o": order_id}).first()
    )


def live_for_agent(conn: Connection, agent: uuid.UUID, *, lock: bool = False) -> AssignmentRow | None:
    sql = (
        _ASSIGNMENT
        + " WHERE a.agent_user_id = :a AND a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED')"
    )
    return _assignment(conn.execute(text(sql + (" FOR UPDATE OF a" if lock else "")), {"a": agent}).first())


def insert_offer(conn: Connection, order_id: uuid.UUID, agent: uuid.UUID) -> uuid.UUID:
    assignment_id: uuid.UUID = conn.execute(
        text(
            "INSERT INTO app.delivery_assignments (order_id, agent_user_id, status) "
            "VALUES (:o, :a, 'OFFERED') RETURNING id"
        ),
        {"o": order_id, "a": agent},
    ).scalar_one()
    return assignment_id


def set_status(conn: Connection, assignment_id: uuid.UUID, status: str) -> None:
    conn.execute(
        text(
            "UPDATE app.delivery_assignments SET status = :s, "
            "responded_at = coalesce(responded_at, now()) WHERE id = :id"
        ),
        {"s": status, "id": assignment_id},
    )


def seconds_since_offer(conn: Connection, assignment_id: uuid.UUID) -> float:
    seconds: float = conn.execute(
        text("SELECT extract(epoch FROM now() - offered_at) FROM app.delivery_assignments WHERE id = :id"),
        {"id": assignment_id},
    ).scalar_one()
    return float(seconds)


def work_order(conn: Connection, order_id: uuid.UUID) -> WorkOrder | None:
    row = conn.execute(
        text(
            "SELECT o.id, o.fulfilment_status, o.is_test_fixture, o.special_instructions, "
            "o.delivery_address, "
            "ST_Y(o.delivery_location::geometry), ST_X(o.delivery_location::geometry), k.name, "
            "ST_Y(k.location::geometry), ST_X(k.location::geometry), k.location_is_synthetic, u.mobile_e164, "
            "p.method, p.status, o.payable_paise, o.customer_unavailable_since, o.delivery_exception_open, "
            "t.failed_attempts, t.verified_at IS NOT NULL "
            "FROM app.orders o JOIN app.kitchens k ON k.id = o.kitchen_id "
            "JOIN app.users u ON u.id = o.customer_user_id "
            "LEFT JOIN app.payments p ON p.order_id = o.id "
            "LEFT JOIN app.delivery_otps t ON t.order_id = o.id WHERE o.id = :o"
        ),
        {"o": order_id},
    ).first()
    if row is None:
        return None
    values = [*row[:-1], bool(row[-1])]
    return WorkOrder(**dict(zip([f.name for f in fields(WorkOrder)], values, strict=True)))


# ---------------------------------------------------------------- availability (DL-01, DL-06)
def availability(conn: Connection, agent: uuid.UUID) -> tuple[str, datetime | None]:
    row = conn.execute(
        text("SELECT status, changed_at FROM app.agent_availability WHERE agent_user_id = :a"), {"a": agent}
    ).first()
    return (row[0], row[1]) if row else ("OFFLINE", None)


def set_availability(
    conn: Connection, agent: uuid.UUID, status: str, by: uuid.UUID, reason: str | None
) -> None:
    conn.execute(
        text(
            "INSERT INTO app.agent_availability (agent_user_id, status, changed_by, reason) "
            "VALUES (:a, :s, :by, :r) ON CONFLICT (agent_user_id) DO UPDATE SET status = :s, "
            "changed_at = now(), changed_by = :by, reason = :r"
        ),
        {"a": agent, "s": status, "by": by, "r": reason},
    )


def now(conn: Connection) -> datetime:
    value: datetime = conn.execute(text("SELECT now()")).scalar_one()
    return value


def waiting_orders(conn: Connection, region_id: uuid.UUID) -> list[uuid.UUID]:
    """Orders the kitchen holds with no live offer or assignment, oldest acceptance first."""
    rows = conn.execute(
        text(
            "SELECT o.id FROM app.orders o WHERE o.region_id = :r "
            "AND o.fulfilment_status IN ('ACCEPTED', 'PREPARING', 'READY_FOR_PICKUP') "
            "AND NOT EXISTS (SELECT 1 FROM app.delivery_assignments a WHERE a.order_id = o.id "
            "AND a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED')) ORDER BY o.accepted_at, o.id"
        ),
        {"r": region_id},
    ).scalars()
    return list(rows)


def order_region(conn: Connection, order_id: uuid.UUID) -> uuid.UUID:
    region: uuid.UUID | None = conn.execute(
        text("SELECT region_id FROM app.orders WHERE id = :o"), {"o": order_id}
    ).scalar_one_or_none()
    if region is None:
        raise LookupError(order_id)
    return region


def agent_region(conn: Connection, agent: uuid.UUID) -> uuid.UUID | None:
    region: uuid.UUID | None = conn.execute(
        text(
            "SELECT region_id FROM app.role_assignments WHERE user_id = :a AND role = 'DELIVERY_AGENT' "
            "AND revoked_at IS NULL ORDER BY granted_at LIMIT 1"
        ),
        {"a": agent},
    ).scalar_one_or_none()
    return region


def is_agent_in_region(conn: Connection, agent: uuid.UUID, region_id: uuid.UUID) -> bool:
    found: bool = conn.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM app.users u JOIN app.role_assignments r ON r.user_id = u.id "
            "WHERE u.id = :a AND u.status = 'ACTIVE' AND r.role = 'DELIVERY_AGENT' AND r.region_id = :reg "
            "AND r.revoked_at IS NULL)"
        ),
        {"a": agent, "reg": region_id},
    ).scalar_one()
    return found


def agents(conn: Connection, regions: list[uuid.UUID] | None) -> list[AgentRow]:
    """Agents with availability and their live work (manager oversight, #7 §10). None = every region."""
    rows = conn.execute(
        text(
            "SELECT DISTINCT ON (u.id) u.id, u.display_name, coalesce(av.status, 'OFFLINE'), av.changed_at, "
            "a.status, a.order_id FROM app.users u "
            "JOIN app.role_assignments r ON r.user_id = u.id AND r.role = 'DELIVERY_AGENT' AND r.revoked_at "
            "IS NULL "
            "LEFT JOIN app.agent_availability av ON av.agent_user_id = u.id "
            "LEFT JOIN app.delivery_assignments a ON a.agent_user_id = u.id "
            "AND a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED') "
            "WHERE u.status = 'ACTIVE' AND (CAST(:all_regions AS boolean) OR r.region_id = ANY(:regions)) "
            "ORDER BY u.id"
        ),
        {"all_regions": regions is None, "regions": regions or []},
    ).all()
    return sorted((AgentRow(*r) for r in rows), key=lambda a: a.name)


# ---------------------------------------------------------------- delivery codes (DL-11; DDR-113 (6))
def otp(conn: Connection, order_id: uuid.UUID, *, lock: bool = False) -> OtpRow | None:
    sql = "SELECT order_id, nonce, failed_attempts, verified_at FROM app.delivery_otps WHERE order_id = :o"
    row = conn.execute(text(sql + (" FOR UPDATE" if lock else "")), {"o": order_id}).first()
    return OtpRow(*row) if row else None


def issue_otp(conn: Connection, order_id: uuid.UUID, nonce: str, by: uuid.UUID | None) -> None:
    conn.execute(
        text(
            "INSERT INTO app.delivery_otps (order_id, nonce, issued_by) VALUES (:o, :n, :by) "
            "ON CONFLICT (order_id) DO UPDATE SET nonce = :n, issued_by = :by, issued_at = now(), "
            "failed_attempts = 0, verified_at = NULL"
        ),
        {"o": order_id, "n": nonce, "by": by},
    )


def record_otp_attempt(conn: Connection, order_id: uuid.UUID, *, success: bool) -> int:
    attempts: int = conn.execute(
        text(
            "UPDATE app.delivery_otps SET failed_attempts = failed_attempts + CASE WHEN :ok THEN 0 ELSE 1 "
            "END, "
            "verified_at = CASE WHEN :ok THEN now() ELSE verified_at END WHERE order_id = :o "
            "RETURNING failed_attempts"
        ),
        {"ok": success, "o": order_id},
    ).scalar_one()
    return attempts


# ---------------------------------------------------------------- GPS points (DDR-52; DDR-113 (8))
def last_recorded_at(conn: Connection, assignment_id: uuid.UUID) -> datetime | None:
    value: datetime | None = conn.execute(
        text("SELECT max(recorded_at) FROM app.delivery_locations WHERE assignment_id = :a"),
        {"a": assignment_id},
    ).scalar_one()
    return value


def insert_point(
    conn: Connection,
    a: AssignmentRow,
    *,
    lat: float,
    lng: float,
    accuracy_m: Decimal | None,
    recorded_at: datetime,
    source: str,
) -> None:
    conn.execute(
        text(
            "INSERT INTO app.delivery_locations (assignment_id, order_id, agent_user_id, location, "
            "accuracy_m, "
            "recorded_at, source) VALUES (:a, :o, :ag, ST_SetSRID(ST_MakePoint(:lng, :lat), "
            "4326)::geography, "
            ":acc, :at, :src)"
        ),
        {
            "a": a.id,
            "o": a.order_id,
            "ag": a.agent_user_id,
            "lat": lat,
            "lng": lng,
            "acc": accuracy_m,
            "at": recorded_at,
            "src": source,
        },
    )


def latest_point(conn: Connection, order_id: uuid.UUID) -> PointRow | None:
    row = conn.execute(
        text(
            "SELECT ST_Y(location::geometry), ST_X(location::geometry), accuracy_m, recorded_at, source "
            "FROM app.delivery_locations WHERE order_id = :o ORDER BY recorded_at DESC LIMIT 1"
        ),
        {"o": order_id},
    ).first()
    return PointRow(*row) if row else None


def gps_summary(conn: Connection, assignment_id: uuid.UUID) -> dict[str, object]:
    """Per-delivery summary for `delivery.completed` (DDR-78): no individual points leave the table."""
    row = conn.execute(
        text(
            "WITH p AS (SELECT location, recorded_at, source, "
            "lag(location) OVER (ORDER BY recorded_at) AS prev FROM app.delivery_locations WHERE "
            "assignment_id = :a) "
            "SELECT count(*), coalesce(sum(ST_Distance(location, prev)) / 1000.0, 0), "
            "extract(epoch FROM max(recorded_at) - min(recorded_at)), "
            "count(*) FILTER (WHERE source = 'REAL'), count(*) FILTER (WHERE source = 'SIMULATED') FROM p"
        ),
        {"a": assignment_id},
    ).one()
    return {
        "points": int(row[0]),
        "km": round(float(row[1]), 2),
        "duration_seconds": int(row[2] or 0),
        "real_points": int(row[3]),
        "simulated_points": int(row[4]),
    }


def history(conn: Connection, agent: uuid.UUID, days: int) -> list[HistoryRow]:
    rows = conn.execute(
        text(
            "SELECT a.order_id, a.status, o.fulfilment_status, o.is_test_fixture, a.offered_at, "
            "(SELECT max(h.changed_at) FROM app.status_history h WHERE h.machine = 'fulfilment' "
            " AND h.entity_id = o.id AND h.to_status = 'PICKED_UP'), "
            "(SELECT max(h.changed_at) FROM app.status_history h WHERE h.machine = 'fulfilment' "
            " AND h.entity_id = o.id AND h.to_status = 'DELIVERED') "
            "FROM app.delivery_assignments a JOIN app.orders o ON o.id = a.order_id "
            "WHERE a.agent_user_id = :a AND a.status IN ('COMPLETED', 'FAILED') "
            "AND a.offered_at > now() - make_interval(days => :d) ORDER BY a.offered_at DESC LIMIT 100"
        ),
        {"a": agent, "d": days},
    ).all()
    return [HistoryRow(*r) for r in rows]


def items(conn: Connection, order_id: uuid.UUID) -> list[tuple[str, int]]:
    """Item summary for the agent (DL-08): name and quantity only."""
    rows = conn.execute(
        text(
            "SELECT coalesce(item_name, 'Item'), quantity FROM app.order_items "
            "WHERE order_id = :o ORDER BY created_at, id"
        ),
        {"o": order_id},
    ).all()
    return [(str(r[0]), int(r[1])) for r in rows]


def set_display_name(conn: Connection, user_id: uuid.UUID, name: str) -> None:
    conn.execute(text("UPDATE app.users SET display_name = :n WHERE id = :id"), {"n": name, "id": user_id})
