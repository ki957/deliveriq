"""Customer order routes: /api/v1/orders/* (Matrix §7; DDR-109). Checkout UI is Task 6."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.orders import service
from app.modules.orders.schemas import CancelIn, OrderCreateIn, OrderItemOut, OrderOut, PaymentOut, SimulateIn

router = APIRouter(prefix="/api/v1/orders", tags=["orders"], dependencies=[Depends(csrf_protect)])

IdempotencyKey = Annotated[
    uuid.UUID,
    Header(alias="Idempotency-Key", description="Client-generated UUID; a repeat returns the original order"),
]


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Order not found") from None
    except service.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except service.Unavailable:
        raise HTTPException(status_code=422, detail="A dish in this order is not available") from None


def _out(view: service.OrderView) -> OrderOut:
    o = view.order
    return OrderOut(
        id=o.id,
        fulfilment_status=o.fulfilment_status,  # type: ignore[arg-type]
        status_label=view.labels.customer,
        agent_assigned=view.labels.agent_assigned,
        is_test_fixture=o.is_test_fixture,
        special_instructions=o.special_instructions,
        food_subtotal_paise=o.food_subtotal_paise,
        delivery_fee_paise=o.delivery_fee_paise,
        payable_paise=o.payable_paise,
        placed_at=o.placed_at,
        items=[OrderItemOut.model_validate(i, from_attributes=True) for i in view.items],
        payment=PaymentOut.model_validate(view.payment, from_attributes=True) if view.payment else None,
    )


@router.post(
    "", status_code=201, response_model=OrderOut, responses={200: {"description": "Repeat of a request"}}
)
def place_order(
    body: OrderCreateIn, key: IdempotencyKey, principal: CurrentPrincipal, response: Response
) -> OrderOut:
    view, created = _call(
        lambda: service.place(
            principal,
            idempotency_key=str(key),
            lines=[(line.menu_item_id, line.quantity) for line in body.lines],
            method=body.payment_method,
            special_instructions=body.special_instructions,
        )
    )
    if not created:
        response.status_code = 200
    return _out(view)


@router.get("", response_model=list[OrderOut])
def my_orders(principal: CurrentPrincipal) -> list[OrderOut]:
    return [_out(v) for v in _call(lambda: service.list_mine(principal))]


@router.get("/{order_id}", response_model=OrderOut)
def order_detail(order_id: uuid.UUID, principal: CurrentPrincipal) -> OrderOut:
    return _out(_call(lambda: service.get(principal, order_id)))


@router.post("/{order_id}/payment/simulate", response_model=OrderOut)
def simulate_payment(order_id: uuid.UUID, body: SimulateIn, principal: CurrentPrincipal) -> OrderOut:
    """Payment simulator: no real money moves. SUCCESS sends the order to the kitchen; FAILED or
    TIMEOUT cancels it (DDR-109)."""
    return _out(_call(lambda: service.simulate_payment(principal, order_id, body.outcome)))


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: uuid.UUID, principal: CurrentPrincipal, body: CancelIn | None = None) -> OrderOut:
    return _out(_call(lambda: service.cancel(principal, order_id, body.reason if body else None)))
