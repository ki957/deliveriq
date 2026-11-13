"""Delivery routes: /api/v1/delivery (agent) and /api/v1/delivery/manage (RM, CA; UI in Task 10).

Status changes go through the orders service (pickup, delivered, failed); assignment-only actions through
the delivery service (DDR-16, DDR-17, DDR-113).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.modules.delivery import domain as d
from app.modules.delivery import service
from app.modules.delivery.schemas import (
    AgentOut,
    AssignIn,
    AssignmentOut,
    AvailabilityIn,
    CodeIn,
    CodIn,
    DecisionIn,
    FailureIn,
    HistoryOut,
    IngestOut,
    LiveAssignmentOut,
    MyWorkOut,
    NameIn,
    NameOut,
    OptionalReasonIn,
    PhoneOut,
    Place,
    PointsIn,
    ReasonIn,
    RespondIn,
    UnavailableOut,
    WorkItemOut,
    WorkOrderOut,
)
from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.orders import service as orders
from app.modules.orders.api import order_out
from app.modules.orders.domain import Fulfilment, display
from app.modules.orders.schemas import OrderOut

router = APIRouter(prefix="/api/v1/delivery", tags=["delivery"], dependencies=[Depends(csrf_protect)])
manage_router = APIRouter(
    prefix="/api/v1/delivery/manage", tags=["delivery"], dependencies=[Depends(csrf_protect)]
)


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except (service.Forbidden, orders.Forbidden):
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except (service.NotFound, orders.NotFound):
        raise HTTPException(status_code=404, detail="Not found") from None
    except (service.Conflict, orders.Conflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except (service.Invalid, orders.InvalidInput, orders.WrongCode) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _work_out(w: service.MyWork) -> MyWorkOut:
    a, o = w.assignment, w.order
    order = None
    if o is not None and a is not None:
        accepted = a.status != d.Assignment.OFFERED
        attempts = d.OTP_MAX_ATTEMPTS - o.otp_failed_attempts if o.otp_failed_attempts is not None else None
        order = WorkOrderOut(
            order_id=o.order_id,
            items=[WorkItemOut(name=n, quantity=q) for n, q in w.items],
            fulfilment_status=o.fulfilment_status,
            status_label=display(Fulfilment(o.fulfilment_status), accepted).delivery or "Go to kitchen",
            is_test_fixture=o.is_test_fixture,
            special_instructions=o.special_instructions if accepted else None,
            delivery_address=o.delivery_address if accepted else None,
            destination=Place(lat=o.lat, lng=o.lng)
            if accepted and o.lat is not None and o.lng is not None
            else None,
            kitchen_name=o.kitchen_name,
            kitchen=Place(lat=o.kitchen_lat, lng=o.kitchen_lng),
            kitchen_location_is_synthetic=o.kitchen_location_is_synthetic,
            customer_phone_masked=d.mask_phone(o.customer_mobile),
            payment_method=o.payment_method,
            payment_status=o.payment_status,
            payable_paise=o.payable_paise,
            customer_unavailable_since=o.customer_unavailable_since,
            delivery_exception_open=o.delivery_exception_open,
            code_attempts_left=attempts if not o.otp_verified else None,
        )
    return MyWorkOut(
        availability=w.availability,  # type: ignore[arg-type]
        availability_changed_at=w.availability_changed_at,
        assignment=AssignmentOut(
            id=a.id, status=a.status, offered_at=a.offered_at, offer_seconds_left=w.offer_seconds_left
        )
        if a
        else None,
        order=order,
        customer_unavailable_wait_minutes=w.wait_minutes,
        gps_interval_seconds=w.interval_seconds,
        gps_stale_seconds=w.stale_seconds,
    )


# ---------------------------------------------------------------- agent
@router.get("/me", response_model=MyWorkOut)
def my_work(principal: CurrentPrincipal) -> MyWorkOut:
    """Availability and the current offer or delivery (DL-01, DL-08)."""
    return _work_out(_call(lambda: service.my_work(principal)))


@router.put("/me/availability", response_model=MyWorkOut)
def set_availability(body: AvailabilityIn, principal: CurrentPrincipal) -> MyWorkOut:
    """Go online (receive offers) or offline (an open offer expires; not with an accepted delivery)."""
    return _work_out(_call(lambda: service.set_availability(principal, body.online)))


@router.post("/assignments/{assignment_id}/respond", response_model=MyWorkOut)
def respond(assignment_id: uuid.UUID, body: RespondIn, principal: CurrentPrincipal) -> MyWorkOut:
    """Accept within 60 s, or reject with a reason (DL-04)."""
    return _work_out(
        _call(lambda: service.respond(principal, assignment_id, accept=body.accept, reason=body.reason))
    )


@router.get("/orders/{order_id}/customer-phone", response_model=PhoneOut)
def customer_phone(order_id: uuid.UUID, principal: CurrentPrincipal) -> PhoneOut:
    """The full number for the agent's own accepted delivery only; every reveal is audited (DL-08)."""
    return PhoneOut(phone=_call(lambda: service.reveal_phone(principal, order_id)))


@router.post("/orders/{order_id}/pickup", response_model=OrderOut)
def pickup(order_id: uuid.UUID, principal: CurrentPrincipal) -> OrderOut:
    """Validated pickup (DL-09): blocked until Ready; then Out for delivery and the customer's code."""
    return order_out(_call(lambda: orders.record_pickup(principal, order_id)))


@router.post(
    "/orders/{order_id}/deliver", response_model=OrderOut, responses={422: {"description": "Wrong code"}}
)
def deliver(order_id: uuid.UUID, body: CodeIn, principal: CurrentPrincipal) -> OrderOut:
    """The customer's six-digit code, verified by the backend; three wrong codes escalate (DL-11)."""
    return order_out(_call(lambda: orders.deliver(principal, order_id, body.code)))


@router.post("/orders/{order_id}/cod", response_model=OrderOut)
def cod(order_id: uuid.UUID, body: CodIn, principal: CurrentPrincipal) -> OrderOut:
    """Simulated cash on delivery: collected, or a mismatch with a reason (DL-15)."""
    return order_out(
        _call(
            lambda: orders.record_cod_collection(
                principal, order_id, collected=body.collected, reason=body.reason
            )
        )
    )


@router.post("/orders/{order_id}/customer-unavailable", response_model=UnavailableOut)
def customer_unavailable(order_id: uuid.UUID, principal: CurrentPrincipal) -> UnavailableOut:
    """Start the wait (DDR-14); afterwards the agent may contact the manager without a reason."""
    since = _call(lambda: orders.customer_unavailable(principal, order_id))
    wait = _call(lambda: service.my_work(principal)).wait_minutes
    return UnavailableOut(since=since, wait_minutes=wait)


@router.post("/orders/{order_id}/contact-manager", response_model=OrderOut)
def contact_manager(order_id: uuid.UUID, body: OptionalReasonIn, principal: CurrentPrincipal) -> OrderOut:
    """After the customer-unavailable wait, or at any time with a reason (emergency, #7 §7)."""
    return order_out(_call(lambda: orders.contact_manager(principal, order_id, body.reason)))


@router.post("/orders/{order_id}/failure-request", response_model=OrderOut)
def failure_request(order_id: uuid.UUID, body: FailureIn, principal: CurrentPrincipal) -> OrderOut:
    """Customer refused, or delivery failed: a reason is required; the manager decides (DA-18)."""
    return order_out(
        _call(lambda: orders.request_failure(principal, order_id, refused=body.refused, reason=body.reason))
    )


@router.post("/locations", response_model=IngestOut)
def locations(body: PointsIn, principal: CurrentPrincipal) -> IngestOut:
    """GPS points while holding an accepted delivery (DDR-52): stale, future or out-of-order points are
    refused and counted, never stored. REAL or SIMULATED is recorded per point."""
    points = [service.Point(p.lat, p.lng, p.accuracy_m, p.recorded_at, p.source) for p in body.points]
    result = _call(lambda: service.ingest(principal, points))
    return IngestOut(accepted=result.accepted, refused=result.refused)


@router.get("/history", response_model=list[HistoryOut])
def history(principal: CurrentPrincipal) -> list[HistoryOut]:
    """The agent's own deliveries of the last 30 days (#7 §9)."""
    rows = _call(lambda: service.history(principal))
    return [
        HistoryOut(
            order_id=r.order_id,
            assignment_status=r.status,
            fulfilment_status=r.fulfilment_status,
            is_test_fixture=r.is_test_fixture,
            offered_at=r.offered_at,
            picked_up_at=r.picked_up_at,
            delivered_at=r.delivered_at,
            duration_minutes=int((r.delivered_at - r.picked_up_at).total_seconds() // 60)
            if r.picked_up_at and r.delivered_at
            else None,
        )
        for r in rows
    ]


@router.put("/me/name", response_model=NameOut)
def rename(body: NameIn, principal: CurrentPrincipal) -> NameOut:
    """The agent edits the display name (#7 §9); the mobile number changes only through recovery."""
    return NameOut(display_name=_call(lambda: service.rename(principal, body.display_name)))


# ---------------------------------------------------------------- manager (DDR-113 (5))
@manage_router.get("/agents", response_model=list[AgentOut])
def agents(principal: CurrentPrincipal) -> list[AgentOut]:
    rows = _call(lambda: service.agents(principal))
    return [
        AgentOut(
            id=r.id,
            name=r.name,
            availability=r.status,  # type: ignore[arg-type]
            availability_changed_at=r.changed_at,
            live_status=r.live_status,
            live_order_id=r.live_order_id,
        )
        for r in rows
    ]


@manage_router.post("/orders/{order_id}/assign", response_model=LiveAssignmentOut)
def assign(order_id: uuid.UUID, body: AssignIn, principal: CurrentPrincipal) -> LiveAssignmentOut:
    """Offer the order to a chosen online agent; any current offer or assignment is revoked (DL-02, DL-07)."""
    live = _call(lambda: service.manager_assign(principal, order_id, body.agent_user_id, body.reason))
    return LiveAssignmentOut(order_id=live.order_id, assignment_id=live.assignment_id, status=live.status,
                             agent_name=live.agent_name)  # fmt: skip


@manage_router.post("/agents/{agent_id}/force-offline", status_code=204)
def force_offline(agent_id: uuid.UUID, body: ReasonIn, principal: CurrentPrincipal) -> None:
    """Only when the agent holds no accepted delivery (DL-06)."""
    _call(lambda: service.force_offline(principal, agent_id, body.reason))


@manage_router.post("/orders/{order_id}/failure-decision", response_model=OrderOut)
def failure_decision(order_id: uuid.UUID, body: DecisionIn, principal: CurrentPrincipal) -> OrderOut:
    """Approve (Delivery failed) or reject (back to the agent) a failure request, with a reason (DA-18)."""
    return order_out(
        _call(lambda: orders.decide_failure(principal, order_id, approve=body.approve, reason=body.reason))
    )


@manage_router.post("/orders/{order_id}/code", response_model=OrderOut)
def reissue_code(order_id: uuid.UUID, body: ReasonIn, principal: CurrentPrincipal) -> OrderOut:
    """Issue a new delivery code after escalation (DDR-113 (6))."""
    return order_out(_call(lambda: orders.reissue_code(principal, order_id, body.reason)))
