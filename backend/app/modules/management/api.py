"""Management routes: /api/v1/management/* (RM assigned regions, CA all; #10; DDR-114).

Operational actions reuse the owning routes (kitchen settings, kitchen reject, delivery manage, menu
availability); this router serves the scoped read models, staff access and CSV exports.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.permissions import Role
from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.management import service
from app.modules.management.schemas import (
    AuditOut,
    AuditPageOut,
    DeliveryOut,
    InventoryOut,
    KitchenStatusOut,
    ManagedIntakeOut,
    ManagedItemOut,
    ManagedStockOut,
    MovementOut,
    OrderDetailOut,
    OrderPageOut,
    OrderRowOut,
    OverviewOut,
    RefundOut,
    RefundsOut,
    RegionOut,
    StaffIn,
    StaffOut,
    StaffReasonIn,
    StatusIn,
    TimelineOut,
)

router = APIRouter(prefix="/api/v1/management", tags=["management"], dependencies=[Depends(csrf_protect)])
Page = Annotated[int, Query(ge=1, le=1000)]


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except service.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except service.Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _kitchen_out(k: service.KitchenStatus) -> KitchenStatusOut:
    i = k.intake
    return KitchenStatusOut(
        id=k.kitchen.id,
        code=k.kitchen.code,
        name=k.kitchen.name,
        region_id=k.kitchen.region_id,
        region_name=k.kitchen.region_name,
        mode=k.kitchen.mode,
        intake=ManagedIntakeOut(
            mode=i.mode.value,
            capacity=i.capacity,
            active_orders=i.active,
            accepting=i.accepting,
            refusal=i.refusal,
        )
        if i
        else None,
    )


def _order_out(r: service.OrderListRow) -> OrderRowOut:
    return OrderRowOut(
        id=r.id,
        placed_at=r.placed_at,
        fulfilment_status=r.fulfilment_status,
        status_label=service.management_label(r.fulfilment_status),
        is_test_fixture=r.is_test_fixture,
        kitchen_name=r.kitchen_name,
        payable_paise=r.payable_paise,
        payment_method=r.payment_method,
        payment_status=r.payment_status,
        agent_name=r.agent_name,
        assignment_status=r.assignment_status,
        delivery_exception_open=r.delivery_exception_open,
    )


@router.get("/overview", response_model=OverviewOut)
def overview(principal: CurrentPrincipal) -> OverviewOut:
    """Counts from persisted records only (DDR-114 (10)); KPIs wait for Task 13."""
    o = _call(lambda: service.overview(principal))
    p = o.pending
    return OverviewOut(
        orders_by_status=o.orders_by_status,
        overdue_incoming=o.overdue_incoming,
        availability_requests=p["availability_requests"],
        failure_requests=p["failure_requests"],
        delivery_exceptions=p["delivery_exceptions"],
        online_agents=p["online_agents"],
        active_deliveries=p["active_deliveries"],
        kitchens=[_kitchen_out(k) for k in o.kitchens],
    )


@router.get("/regions", response_model=list[RegionOut])
def regions(principal: CurrentPrincipal) -> list[RegionOut]:
    return [RegionOut(id=i, code=c, name=n) for i, c, n in _call(lambda: service.region_list(principal))]


@router.get("/kitchens", response_model=list[KitchenStatusOut])
def kitchens(principal: CurrentPrincipal) -> list[KitchenStatusOut]:
    return [_kitchen_out(k) for k in _call(lambda: service.kitchen_list(principal))]


def _order_filters(
    status: str | None,
    kitchen_id: uuid.UUID | None,
    agent_id: uuid.UUID | None,
    exception: bool | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> dict[str, object]:
    return {
        "status": status,
        "kitchen_id": kitchen_id,
        "agent_id": agent_id,
        "exception": exception,
        "date_from": date_from,
        "date_to": date_to,
    }


@router.get("/orders", response_model=OrderPageOut)
def orders(
    principal: CurrentPrincipal,
    page: Page = 1,
    status: Annotated[str | None, Query(max_length=40)] = None,
    kitchen_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    exception: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> OrderPageOut:
    """Orders by status, date (≤ 31 days), kitchen, agent and exception flag (#10 §7)."""
    f = _order_filters(status, kitchen_id, agent_id, exception, date_from, date_to)
    rows, total = _call(lambda: service.order_list(principal, page=page, **f))
    return OrderPageOut(
        rows=[_order_out(r) for r in rows], total=total, page=page, page_size=service.PAGE_SIZE
    )


@router.get("/orders.csv", response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def orders_csv(
    principal: CurrentPrincipal,
    status: Annotated[str | None, Query(max_length=40)] = None,
    kitchen_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    exception: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Response:
    """The current filtered view as CSV (≤ 5,000 rows), same scope as the screen; the export is audited."""
    f = _order_filters(status, kitchen_id, agent_id, exception, date_from, date_to)
    body = _call(lambda: service.orders_csv(principal, **f))
    return Response(
        body, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="orders.csv"'}
    )


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
def order_detail(order_id: uuid.UUID, principal: CurrentPrincipal) -> OrderDetailOut:
    """Fulfilment, item, payment and assignment timelines with actor and reason."""
    d = _call(lambda: service.order_detail(principal, order_id))
    return OrderDetailOut(
        order=_order_out(d.head),
        items=[ManagedItemOut(name=n, quantity=q) for n, q in d.items],
        timeline=[TimelineOut.model_validate(t, from_attributes=True) for t in d.timeline],
    )


@router.get("/deliveries", response_model=list[DeliveryOut])
def deliveries(principal: CurrentPrincipal) -> list[DeliveryOut]:
    """Live offers and deliveries with the latest position (Simulated labelled; DDR-114 (11))."""
    return [
        DeliveryOut(
            order_id=r.order_id,
            assignment_id=r.assignment_id,
            assignment_status=r.assignment_status,
            fulfilment_status=r.fulfilment_status,
            is_test_fixture=r.is_test_fixture,
            agent_id=r.agent_id,
            agent_name=r.agent_name,
            delivery_address=r.delivery_address,
            delivery_exception_open=r.delivery_exception_open,
            lat=r.lat,
            lng=r.lng,
            recorded_at=r.recorded_at,
            simulated=None if r.source is None else r.source == "SIMULATED",
        )
        for r in _call(lambda: service.delivery_board(principal))
    ]


@router.get("/refunds", response_model=RefundsOut)
def refunds(principal: CurrentPrincipal) -> RefundsOut:
    """Refund records (actor, amount, reason, order, outcome; MG-05) and pending decisions (DDR-114 (6))."""
    rows = _call(lambda: service.refund_list(principal))
    return RefundsOut(rows=[RefundOut.model_validate(r, from_attributes=True) for r in rows])


@router.get("/kitchens/{kitchen_id}/inventory", response_model=InventoryOut)
def inventory(kitchen_id: uuid.UUID, principal: CurrentPrincipal) -> InventoryOut:
    """Read-only stock, reservations, thresholds and the latest 100 ledger rows (DDR-114 (12))."""
    inv = _call(lambda: service.inventory(principal, kitchen_id))
    return InventoryOut(
        kitchen_id=inv.kitchen_id,
        stock=[ManagedStockOut(**{**s.__dict__, "available": s.on_hand - s.reserved}) for s in inv.stock],
        movements=[MovementOut.model_validate(m, from_attributes=True) for m in inv.movements],
    )


def _audit_filters(
    action: str | None,
    target_type: str | None,
    actor_role: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> dict[str, object]:
    return {
        "action": action,
        "target_type": target_type,
        "actor_role": actor_role,
        "date_from": date_from,
        "date_to": date_to,
    }


@router.get("/audit", response_model=AuditPageOut)
def audit(
    principal: CurrentPrincipal,
    page: Page = 1,
    action: Annotated[str | None, Query(max_length=80)] = None,
    target_type: Annotated[str | None, Query(max_length=60)] = None,
    actor_role: Annotated[str | None, Query(max_length=40)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditPageOut:
    """RM: events of assigned regions. CA: all events (#10 §12; DDR-114 (7))."""
    f = _audit_filters(action, target_type, actor_role, date_from, date_to)
    rows, total = _call(lambda: service.audit_list(principal, page=page, **f))
    return AuditPageOut(
        rows=[AuditOut.model_validate(r, from_attributes=True) for r in rows],
        total=total,
        page=page,
        page_size=service.PAGE_SIZE,
    )


@router.get("/audit.csv", response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def audit_csv(
    principal: CurrentPrincipal,
    action: Annotated[str | None, Query(max_length=80)] = None,
    target_type: Annotated[str | None, Query(max_length=60)] = None,
    actor_role: Annotated[str | None, Query(max_length=40)] = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Response:
    f = _audit_filters(action, target_type, actor_role, date_from, date_to)
    body = _call(lambda: service.audit_csv(principal, **f))
    return Response(
        body, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="audit.csv"'}
    )


# ---------------------------------------------------------------- staff (#10 §4; DDR-114 (3)–(5))
def _staff_out(r: service.StaffGrantRow) -> StaffOut:
    masked = r.mobile[:3] + "*" * max(len(r.mobile) - 5, 0) + r.mobile[-2:]
    return StaffOut(
        assignment_id=r.assignment_id,
        user_id=r.user_id,
        display_name=r.display_name,
        mobile_masked=masked,
        user_status=r.user_status,
        role=r.role,
        region_id=r.region_id,
        kitchen_id=r.kitchen_id,
        granted_at=r.granted_at,
    )


@router.get("/staff", response_model=list[StaffOut])
def staff(principal: CurrentPrincipal) -> list[StaffOut]:
    """Staff the caller may manage (RM: KM, KS, agents of assigned regions; CA: all staff)."""
    return [_staff_out(r) for r in _call(lambda: service.staff_list(principal))]


@router.post("/staff", status_code=201, response_model=StaffOut)
def add_staff(body: StaffIn, principal: CurrentPrincipal) -> StaffOut:
    """Grant a staff role (creating the account if the mobile is new); the person signs in by OTP."""
    row = _call(
        lambda: service.add_staff(
            principal,
            display_name=body.display_name,
            mobile=body.mobile,
            role=Role(body.role),
            region_id=body.region_id,
            kitchen_id=body.kitchen_id,
            reason=body.reason,
        )
    )
    return _staff_out(row)


@router.post("/staff/roles/{assignment_id}/remove", status_code=204)
def remove_role(assignment_id: uuid.UUID, body: StaffReasonIn, principal: CurrentPrincipal) -> Response:
    """Remove a role; blocked while an agent holds a delivery; ends the person's sessions at once."""
    _call(lambda: service.remove_role(principal, assignment_id, body.reason))
    return Response(status_code=204)


@router.put("/staff/{user_id}/status", status_code=204)
def set_status(user_id: uuid.UUID, body: StatusIn, principal: CurrentPrincipal) -> Response:
    """Deactivate (blocked while an agent holds a delivery; ends sessions) or reactivate, with a reason."""
    _call(lambda: service.set_active(principal, user_id, active=body.active, reason=body.reason))
    return Response(status_code=204)
