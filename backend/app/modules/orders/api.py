"""Customer order and cart routes: /api/v1/orders/*, /api/v1/cart/* (Matrix §7; DDR-109, DDR-110)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from app.core.errors import error_body
from app.modules.customers.schemas import serviceability_out
from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.orders import service
from app.modules.orders.schemas import (
    BillOut,
    CancelIn,
    CartLineOut,
    CartOut,
    CartQuantityIn,
    KitchenAssignmentOut,
    KitchenIntakeOut,
    KitchenItemOut,
    KitchenItemStatusIn,
    KitchenOrderOut,
    KitchenQueueOut,
    KitchenRejectIn,
    LiveLocationOut,
    OrderCreateIn,
    OrderItemOut,
    OrderOut,
    PaymentOut,
    SimulateIn,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"], dependencies=[Depends(csrf_protect)])
cart_router = APIRouter(prefix="/api/v1/cart", tags=["cart"], dependencies=[Depends(csrf_protect)])
kitchen_router = APIRouter(
    prefix="/api/v1/kitchen/orders", tags=["kitchen"], dependencies=[Depends(csrf_protect)]
)

IdempotencyKey = Annotated[
    uuid.UUID,
    Header(alias="Idempotency-Key", description="Client-generated UUID; a repeat returns the original order"),
]
REFUSALS: dict[int | str, dict[str, Any]] = {
    422: {"description": "A checkout rule refused the order; `code` names the rule"},
    409: {"description": "A price changed (`price_changes`), a wrong step, or a reused Idempotency-Key"},
}


class _Refusal(Exception):
    def __init__(self, response: JSONResponse) -> None:
        self.response = response


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except service.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except service.InvalidInput as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except service.KitchenRefused as exc:
        raise _Refusal(
            JSONResponse({**error_body(exc.code, str(exc)), **exc.detail}, status_code=409)
        ) from None
    except service.MissingKitchenSetting as exc:
        raise HTTPException(status_code=409, detail=f"Kitchen setting {exc} is not configured") from None
    except service.CheckoutRefused as exc:
        raise _Refusal(
            JSONResponse({**error_body(exc.code, str(exc)), **exc.detail}, status_code=422)
        ) from None
    except service.PricesChanged as exc:
        changes = [
            {
                "menu_item_id": str(c.menu_item_id),
                "stated_price_paise": c.stated_price_paise,
                "current_price_paise": c.current_price_paise,
            }
            for c in exc.changes
        ]
        raise _Refusal(
            JSONResponse({**error_body("price_changed", str(exc)), "price_changes": changes}, status_code=409)
        ) from None


def _respond[T](fn: Callable[[], T]) -> T | JSONResponse:
    try:
        return _call(fn)
    except _Refusal as refusal:
        return refusal.response


def order_out(view: service.OrderView) -> OrderOut:
    """Shared with the delivery routes. Tracking fields are filled only on the customer's own view."""
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
        discount_paise=o.discount_paise,
        payable_paise=o.payable_paise,
        delivery_address=o.delivery_address,
        road_km_estimated=o.road_km_estimated,
        placed_at=o.placed_at,
        items=[OrderItemOut.model_validate(i, from_attributes=True) for i in view.items],
        payment=PaymentOut.model_validate(view.payment, from_attributes=True) if view.payment else None,
        delivery_code=view.delivery_code,
        live_location=LiveLocationOut(
            lat=view.location.lat,
            lng=view.location.lng,
            recorded_at=view.location.recorded_at,
            simulated=view.location.source == "SIMULATED",
        )
        if view.location
        else None,
    )


def _cart_out(view: service.CartView) -> CartOut:
    return CartOut(
        lines=[
            CartLineOut(
                menu_item_id=v.line.menu_item_id,
                name=v.line.name,
                quantity=v.line.quantity,
                is_test_fixture=v.line.is_test_fixture,
                available=v.available,
                cart_price_paise=v.line.unit_price_paise,
                protected_until=v.protected_until,
                charge_price_paise=v.charge_price_paise,
                price_changed=v.price_changed,
            )
            for v in view.lines
        ],
        bill=BillOut.model_validate(view.bill, from_attributes=True),
        coupon_code=view.coupon_code,
        coupon_error=view.coupon_error,
        serviceability=serviceability_out(view.kitchen, view.serviceability) if view.serviceability else None,
        address_error=view.address_error,
        blockers=view.blockers,
    )


# ---------------------------------------------------------------- orders
@router.post(
    "",
    status_code=201,
    response_model=OrderOut,
    responses={200: {"description": "Repeat of a request"}, **REFUSALS},
)
def place_order(
    body: OrderCreateIn, key: IdempotencyKey, principal: CurrentPrincipal, response: Response
) -> OrderOut | JSONResponse:
    result = _respond(
        lambda: service.place(
            principal,
            idempotency_key=str(key),
            lines=[service.Line(x.menu_item_id, x.quantity, x.unit_price_paise) for x in body.lines],
            method=body.payment_method,
            special_instructions=body.special_instructions,
            address_id=body.address_id,
            coupon_code=body.coupon_code,
        )
    )
    if isinstance(result, JSONResponse):
        return result
    view, created = result
    if not created:
        response.status_code = 200
    return order_out(view)


@router.get("", response_model=list[OrderOut])
def my_orders(principal: CurrentPrincipal) -> list[OrderOut]:
    return [order_out(v) for v in _call(lambda: service.list_mine(principal))]


@router.get("/{order_id}", response_model=OrderOut)
def order_detail(order_id: uuid.UUID, principal: CurrentPrincipal) -> OrderOut:
    return order_out(_call(lambda: service.get(principal, order_id)))


@router.post("/{order_id}/payment/simulate", response_model=OrderOut)
def simulate_payment(order_id: uuid.UUID, body: SimulateIn, principal: CurrentPrincipal) -> OrderOut:
    """Payment simulator: no real money moves. SUCCESS sends the order to the kitchen; FAILED or
    TIMEOUT cancels it (DDR-109)."""
    return order_out(_call(lambda: service.simulate_payment(principal, order_id, body.outcome)))


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: uuid.UUID, principal: CurrentPrincipal, body: CancelIn | None = None) -> OrderOut:
    return order_out(_call(lambda: service.cancel(principal, order_id, body.reason if body else None)))


# ---------------------------------------------------------------- cart (persisted for customers, CU-11)
@cart_router.get("", response_model=CartOut)
def get_cart(
    principal: CurrentPrincipal,
    address_id: uuid.UUID | None = None,
    coupon_code: Annotated[str | None, Query(max_length=20)] = None,
) -> CartOut:
    """The cart with a live quote: protected prices, the bill, serviceability and checkout blockers."""
    return _cart_out(_call(lambda: service.get_cart(principal, address_id, coupon_code)))


@cart_router.put("/items/{menu_item_id}", response_model=CartOut, responses={422: REFUSALS[422]})
def set_quantity(
    menu_item_id: uuid.UUID, body: CartQuantityIn, principal: CurrentPrincipal
) -> CartOut | JSONResponse:
    result = _respond(lambda: service.set_cart_quantity(principal, menu_item_id, body.quantity))
    return result if isinstance(result, JSONResponse) else _cart_out(result)


@cart_router.post(
    "/items/{menu_item_id}/accept-price", response_model=CartOut, responses={422: REFUSALS[422]}
)
def accept_price(menu_item_id: uuid.UUID, principal: CurrentPrincipal) -> CartOut | JSONResponse:
    """Explicit confirmation of a revised price (CU-13)."""
    result = _respond(lambda: service.accept_price(principal, menu_item_id))
    return result if isinstance(result, JSONResponse) else _cart_out(result)


@cart_router.delete("/items/{menu_item_id}", response_model=CartOut)
def remove_item(menu_item_id: uuid.UUID, principal: CurrentPrincipal) -> CartOut:
    return _cart_out(_call(lambda: service.remove_from_cart(principal, menu_item_id)))


@cart_router.post("/remove-unavailable", response_model=CartOut)
def remove_unavailable(principal: CurrentPrincipal) -> CartOut:
    """The customer confirms removal of dishes that became unavailable (CU-14)."""
    return _cart_out(_call(lambda: service.remove_unavailable(principal)))


@cart_router.delete("", status_code=204)
def clear(principal: CurrentPrincipal) -> Response:
    _call(lambda: service.clear_cart(principal))
    return Response(status_code=204)


# ---------------------------------------------------------------- kitchen (Task 8; KI-01–KI-07, DDR-111)
KITCHEN_REFUSALS: dict[int | str, dict[str, Any]] = {
    409: {"description": "Wrong step, or the kitchen cannot accept now (`code`: kitchen_paused, "
          "kitchen_at_capacity, recipe_not_active, stock_short with `shortages`)"},
}  # fmt: skip


def _kitchen_out(v: service.KitchenOrderView) -> KitchenOrderOut:
    o = v.order
    return KitchenOrderOut(
        id=o.id,
        fulfilment_status=o.fulfilment_status,  # type: ignore[arg-type]
        status_label=v.kitchen_label,
        is_test_fixture=o.is_test_fixture,
        special_instructions=o.special_instructions,
        payment_method=v.payment_method,  # type: ignore[arg-type]
        placed_at=o.placed_at,
        queued_at=v.queued_at,
        accepted_at=o.accepted_at,
        overdue=v.overdue,
        items=[KitchenItemOut.model_validate(i, from_attributes=True) for i in v.items],
        assignment=KitchenAssignmentOut(status=v.assignment.status, agent_name=v.assignment.agent_name)
        if v.assignment
        else None,
    )


@kitchen_router.get("", response_model=KitchenQueueOut)
def kitchen_queue(principal: CurrentPrincipal, kitchen_id: uuid.UUID | None = None) -> KitchenQueueOut:
    """Incoming orders and the FIFO queue by acceptance time (KI-01, KI-03). Poll; realtime is Task 11."""
    q = _call(lambda: service.kitchen_queue(principal, kitchen_id))
    return KitchenQueueOut(
        kitchen_id=q.kitchen.id,
        kitchen_name=q.kitchen.name,
        intake=KitchenIntakeOut(
            mode=q.intake.mode.value,
            capacity=q.intake.capacity,
            active_orders=q.intake.active,
            accepting=q.intake.accepting,
            refusal=q.intake.refusal,
        ),
        acceptance_timeout_minutes=q.acceptance_timeout_minutes,
        incoming=[_kitchen_out(v) for v in q.incoming],
        held=[_kitchen_out(v) for v in q.held],
        can_process=q.can_process,
        can_reject_accepted=q.can_reject_accepted,
    )


def _kitchen_respond(fn: Callable[[], service.KitchenOrderView]) -> KitchenOrderOut | JSONResponse:
    result = _respond(fn)
    return result if isinstance(result, JSONResponse) else _kitchen_out(result)


@kitchen_router.post("/{order_id}/accept", response_model=KitchenOrderOut, responses=KITCHEN_REFUSALS)
def kitchen_accept(order_id: uuid.UUID, principal: CurrentPrincipal) -> KitchenOrderOut | JSONResponse:
    """Accept: capacity, ACTIVE recipe pin, all-or-nothing stock reservation, agent offer (DDR-51)."""
    return _kitchen_respond(lambda: service.kitchen_accept(principal, order_id))


@kitchen_router.post("/{order_id}/reject", response_model=KitchenOrderOut, responses=KITCHEN_REFUSALS)
def kitchen_reject(
    order_id: uuid.UUID, body: KitchenRejectIn, principal: CurrentPrincipal
) -> KitchenOrderOut | JSONResponse:
    """Reject with a reason; after acceptance KM/RM/CA only. Releases stock and refunds prepaid."""
    return _kitchen_respond(lambda: service.kitchen_reject(principal, order_id, body.reason))


@kitchen_router.post("/{order_id}/start", response_model=KitchenOrderOut, responses=KITCHEN_REFUSALS)
def kitchen_start(order_id: uuid.UUID, principal: CurrentPrincipal) -> KitchenOrderOut | JSONResponse:
    """Every pending item to Preparing; the order follows automatically."""
    return _kitchen_respond(lambda: service.kitchen_start(principal, order_id))


@kitchen_router.post(
    "/{order_id}/items/{item_id}/status", response_model=KitchenOrderOut, responses=KITCHEN_REFUSALS
)
def kitchen_item_status(
    order_id: uuid.UUID, item_id: uuid.UUID, body: KitchenItemStatusIn, principal: CurrentPrincipal
) -> KitchenOrderOut | JSONResponse:
    """Item Preparing or Prepared; the order becomes Ready for Pickup when all are Prepared (KI-05)."""
    return _kitchen_respond(lambda: service.kitchen_set_item(principal, order_id, item_id, body.status))
