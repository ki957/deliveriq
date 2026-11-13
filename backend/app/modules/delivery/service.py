"""Delivery assignments, agent availability and GPS (#7 §3–§6; DL-01–DL-08, DL-G1–DL-G5; DDR-51, DDR-52,
DDR-113).

Assignment never changes an order's fulfilment status (DDR-16, DDR-17): status changes (pickup, delivered,
failed) live in the orders service, which calls the helpers marked "caller's transaction" below.

Deny by default: an agent acts only on their own offer or assignment (anyone else's reads as not found);
managers act within `management.agents.assign` scope (RM assigned regions, CA everywhere).
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.permissions import Grant, Permission, Principal, Role, can
from app.core.request_context import current_request_id
from app.modules.delivery import domain as d
from app.modules.delivery import repository as repo
from app.shared.actor import set_actor
from app.shared.audit import write_event
from app.shared.config_values import value as config_value
from app.shared.events import emit

P = Permission
A = d.Assignment
LiveAssignment = repo.LiveAssignment
AssignmentRow = repo.AssignmentRow
WorkOrder = repo.WorkOrder
PointRow = repo.PointRow
HISTORY_DAYS = 30  # #7 §9 "latest 30 days"
NAME_MAX = 80


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class Invalid(Exception):
    pass


def _reason(reason: str | None, *, required: bool = True) -> str | None:
    text = (reason or "").strip()
    if required and not text:
        raise Invalid("A reason is required")
    if len(text) > d.REASON_MAX:
        raise Invalid(f"The reason can be at most {d.REASON_MAX} characters")
    return text or None


def _agent_region(principal: Principal) -> uuid.UUID:
    for grant in principal.grants:
        if grant.role is Role.DELIVERY_AGENT and grant.region_id is not None:
            return grant.region_id
    raise Forbidden


def _manager_role(principal: Principal, region_id: uuid.UUID) -> str:
    for grant in principal.grants:
        alone = Principal(principal.user_id, (Grant(grant.role, grant.region_id, grant.kitchen_id),))
        if can(alone, P.MGMT_AGENTS_ASSIGN, region_id=region_id):
            return grant.role.value
    raise NotFound  # outside the manager's scope reads as not found


def _event(conn: Connection, a: AssignmentRow, event_type: str, data: dict[str, object]) -> None:
    emit(
        conn,
        event_type=event_type,
        aggregate_type="order",
        aggregate_id=a.order_id,
        is_test_fixture=a.is_test_fixture,
        region_id=a.region_id,
        kitchen_id=a.kitchen_id,
        correlation_id=current_request_id(),
        # One event of each type per assignment: a reassigned order may be assigned again.
        idempotency_key=f"{event_type}:{a.id}",
        data={"order_id": str(a.order_id), "assignment_id": str(a.id), **data},
    )


# ---------------------------------------------------------------- caller's transaction (orders service)
def offer_on_acceptance(conn: Connection, order_id: uuid.UUID, region_id: uuid.UUID) -> LiveAssignment | None:
    """DDR-51: offer at kitchen acceptance through the single re-offer rule. None = "Awaiting agent"."""
    del region_id  # the rule reads the order's region itself
    if repo.offer_next(conn, order_id) is None:
        return None
    return repo.live(conn, [order_id]).get(order_id)


def revoke(conn: Connection, order_id: uuid.UUID) -> bool:
    """Revoke the order's live offer or assignment (DL-07); the caller's actor context holds the reason."""
    current = repo.live(conn, [order_id], lock=True).get(order_id)
    if current is None or not d.can_transition(A(current.status), A.REVOKED):
        return False  # a failure request stays with the manager (DA-18)
    repo.set_status(conn, current.assignment_id, A.REVOKED.value)
    return True


def live_for(conn: Connection, order_ids: list[uuid.UUID]) -> dict[uuid.UUID, LiveAssignment]:
    return repo.live(conn, order_ids) if order_ids else {}


def held_by(conn: Connection, agent: Principal, order_id: uuid.UUID) -> AssignmentRow:
    """The agent's own accepted assignment for this order (or a pending failure request); else NotFound."""
    a = repo.live_for_order(conn, order_id, lock=True)
    if a is None or a.agent_user_id != agent.user_id or a.status == A.OFFERED:
        raise NotFound
    if not can(agent, P.DELIVERY_ASSIGNMENTS_VIEW, region_id=a.region_id):
        raise NotFound
    return a


def move(conn: Connection, a: AssignmentRow, target: d.Assignment) -> None:
    repo.set_status(conn, a.id, target.value)


def issue_otp(conn: Connection, order_id: uuid.UUID, by: uuid.UUID | None) -> None:
    repo.issue_otp(conn, order_id, secrets.token_hex(24), by)


def code_for_customer(conn: Connection, order_id: uuid.UUID) -> str | None:
    """The six digits for the customer's own order page, while the delivery is open (DDR-113 (6))."""
    row = repo.otp(conn, order_id)
    if row is None or row.verified_at is not None:
        return None
    return d.delivery_code(get_settings().otp_pepper.get_secret_value(), str(order_id), row.nonce)


@dataclass(frozen=True)
class OtpCheck:
    ok: bool
    attempts_left: int


def check_otp(conn: Connection, order_id: uuid.UUID, code: str) -> OtpCheck:
    row = repo.otp(conn, order_id, lock=True)
    if row is None:
        raise Conflict("No delivery code has been issued for this order")
    if row.failed_attempts >= d.OTP_MAX_ATTEMPTS:
        raise Conflict("The delivery code is locked after three wrong attempts; contact the manager")
    expected = d.delivery_code(get_settings().otp_pepper.get_secret_value(), str(order_id), row.nonce)
    ok = d.codes_match(expected, code)
    failed = repo.record_otp_attempt(conn, order_id, success=ok)
    return OtpCheck(ok, max(d.OTP_MAX_ATTEMPTS - failed, 0))


def live_assignment(conn: Connection, order_id: uuid.UUID) -> AssignmentRow | None:
    """The order's live offer or assignment, row-locked."""
    return repo.live_for_order(conn, order_id, lock=True)


def customer_unavailable_since(conn: Connection, order_id: uuid.UUID) -> datetime | None:
    row = repo.work_order(conn, order_id)
    return row.customer_unavailable_since if row else None


def gps_summary(conn: Connection, assignment_id: uuid.UUID) -> dict[str, object]:
    return repo.gps_summary(conn, assignment_id)


def latest_point(conn: Connection, order_id: uuid.UUID) -> PointRow | None:
    return repo.latest_point(conn, order_id)


def manager_role_for(principal: Principal, region_id: uuid.UUID) -> str:
    return _manager_role(principal, region_id)


def emit_for(conn: Connection, a: AssignmentRow, event_type: str, data: dict[str, object]) -> None:
    _event(conn, a, event_type, data)


# ---------------------------------------------------------------- the agent's own work (#7 §3–§4)
@dataclass(frozen=True)
class MyWork:
    availability: str
    availability_changed_at: datetime | None
    assignment: AssignmentRow | None
    order: WorkOrder | None
    offer_seconds_left: int | None
    wait_minutes: int
    stale_seconds: int
    interval_seconds: tuple[int, int]


def my_work(principal: Principal) -> MyWork:
    region = _agent_region(principal)
    with get_engine().connect() as conn:
        status, changed_at = repo.availability(conn, principal.user_id)
        a = repo.live_for_agent(conn, principal.user_id)
        order = repo.work_order(conn, a.order_id) if a else None
        left = None
        if a is not None and a.status == A.OFFERED:
            timeout = int(config_value(conn, "AGENT_ASSIGNMENT_RESPONSE_TIMEOUT", region_id=region))
            left = max(int(timeout - repo.seconds_since_offer(conn, a.id)), 0)
        return MyWork(
            availability=status,
            availability_changed_at=changed_at,
            assignment=a,
            order=order,
            offer_seconds_left=left,
            wait_minutes=int(config_value(conn, "CUSTOMER_UNAVAILABLE_WAIT", region_id=region)),
            stale_seconds=int(config_value(conn, "GPS_STALE_SECONDS")),
            interval_seconds=(
                int(config_value(conn, "GPS_UPDATE_INTERVAL_MIN", region_id=region)),
                int(config_value(conn, "GPS_UPDATE_INTERVAL_MAX", region_id=region)),
            ),
        )


def _expire_open_offer(conn: Connection, agent: uuid.UUID) -> None:
    a = repo.live_for_agent(conn, agent, lock=True)
    if a is not None and a.status == A.OFFERED:
        repo.set_status(conn, a.id, A.EXPIRED.value)
        repo.offer_next(conn, a.order_id)


def set_availability(principal: Principal, online: bool) -> MyWork:
    """DL-01, DDR-113 (4): going offline expires an open offer; never with an accepted delivery."""
    _agent_region(principal)
    with get_engine().begin() as conn:
        a = repo.live_for_agent(conn, principal.user_id, lock=True)
        set_actor(
            conn,
            role="DELIVERY_AGENT",
            user_id=principal.user_id,
            reason=None if online else "Agent went offline",
            correlation_id=current_request_id(),
        )
        if not online:
            if a is not None and a.status != A.OFFERED:
                raise Conflict("Finish the active delivery or contact the manager before going offline")
            _expire_open_offer(conn, principal.user_id)
        repo.set_availability(
            conn, principal.user_id, "ONLINE" if online else "OFFLINE", principal.user_id, None
        )
    if online:
        # Offer any order that is waiting for an agent (the worker sweep would do it within 10 s).
        with get_engine().begin() as conn:
            set_actor(conn, role="SYSTEM", user_id=None, reason=None, correlation_id=current_request_id())
            for order_id in repo.waiting_orders(conn, _agent_region(principal)):
                if repo.offer_next(conn, order_id) is not None:
                    break
    return my_work(principal)


def respond(principal: Principal, assignment_id: uuid.UUID, *, accept: bool, reason: str | None) -> MyWork:
    """DL-04: accept within the timeout, or reject with a reason; both return the order to the pool."""
    region = _agent_region(principal)
    text_reason = None if accept else _reason(reason)
    expired = False
    with get_engine().begin() as conn:
        a = repo.find(conn, assignment_id, lock=True)
        if a is None or a.agent_user_id != principal.user_id or a.region_id != region:
            raise NotFound
        if a.status != A.OFFERED:
            raise Conflict(f"This offer is {a.status.lower()}")
        timeout = int(config_value(conn, "AGENT_ASSIGNMENT_RESPONSE_TIMEOUT", region_id=region))
        late = repo.seconds_since_offer(conn, a.id) > timeout
        set_actor(
            conn,
            role="SYSTEM" if late else "DELIVERY_AGENT",
            user_id=None if late else principal.user_id,
            reason="Offer response timeout (DL-04)" if late else text_reason,
            correlation_id=current_request_id(),
        )
        if late:
            repo.set_status(conn, a.id, A.EXPIRED.value)
            repo.offer_next(conn, a.order_id)
            expired = True
        elif accept:
            repo.set_status(conn, a.id, A.ACCEPTED.value)
            _event(conn, a, "delivery.assigned", {"agent_user_id": str(principal.user_id)})
        else:
            repo.set_status(conn, a.id, A.REJECTED.value)
            repo.offer_next(conn, a.order_id)
    if expired:
        raise Conflict("This offer expired after 60 seconds and went back to the pool")
    return my_work(principal)


def reveal_phone(principal: Principal, order_id: uuid.UUID) -> str:
    """DL-08, DDR-113 (14): the full number, only for the agent's own accepted delivery; audited."""
    with get_engine().begin() as conn:
        a = held_by(conn, principal, order_id)
        order = repo.work_order(conn, order_id)
        if order is None:  # pragma: no cover - the assignment exists
            raise NotFound
        write_event(
            conn,
            action="delivery.customer_phone.revealed",
            actor_user_id=principal.user_id,
            actor_role="DELIVERY_AGENT",
            target_type="order",
            target_id=str(order_id),
            region_id=a.region_id,
            kitchen_id=a.kitchen_id,
            correlation_id=current_request_id(),
        )
        return order.customer_mobile


# ---------------------------------------------------------------- GPS (DL-G1–DL-G5; DDR-52, DDR-113 (8), (9))
@dataclass(frozen=True)
class Point:
    lat: float
    lng: float
    accuracy_m: Decimal | None
    recorded_at: datetime
    source: str


@dataclass(frozen=True)
class IngestResult:
    accepted: int
    refused: dict[str, int]


def ingest(principal: Principal, points: list[Point]) -> IngestResult:
    """Only the agent holding the accepted assignment may send; stale, future and out-of-order points are
    refused, never stored. Points are checked in time order, so a re-sent buffer is safe."""
    if len(points) > d.GPS_BATCH_MAX:
        raise Invalid(f"At most {d.GPS_BATCH_MAX} points per request")
    _agent_region(principal)
    with get_engine().begin() as conn:
        a = repo.live_for_agent(conn, principal.user_id, lock=True)
        if a is None or a.status not in (A.ACCEPTED, A.FAILURE_REQUESTED):
            raise Conflict("Location is recorded only while you hold an accepted delivery")
        stale = int(config_value(conn, "GPS_STALE_SECONDS"))
        now = repo.now(conn)
        last = repo.last_recorded_at(conn, a.id)
        refused: dict[str, int] = {}
        accepted = 0
        for p in sorted(points, key=lambda x: x.recorded_at):
            why = d.point_refusal(p.recorded_at, now=now, last=last, stale_seconds=stale)
            if why is None and not (-90 <= p.lat <= 90 and -180 <= p.lng <= 180):
                why = "invalid"
            if why:
                refused[why] = refused.get(why, 0) + 1
                continue
            repo.insert_point(
                conn,
                a,
                lat=p.lat,
                lng=p.lng,
                accuracy_m=p.accuracy_m,
                recorded_at=p.recorded_at,
                source=p.source,
            )
            last = p.recorded_at
            accepted += 1
        return IngestResult(accepted, refused)


# ---------------------------------------------------------------- manager actions (DDR-113 (5); UI Task 10)
def manager_assign(
    principal: Principal, order_id: uuid.UUID, agent_id: uuid.UUID, reason: str
) -> LiveAssignment:
    """DL-02, DL-07: assign an order before pickup to an online agent; any live offer or assignment is
    revoked first (the old agent loses access at once)."""
    text_reason = _reason(reason)
    with get_engine().begin() as conn:
        a = repo.live_for_order(conn, order_id, lock=True)
        order = repo.work_order(conn, order_id)
        try:
            region = a.region_id if a else repo.order_region(conn, order_id)
        except LookupError:
            raise NotFound from None
        role = _manager_role(principal, region)
        if order is None or order.fulfilment_status not in ("ACCEPTED", "PREPARING", "READY_FOR_PICKUP"):
            raise Conflict("Only orders the kitchen still holds can be assigned")
        if not repo.is_agent_in_region(conn, agent_id, region):
            raise Invalid("Choose an active delivery agent of this order's region")
        if repo.availability(conn, agent_id)[0] != "ONLINE":
            raise Conflict("The agent is offline")
        set_actor(
            conn,
            role=role,
            user_id=principal.user_id,
            reason=text_reason,
            correlation_id=current_request_id(),
        )
        if a is not None:
            if a.agent_user_id == agent_id and a.status == A.ACCEPTED:
                raise Conflict("The order is already assigned to this agent")
            if not d.can_transition(A(a.status), A.REVOKED):
                raise Conflict("A failure request is open; decide it first")
            repo.set_status(conn, a.id, A.REVOKED.value)
        try:
            with conn.begin_nested():
                repo.insert_offer(conn, order_id, agent_id)
        except IntegrityError:
            raise Conflict("The agent already has an offer or a delivery") from None
        write_event(
            conn,
            action="delivery.assignment.overridden",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_type="order",
            target_id=str(order_id),
            region_id=region,
            reason=text_reason,
            correlation_id=current_request_id(),
            after={"agent_user_id": str(agent_id), "revoked": str(a.agent_user_id) if a else None},
        )
        live_now = repo.live(conn, [order_id]).get(order_id)
    if live_now is None:  # pragma: no cover - inserted above
        raise NotFound
    return live_now


def force_offline(principal: Principal, agent_id: uuid.UUID, reason: str) -> None:
    """DL-06: only when the agent holds no accepted delivery; an open offer expires and is re-offered."""
    text_reason = _reason(reason)
    with get_engine().begin() as conn:
        region = repo.agent_region(conn, agent_id)
        if region is None:
            raise NotFound
        role = _manager_role(principal, region)
        a = repo.live_for_agent(conn, agent_id, lock=True)
        if a is not None and a.status != A.OFFERED:
            raise Conflict("Reassign or resolve the agent's active delivery first")
        set_actor(
            conn,
            role=role,
            user_id=principal.user_id,
            reason=text_reason,
            correlation_id=current_request_id(),
        )
        _expire_open_offer(conn, agent_id)
        repo.set_availability(conn, agent_id, "OFFLINE", principal.user_id, text_reason)
        write_event(
            conn,
            action="delivery.agent.forced_offline",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_type="user",
            target_id=str(agent_id),
            region_id=region,
            reason=text_reason,
            correlation_id=current_request_id(),
        )


def agents(principal: Principal) -> list[repo.AgentRow]:
    """Online/offline agents and their live work, within the manager's scope (#7 §10)."""
    if can(principal, P.MGMT_AGENTS_ASSIGN):
        regions = None
    else:
        regions = [
            g.region_id
            for g in principal.grants
            if g.region_id and can(principal, P.MGMT_AGENTS_ASSIGN, region_id=g.region_id)
        ]
        if not regions:
            raise Forbidden
    with get_engine().connect() as conn:
        return repo.agents(conn, regions)


# ---------------------------------------------------------------- profile and history (#7 §9; DDR-113 (15))
def history(principal: Principal) -> list[repo.HistoryRow]:
    _agent_region(principal)
    with get_engine().connect() as conn:
        return repo.history(conn, principal.user_id, HISTORY_DAYS)


def rename(principal: Principal, name: str) -> str:
    _agent_region(principal)
    cleaned = " ".join(name.split())
    if not 1 <= len(cleaned) <= NAME_MAX:
        raise Invalid(f"Enter a name of 1 to {NAME_MAX} characters")
    with get_engine().begin() as conn:
        repo.set_display_name(conn, principal.user_id, cleaned)
    return cleaned
