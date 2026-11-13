"""Order placement, simulated payment outcome, cancellation and the fulfilment rules other tasks call
(Matrix §7; DDR-16, DDR-17, DDR-38, DDR-109; Phase 2 §7).

Transaction owner for orders and their payments: each public function is one transaction in which
the order, its payment and its outbox events change together or not at all. The database enforces
legal transitions and actor context; this module adds ownership, idempotency and payment rules.

Deny by default: customers act on their own orders only; another customer's order reads as not found.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.permissions import Permission, Principal, can
from app.core.request_context import current_request_id
from app.modules.customers import service as customers
from app.modules.delivery import service as delivery
from app.modules.inventory import service as inventory
from app.modules.kitchen_ops import service as kitchens
from app.modules.kitchen_ops.domain import Intake as KitchenIntake
from app.modules.orders import domain as d
from app.modules.orders import repository as repo
from app.modules.payments import service as payments
from app.modules.payments.domain import OUTCOME_STATUS, PaymentMethod, PaymentStatus, SimOutcome, is_prepaid
from app.modules.pricing import domain as pricing_domain
from app.modules.pricing import service as pricing
from app.shared.actor import set_actor
from app.shared.events import emit

P = Permission
F = d.Fulfilment
LIST_LIMIT = 50


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


@dataclass(frozen=True)
class OrderView:
    order: repo.OrderRow
    items: list[repo.ItemRow]
    payment: payments.PaymentRow | None
    labels: d.DisplayLabels


def _view(conn: Connection, order: repo.OrderRow) -> OrderView:
    return OrderView(
        order=order,
        items=repo.items(conn, order.id),
        payment=payments.for_order(conn, order.id),
        labels=d.display(F(order.fulfilment_status), order.assignment_accepted),
    )


def _require(principal: Principal, permission: Permission) -> None:
    if not can(principal, permission, customer_id=principal.user_id):
        raise Forbidden


def _own(conn: Connection, principal: Principal, order_id: uuid.UUID, *, lock: bool = False) -> repo.OrderRow:
    order = repo.find(conn, order_id, lock=lock)
    if order is None or order.customer_user_id != principal.user_id:
        raise NotFound
    return order


def _event(conn: Connection, order: repo.OrderRow, event_type: str, data: dict[str, object]) -> None:
    emit(
        conn,
        event_type=event_type,
        aggregate_type="order",
        aggregate_id=order.id,
        is_test_fixture=order.is_test_fixture,
        region_id=order.region_id,
        kitchen_id=order.kitchen_id,
        correlation_id=current_request_id(),
        data={"order_id": str(order.id), **data},
    )


def _ref(order: repo.OrderRow) -> inventory.OrderRef:
    return inventory.OrderRef(order.id, order.kitchen_id, order.region_id, order.is_test_fixture)


def _reread(conn: Connection, order_id: uuid.UUID) -> repo.OrderRow:
    order = repo.find(conn, order_id)
    if order is None:  # pragma: no cover - the row exists in this transaction
        raise NotFound
    return order


# ---------------------------------------------------------------- reads
def get(principal: Principal, order_id: uuid.UUID) -> OrderView:
    _require(principal, P.CUSTOMER_ORDERS_READ)
    with get_engine().connect() as conn:
        return _view(conn, _own(conn, principal, order_id))


def list_mine(principal: Principal) -> list[OrderView]:
    _require(principal, P.CUSTOMER_ORDERS_READ)
    with get_engine().connect() as conn:
        return [_view(conn, o) for o in repo.list_for_customer(conn, principal.user_id, LIST_LIMIT)]


# ---------------------------------------------------------------- checkout refusals
class CheckoutRefused(Exception):
    """A checkout rule refused the order (422). `code` is stable for the UI; `detail` adds context."""

    def __init__(self, code: str, message: str, detail: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


class PricesChanged(Exception):
    """A price differs from what the customer accepted (409); they must confirm the new price (CU-13)."""

    def __init__(self, changes: list[pricing_domain.PriceChange]) -> None:
        super().__init__("A price has changed. Review and confirm the new price before placing the order.")
        self.changes = changes


INTAKE_MESSAGES = {
    "kitchen_paused": "The kitchen is not taking new orders right now",
    "kitchen_at_capacity": "The kitchen is at capacity right now. Try again in a few minutes",
}


@dataclass(frozen=True)
class Line:
    menu_item_id: uuid.UUID
    quantity: int
    # The unit price the customer saw and accepted (DDR-110 (5)).
    unit_price_paise: int


def _orderable(dish: repo.MenuItemRow | None, production: bool) -> bool:
    return not (
        dish is None
        or dish.publication_status != "PUBLISHED"
        or dish.price_paise is None
        or (production and dish.is_test_fixture)
    )


def _charges(
    conn: Connection,
    customer: uuid.UUID,
    lines: list[Line],
    dishes: dict[uuid.UUID, repo.MenuItemRow],
) -> tuple[dict[uuid.UUID, int], list[pricing_domain.PriceChange]]:
    """The price to charge per dish (protected cart price or current price) and any stated-price mismatch."""
    window = pricing.protection_minutes(conn)
    now = pricing.now(conn)
    cart_lines = {c.menu_item_id: c for c in repo.cart(conn, customer)}
    charges: dict[uuid.UUID, int] = {}
    changes: list[pricing_domain.PriceChange] = []
    for line in lines:
        current = dishes[line.menu_item_id].price_paise or 0
        cart_line = cart_lines.get(line.menu_item_id)
        charge = pricing_domain.charge_price(
            current_price_paise=current,
            cart_price_paise=cart_line.unit_price_paise if cart_line else None,
            added_at=cart_line.added_at if cart_line else None,
            now=now,
            window_minutes=window,
        )
        charges[line.menu_item_id] = charge
        if charge != line.unit_price_paise:
            changes.append(pricing_domain.PriceChange(line.menu_item_id, line.unit_price_paise, charge))
    return charges, changes


# ---------------------------------------------------- placement (CU-17 sequence; DDR-109, DDR-110)
def place(
    principal: Principal,
    *,
    idempotency_key: str,
    lines: list[Line],
    method: PaymentMethod,
    special_instructions: str | None,
    address_id: uuid.UUID,
    coupon_code: str | None,
) -> tuple[OrderView, bool]:
    """Returns (order, created). A repeat of the same request returns the original order (DDR-109).

    Order of checks follows #1 §9: stock and prices → address and eligibility → ₹500 minimum →
    coupon → delivery fee → payment → place → simulate payment or COD → kitchen.
    """
    _require(principal, P.CUSTOMER_ORDERS_PLACE)
    fingerprint = d.request_hash(
        [(f"{line.menu_item_id}@{line.unit_price_paise}", line.quantity) for line in lines],
        f"{method.value}|{address_id}|{(coupon_code or '').strip().upper()}",
        special_instructions,
    )
    with get_engine().begin() as conn:
        existing = repo.find_by_key(conn, principal.user_id, idempotency_key)
        if existing is not None:
            return _replay(conn, existing, fingerprint), False

        # 1. Stock/availability and prices (CU-07, CU-13, CU-14).
        production = not get_settings().is_local_or_test
        dishes = repo.menu_items(conn, [line.menu_item_id for line in lines])
        unavailable = [
            str(x.menu_item_id) for x in lines if not _orderable(dishes.get(x.menu_item_id), production)
        ]
        if unavailable:
            raise CheckoutRefused(
                "dish_unavailable", "A dish in this order is not available", {"menu_item_ids": unavailable}
            )
        charges, changes = _charges(conn, principal.user_id, lines, dishes)
        if changes:
            raise PricesChanged(changes)
        subtotal = sum(charges[x.menu_item_id] * x.quantity for x in lines)
        order_is_fixture = all(dishes[x.menu_item_id].is_test_fixture for x in lines)

        # 2. Address and eligibility, revalidated before placement (CU-03).
        try:
            address = customers.owned_address(conn, principal, address_id)
        except customers.NotFound:
            raise CheckoutRefused("address_unknown", "Choose one of your saved delivery addresses") from None
        kitchen, reach = customers.check(conn, address.lat, address.lng)
        if not reach.serviceable:
            raise CheckoutRefused(
                "not_serviceable",
                "This address is outside the delivery area",
                {
                    "straight_line_km": str(reach.straight_line_km),
                    "road_km": str(reach.road_km),
                    "road_km_estimated": reach.road_km_estimated,
                },
            )

        # The kitchen must be taking orders: not Paused and below capacity (KI-13; DDR-111 (3)).
        intake = kitchens.intake_for(conn, kitchen.id)
        if intake.refusal:
            raise CheckoutRefused(intake.refusal, INTAKE_MESSAGES[intake.refusal])

        # 3. ₹500 minimum on the food subtotal before any coupon (DDR-53).
        minimum = pricing.minimum_paise(conn, kitchen.id)
        if subtotal < minimum:
            raise CheckoutRefused(
                "below_minimum",
                "The food subtotal is below the minimum order",
                {"food_subtotal_paise": subtotal, "minimum_paise": minimum},
            )

        # 4. Coupon (CU-16; one per order).
        coupon = None
        if coupon_code and coupon_code.strip():
            try:
                coupon = pricing.coupon(
                    conn,
                    coupon_code,
                    food_subtotal_paise=subtotal,
                    order_is_fixture=order_is_fixture,
                    production=production,
                    lock=True,
                )
            except pricing.CouponRefused as exc:
                raise CheckoutRefused(exc.code, str(exc)) from None
        fee = pricing.delivery_fee_paise(conn, kitchen.id)  # ₹30 at every subtotal (DDR-38)
        amounts = pricing_domain.bill(
            food_subtotal_paise=subtotal,
            minimum_paise=minimum,
            delivery_fee_paise=fee,
            discount_paise=coupon.discount_paise if coupon else 0,
        )

        # 5. Place: order, items, payment and event in one transaction.
        set_actor(
            conn, role="CUSTOMER", user_id=principal.user_id, reason=None, correlation_id=current_request_id()
        )
        try:
            with conn.begin_nested():
                order_id = repo.create(
                    conn,
                    customer=principal.user_id,
                    menu_item_ids=[x.menu_item_id for x in lines],
                    idempotency_key=idempotency_key,
                    request_hash=fingerprint,
                    special_instructions=special_instructions,
                    food_subtotal_paise=subtotal,
                    delivery_fee_paise=fee,
                    discount_paise=amounts.discount_paise,
                )
        except IntegrityError as exc:
            if "orders_customer_idempotency_uq" not in str(exc.orig):
                raise
            # A concurrent request with the same key committed first: answer as a replay.
            raced = repo.find_by_key(conn, principal.user_id, idempotency_key)
            if raced is None:  # pragma: no cover - the unique violation means it exists
                raise
            return _replay(conn, raced, fingerprint), False
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23514":  # create_order refused the dish set
                diag = getattr(exc.orig, "diag", None)
                raise CheckoutRefused(
                    "order_refused", str(getattr(diag, "message_primary", "") or "refused")
                ) from None
            raise
        if coupon is not None:
            try:
                pricing.redeem(conn, coupon)
            except pricing.CouponRefused as exc:
                raise CheckoutRefused(exc.code, str(exc)) from None
        repo.set_delivery_snapshot(
            conn,
            order_id,
            address_line=address.address_line,
            lat=address.lat,
            lng=address.lng,
            straight_line_km=reach.straight_line_km,
            road_km=reach.road_km,
            road_estimated=reach.road_km_estimated,
            coupon_id=coupon.id if coupon else None,
        )
        for line in lines:
            dish = dishes[line.menu_item_id]
            repo.insert_item(
                conn, order_id, line.menu_item_id, line.quantity, dish.name, charges[line.menu_item_id]
            )
        order = _reread(conn, order_id)
        payments.open_payment(conn, order_id, method, order.payable_paise or 0)
        _event(
            conn,
            order,
            "order.placed",
            {
                "payment_method": method.value,
                "payable_paise": order.payable_paise,
                "discount_paise": order.discount_paise,
                "lines": len(lines),
            },
        )
        if not is_prepaid(method):
            # COD goes straight to the kitchen queue (Matrix §7.1; plan Task 7).
            repo.set_status(conn, order_id, F.PENDING_KITCHEN.value)
            order = _reread(conn, order_id)
        repo.delete_cart_lines(conn, principal.user_id, [x.menu_item_id for x in lines])
        return _view(conn, order), True


def _replay(conn: Connection, existing: repo.OrderRow, fingerprint: str) -> OrderView:
    if existing.request_hash != fingerprint:
        raise Conflict("This Idempotency-Key was already used for a different order")
    return _view(conn, existing)


# ---------------------------------------------------------------- simulated payment (DDR-109)
def simulate_payment(principal: Principal, order_id: uuid.UUID, outcome: SimOutcome) -> OrderView:
    _require(principal, P.CUSTOMER_ORDERS_PLACE)
    with get_engine().begin() as conn:
        order = _own(conn, principal, order_id, lock=True)
        payment = payments.for_order(conn, order_id, lock=True)
        if payment is None:
            raise Conflict("Order has no payment")
        if payment.status == OUTCOME_STATUS[outcome]:
            return _view(conn, order)  # the same result again: idempotent
        if order.fulfilment_status != F.PLACED:
            raise Conflict(f"Order is {order.fulfilment_status}; no payment step remains")
        reason = None if outcome is SimOutcome.SUCCESS else f"Simulated payment {outcome.value.lower()}"
        set_actor(
            conn,
            role="CUSTOMER",
            user_id=principal.user_id,
            reason=reason,
            correlation_id=current_request_id(),
        )
        try:
            status = payments.apply_outcome(conn, payment, outcome)
        except payments.PaymentConflict as exc:
            raise Conflict(str(exc)) from None
        if status is PaymentStatus.SUCCEEDED:
            repo.set_status(conn, order_id, F.PENDING_KITCHEN.value)
            _event(
                conn,
                order,
                "payment.succeeded",
                {"payment_id": str(payment.id), "amount_paise": payment.amount_paise},
            )
        else:
            # Failure or timeout never reaches the kitchen: the order is cancelled (DDR-109).
            repo.set_status(conn, order_id, F.CANCELLED.value)
            _event(conn, order, "payment.failed", {"payment_id": str(payment.id), "status": status.value})
            _event(conn, order, "order.cancelled", {"cause": "payment_" + status.value.lower()})
        return _view(conn, _reread(conn, order_id))


# ---------------------------------------------------------------- customer cancel before acceptance (CU-19)
def cancel(principal: Principal, order_id: uuid.UUID, reason: str | None) -> OrderView:
    _require(principal, P.CUSTOMER_ORDERS_CANCEL)
    with get_engine().begin() as conn:
        order = _own(conn, principal, order_id, lock=True)
        if order.fulfilment_status == F.PLACED:
            raise Conflict("Complete or fail the simulated payment first")
        if order.fulfilment_status != F.PENDING_KITCHEN:
            raise Conflict(f"Order is {order.fulfilment_status}; it can no longer be cancelled")
        text_reason = reason or "Customer cancelled before kitchen acceptance"
        set_actor(
            conn,
            role="CUSTOMER",
            user_id=principal.user_id,
            reason=text_reason,
            correlation_id=current_request_id(),
        )
        repo.set_status(conn, order_id, F.CANCELLED.value)
        payment = payments.for_order(conn, order_id, lock=True)
        refunded = payment is not None and payments.refund_routine(conn, payment)
        _event(conn, order, "order.cancelled", {"cause": "customer", "refunded": refunded})
        return _view(conn, _reread(conn, order_id))


# ---------------------------------------------------------------- rules called by Tasks 8 and 9
def _agent_assignment(conn: Connection, order: repo.OrderRow, agent: Principal) -> repo.AssignmentRow:
    """The caller must be a delivery agent in the order's region holding its accepted assignment."""
    if not can(agent, P.DELIVERY_ASSIGNMENTS_VIEW, region_id=order.region_id):
        raise Forbidden
    assignment = repo.live_assignment(conn, order.id)
    if assignment is None or assignment.agent_user_id != agent.user_id or assignment.status != "ACCEPTED":
        raise Forbidden
    return assignment


def record_pickup(agent: Principal, order_id: uuid.UUID) -> OrderView:
    """Validated pickup: PICKED_UP, then OUT_FOR_DELIVERY automatically in the same transaction (DDR-16).

    The only code path into either status. Assignment changes never call it (Task 9 owns the endpoint).
    """
    with get_engine().begin() as conn:
        order = repo.find(conn, order_id, lock=True)
        if order is None:
            raise NotFound
        _agent_assignment(conn, order, agent)
        if order.fulfilment_status != F.READY_FOR_PICKUP:
            raise Conflict(f"Pickup needs a ready order; it is {order.fulfilment_status}")
        set_actor(
            conn,
            role="DELIVERY_AGENT",
            user_id=agent.user_id,
            reason=None,
            correlation_id=current_request_id(),
        )
        repo.set_status(conn, order_id, F.PICKED_UP.value)
        repo.set_status(conn, order_id, F.OUT_FOR_DELIVERY.value)
        # Reserved stock is deducted at the validated handover, once (KI-22; DDR-111).
        inventory.consume(conn, _ref(order), actor_user_id=agent.user_id, actor_role="DELIVERY_AGENT")
        emit(
            conn,
            event_type="delivery.picked_up",
            aggregate_type="order",
            aggregate_id=order.id,
            is_test_fixture=order.is_test_fixture,
            region_id=order.region_id,
            kitchen_id=order.kitchen_id,
            correlation_id=current_request_id(),
            data={"order_id": str(order.id)},
        )
        return _view(conn, _reread(conn, order_id))


def _kitchen_allowed(principal: Principal, order: repo.OrderRow, permission: Permission) -> str:
    """The acting role for a kitchen action on this order; Forbidden or NotFound otherwise."""
    if can(principal, permission, kitchen_id=order.kitchen_id, region_id=order.region_id):
        return kitchens.acting_role(
            principal, permission, kitchen_id=order.kitchen_id, region_id=order.region_id
        )
    if _can_view_kitchen(principal, order.kitchen_id, order.region_id):
        raise Forbidden
    raise NotFound  # another kitchen's order reads as not found


def _can_view_kitchen(principal: Principal, kitchen_id: uuid.UUID, region_id: uuid.UUID) -> bool:
    return can(principal, P.KITCHEN_ORDERS_VIEW, kitchen_id=kitchen_id, region_id=region_id) or can(
        principal, P.MGMT_OPERATIONS_VIEW, kitchen_id=kitchen_id, region_id=region_id
    )


# ---------------------------------------------------------------- kitchen queue and preparation (Task 8)
class KitchenRefused(Exception):
    """The kitchen cannot accept the order now (409). `code` is stable for the UI (DDR-111 (3), (4))."""

    def __init__(self, code: str, message: str, detail: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


class InvalidInput(Exception):
    """The request breaks an input rule (422)."""


MissingKitchenSetting = kitchens.MissingSetting


@dataclass(frozen=True)
class KitchenOrderView:
    order: repo.OrderRow
    items: list[repo.ItemRow]
    kitchen_label: str
    payment_method: str | None
    queued_at: datetime | None
    # Incoming beyond the acceptance timeout (KI-02). A warning only: it never reorders the queue.
    overdue: bool
    assignment: delivery.LiveAssignment | None


@dataclass(frozen=True)
class KitchenQueue:
    kitchen: kitchens.KitchenRow
    intake: KitchenIntake
    acceptance_timeout_minutes: int | None
    incoming: list[KitchenOrderView]
    held: list[KitchenOrderView]
    can_process: bool
    can_reject_accepted: bool


def _kitchen_views(
    conn: Connection, kitchen: kitchens.KitchenRow, orders: list[repo.OrderRow]
) -> list[KitchenOrderView]:
    ids = [o.id for o in orders]
    queued = repo.queued_since(conn, ids)
    live = delivery.live_for(conn, ids)
    timeout = kitchens.acceptance_timeout_minutes(conn, kitchen)
    now = pricing.now(conn)
    views = []
    for o in orders:
        payment = payments.for_order(conn, o.id)
        since = queued.get(o.id)
        overdue = (
            o.fulfilment_status == F.PENDING_KITCHEN
            and since is not None
            and timeout is not None
            and (now - since).total_seconds() > timeout * 60
        )
        views.append(
            KitchenOrderView(
                order=o,
                items=repo.items(conn, o.id),
                kitchen_label=d.display(F(o.fulfilment_status), o.assignment_accepted).kitchen or "",
                payment_method=payment.method if payment else None,
                queued_at=since,
                overdue=overdue,
                assignment=live.get(o.id),
            )
        )
    return views


def kitchen_queue(principal: Principal, kitchen_id: uuid.UUID | None) -> KitchenQueue:
    """Incoming orders, then the orders the kitchen holds in FIFO by acceptance time (KI-01, KI-03)."""
    with get_engine().connect() as conn:
        try:
            kitchen = kitchens.resolve(conn, principal, kitchen_id)
        except kitchens.NotFound:
            raise NotFound from None
        if not _can_view_kitchen(principal, kitchen.id, kitchen.region_id):
            raise NotFound
        incoming = repo.kitchen_orders(conn, kitchen.id, [F.PENDING_KITCHEN.value])
        held = repo.kitchen_orders(conn, kitchen.id, [s.value for s in d.KITCHEN_ACTIVE])
        return KitchenQueue(
            kitchen=kitchen,
            intake=kitchens.intake(conn, kitchen),
            acceptance_timeout_minutes=kitchens.acceptance_timeout_minutes(conn, kitchen),
            incoming=_kitchen_views(conn, kitchen, incoming),
            held=_kitchen_views(conn, kitchen, held),
            can_process=kitchens.allowed(principal, P.KITCHEN_ORDERS_PROCESS, kitchen),
            can_reject_accepted=kitchens.allowed(principal, P.KITCHEN_ORDERS_REJECT_ACCEPTED, kitchen),
        )


def _kitchen_view(conn: Connection, order_id: uuid.UUID) -> KitchenOrderView:
    order = _reread(conn, order_id)
    return _kitchen_views(conn, kitchens.find(conn, order.kitchen_id), [order])[0]


def kitchen_accept(principal: Principal, order_id: uuid.UUID) -> KitchenOrderView:
    """Accept: capacity and mode, pin ACTIVE versions, reserve all stock or none, offer to an agent.

    One transaction, serialised per kitchen by a row lock, so concurrent acceptances cannot exceed
    capacity or oversell. Any refusal leaves the order Incoming with nothing pinned or reserved.
    """
    with get_engine().begin() as conn:
        order = repo.find(conn, order_id)
        if order is None:
            raise NotFound
        role = _kitchen_allowed(principal, order, P.KITCHEN_ORDERS_PROCESS)
        kitchen = kitchens.lock(conn, order.kitchen_id)
        order = repo.find(conn, order_id, lock=True)
        if order is None:  # pragma: no cover - read above
            raise NotFound
        if order.fulfilment_status != F.PENDING_KITCHEN:
            raise Conflict(f"Order is {order.fulfilment_status}; only incoming orders can be accepted")
        intake = kitchens.intake(conn, kitchen)
        if intake.refusal:
            raise KitchenRefused(
                intake.refusal,
                INTAKE_MESSAGES[intake.refusal],
                {"mode": intake.mode.value, "capacity": intake.capacity, "active_orders": intake.active},
            )
        set_actor(
            conn, role=role, user_id=principal.user_id, reason=None, correlation_id=current_request_id()
        )
        if repo.pin_active_versions(conn, order_id):
            raise KitchenRefused("recipe_not_active", "A dish in this order has no active recipe version")
        try:
            inventory.reserve(conn, _ref(order))
        except inventory.InsufficientStock as exc:
            raise KitchenRefused(
                "stock_short",
                str(exc),
                {
                    "shortages": [
                        {
                            "ingredient": s.ingredient_name,
                            "unit": s.unit,
                            "needed": str(s.needed),
                            "available": str(s.available),
                        }
                        for s in exc.shortages
                    ]
                },
            ) from None
        repo.set_accepted_at(conn, order_id)
        repo.set_status(conn, order_id, F.ACCEPTED.value)
        offer = delivery.offer_on_acceptance(conn, order.id, order.region_id)
        _event(conn, order, "order.accepted", {"agent_offered": offer is not None})
        return _kitchen_view(conn, order_id)


def kitchen_reject(principal: Principal, order_id: uuid.UUID, reason: str) -> KitchenOrderView:
    """Reject an incoming order, or "cannot fulfil" a held one (KM, RM, CA; DDR-111 (5)).

    Releases reserved stock, refunds a prepaid order in full (DDR-109 (5)) and revokes the agent offer.
    """
    text_reason = reason.strip()
    with get_engine().begin() as conn:
        # Authorize on a plain read before taking the row lock (no lock for callers outside scope).
        seen = repo.find(conn, order_id)
        if seen is None or not _can_view_kitchen(principal, seen.kitchen_id, seen.region_id):
            raise NotFound
        if not (
            can(principal, P.KITCHEN_ORDERS_PROCESS, kitchen_id=seen.kitchen_id, region_id=seen.region_id)
            or can(
                principal,
                P.KITCHEN_ORDERS_REJECT_ACCEPTED,
                kitchen_id=seen.kitchen_id,
                region_id=seen.region_id,
            )
        ):
            raise Forbidden
        if not text_reason or len(text_reason) > d.REJECT_REASON_MAX:
            raise InvalidInput(f"A reason of 1 to {d.REJECT_REASON_MAX} characters is required")
        order = repo.find(conn, order_id, lock=True)
        if order is None:  # pragma: no cover - read above
            raise NotFound
        status = F(order.fulfilment_status)
        if status is F.PENDING_KITCHEN:
            permission = P.KITCHEN_ORDERS_PROCESS
        elif status in d.KITCHEN_ACTIVE:
            permission = P.KITCHEN_ORDERS_REJECT_ACCEPTED
        else:
            raise Conflict(f"Order is {order.fulfilment_status}; it can no longer be rejected")
        role = _kitchen_allowed(principal, order, permission)
        set_actor(
            conn,
            role=role,
            user_id=principal.user_id,
            reason=text_reason,
            correlation_id=current_request_id(),
        )
        repo.set_status(conn, order_id, F.REJECTED.value)
        released = inventory.release(conn, _ref(order))
        payment = payments.for_order(conn, order_id, lock=True)
        refunded = payment is not None and payments.refund_routine(conn, payment)
        revoked = delivery.revoke(conn, order_id)
        _event(
            conn,
            order,
            "order.rejected",
            {
                "after_acceptance": status is not F.PENDING_KITCHEN,
                "stock_released": released,
                "refunded": refunded,
                "assignment_revoked": revoked,
            },
        )
        return _kitchen_view(conn, order_id)


def _advance(conn: Connection, order: repo.OrderRow) -> None:
    """Apply the automatic order steps after item changes (KI-05; DDR-111 (11))."""
    items = [d.ItemPrep(i.prep_status) for i in repo.items(conn, order.id)]
    for step in d.order_status_after_items(F(order.fulfilment_status), items):
        repo.set_status(conn, order.id, step.value)
        _event(conn, order, "order.preparing" if step is F.PREPARING else "order.ready_for_pickup", {})


def _held_for_prep(conn: Connection, principal: Principal, order_id: uuid.UUID) -> repo.OrderRow:
    seen = repo.find(conn, order_id)
    if seen is None:
        raise NotFound
    role = _kitchen_allowed(principal, seen, P.KITCHEN_ORDERS_PROCESS)  # before the row lock
    order = repo.find(conn, order_id, lock=True)
    if order is None:  # pragma: no cover - read above
        raise NotFound
    if order.fulfilment_status not in (F.ACCEPTED, F.PREPARING):
        raise Conflict(
            f"Order is {order.fulfilment_status}; items can change only while it is being prepared"
        )
    # Any staff member may continue another's order; the actor of each change is kept (KI-06).
    set_actor(conn, role=role, user_id=principal.user_id, reason=None, correlation_id=current_request_id())
    return order


def kitchen_set_item(
    principal: Principal, order_id: uuid.UUID, item_id: uuid.UUID, target: d.ItemPrep
) -> KitchenOrderView:
    with get_engine().begin() as conn:
        order = _held_for_prep(conn, principal, order_id)
        item = next((i for i in repo.items(conn, order_id) if i.id == item_id), None)
        if item is None:
            raise NotFound
        if not d.can_prepare(d.ItemPrep(item.prep_status), target):
            raise Conflict(f"Item is {item.prep_status}; it cannot move to {target.value}")
        repo.set_item_status(conn, item_id, target.value)
        _advance(conn, order)
        return _kitchen_view(conn, order_id)


def kitchen_start(principal: Principal, order_id: uuid.UUID) -> KitchenOrderView:
    """ "Start order": every pending item to Preparing in one tap (KI-U5; DDR-111 (11))."""
    with get_engine().begin() as conn:
        order = _held_for_prep(conn, principal, order_id)
        pending = [i for i in repo.items(conn, order_id) if i.prep_status == d.ItemPrep.PENDING]
        if not pending:
            raise Conflict("Every item has already started")
        for item in pending:
            repo.set_item_status(conn, item.id, d.ItemPrep.PREPARING.value)
        _advance(conn, order)
        return _kitchen_view(conn, order_id)


def record_cod_collection(
    agent: Principal, order_id: uuid.UUID, *, collected: bool, reason: str | None
) -> OrderView:
    """COD at the door: collected, or a mismatch escalated to the manager with a reason (#7 §8)."""
    with get_engine().begin() as conn:
        order = repo.find(conn, order_id, lock=True)
        if order is None:
            raise NotFound
        _agent_assignment(conn, order, agent)
        if order.fulfilment_status != F.OUT_FOR_DELIVERY:
            raise Conflict("Cash is collected at delivery")
        payment = payments.for_order(conn, order_id, lock=True)
        if payment is None:
            raise Conflict("Order has no payment")
        if not collected and not reason:
            raise Conflict("A mismatch needs a reason")
        set_actor(
            conn,
            role="DELIVERY_AGENT",
            user_id=agent.user_id,
            reason=reason,
            correlation_id=current_request_id(),
        )
        try:
            payments.record_cod(conn, payment, collected=collected)
        except payments.PaymentConflict as exc:
            raise Conflict(str(exc)) from None
        return _view(conn, _reread(conn, order_id))


# ---------------------------------------------------------------- cart and quote (CU-11–CU-17; DDR-110)
CART_QUANTITY_MAX = 99  # input-size guard only; #1 §8 sets no per-dish cap (stock limits it, Task 8)


@dataclass(frozen=True)
class CartLineView:
    line: repo.CartRow
    available: bool
    charge_price_paise: int | None
    protected_until: datetime
    # Protection expired and the published price differs: the customer must confirm (CU-13).
    price_changed: bool


@dataclass(frozen=True)
class CartView:
    lines: list[CartLineView]
    bill: pricing_domain.Bill
    coupon_code: str | None
    coupon_error: str | None
    serviceability: customers.Serviceability | None
    kitchen: customers.KitchenRow
    address_error: str | None
    blockers: list[str]


def _cart_view(
    conn: Connection, principal: Principal, address_id: uuid.UUID | None, coupon_code: str | None
) -> CartView:
    production = not get_settings().is_local_or_test
    window = pricing.protection_minutes(conn)
    now = pricing.now(conn)
    views: list[CartLineView] = []
    for line in repo.cart(conn, principal.user_id):
        available = (
            line.publication_status == "PUBLISHED"
            and line.current_price_paise is not None
            and not (production and line.is_test_fixture)
        )
        charge = (
            pricing_domain.charge_price(
                current_price_paise=line.current_price_paise or 0,
                cart_price_paise=line.unit_price_paise,
                added_at=line.added_at,
                now=now,
                window_minutes=window,
            )
            if available
            else None
        )
        views.append(
            CartLineView(
                line,
                available,
                charge,
                pricing_domain.protected_until(line.added_at, window),
                price_changed=available and charge != line.unit_price_paise,
            )
        )

    kitchen = customers.kitchen(conn)
    subtotal = sum((v.charge_price_paise or 0) * v.line.quantity for v in views if v.available)
    blockers: list[str] = []
    if not views:
        blockers.append("cart_empty")
    intake = kitchens.intake_for(conn, kitchen.id)
    if intake.refusal:
        blockers.append(intake.refusal)
    if any(not v.available for v in views):
        blockers.append("dish_unavailable")
    if any(v.price_changed for v in views):
        blockers.append("price_changed")

    reach = None
    address_error = None
    if address_id is not None:
        try:
            address = customers.owned_address(conn, principal, address_id)
            reach = customers.check(conn, address.lat, address.lng)[1]
            if not reach.serviceable:
                blockers.append("not_serviceable")
        except customers.NotFound:
            address_error = "address_unknown"
            blockers.append("address_unknown")
    else:
        blockers.append("address_required")

    minimum = pricing.minimum_paise(conn, kitchen.id)
    if views and subtotal < minimum:
        blockers.append("below_minimum")
    discount = 0
    coupon_error = None
    if coupon_code and coupon_code.strip() and views:
        is_fixture = all(v.line.is_test_fixture for v in views)
        try:
            discount = pricing.coupon(
                conn,
                coupon_code,
                food_subtotal_paise=subtotal,
                order_is_fixture=is_fixture,
                production=production,
            ).discount_paise
        except pricing.CouponRefused as exc:
            coupon_error = exc.code
            blockers.append(exc.code)
    amounts = pricing_domain.bill(
        food_subtotal_paise=subtotal,
        minimum_paise=minimum,
        delivery_fee_paise=pricing.delivery_fee_paise(conn, kitchen.id),
        discount_paise=discount,
    )
    return CartView(
        views,
        amounts,
        coupon_code.strip().upper() if coupon_code else None,
        coupon_error,
        reach,
        kitchen,
        address_error,
        blockers,
    )


def get_cart(principal: Principal, address_id: uuid.UUID | None, coupon_code: str | None) -> CartView:
    _require(principal, P.CUSTOMER_ORDERS_PLACE)
    with get_engine().connect() as conn:
        return _cart_view(conn, principal, address_id, coupon_code)


def set_cart_quantity(principal: Principal, menu_item_id: uuid.UUID, quantity: int) -> CartView:
    """Add a dish at today's price, or change the quantity of a line (keeping its protection window)."""
    _require(principal, P.CUSTOMER_ORDERS_PLACE)
    production = not get_settings().is_local_or_test
    with get_engine().begin() as conn:
        dish = repo.menu_items(conn, [menu_item_id]).get(menu_item_id)
        existing = repo.cart_line(conn, principal.user_id, menu_item_id)
        if existing is None and not _orderable(dish, production):
            raise CheckoutRefused("dish_unavailable", "This dish is not available")
        others = [c for c in repo.cart(conn, principal.user_id) if c.menu_item_id != menu_item_id]
        if dish is not None and any(c.is_test_fixture != dish.is_test_fixture for c in others):
            # Test and real dishes never share an order (DDR-109), so they never share a cart.
            raise CheckoutRefused("cart_mixed", "TEST dishes and real dishes cannot be in the same cart")
        repo.upsert_cart_line(
            conn,
            principal.user_id,
            menu_item_id,
            quantity,
            existing.unit_price_paise if existing else (dish.price_paise or 0) if dish else 0,
        )
        return _cart_view(conn, principal, None, None)


def accept_price(principal: Principal, menu_item_id: uuid.UUID) -> CartView:
    """Explicit confirmation of a revised price (CU-13)."""
    _require(principal, P.CUSTOMER_ORDERS_PLACE)
    production = not get_settings().is_local_or_test
    with get_engine().begin() as conn:
        dish = repo.menu_items(conn, [menu_item_id]).get(menu_item_id)
        if repo.cart_line(conn, principal.user_id, menu_item_id) is None:
            raise NotFound
        if dish is None or not _orderable(dish, production):
            raise CheckoutRefused("dish_unavailable", "This dish is not available")
        repo.accept_cart_price(conn, principal.user_id, menu_item_id, dish.price_paise or 0)
        return _cart_view(conn, principal, None, None)


def remove_from_cart(principal: Principal, menu_item_id: uuid.UUID) -> CartView:
    _require(principal, P.CUSTOMER_ORDERS_PLACE)
    with get_engine().begin() as conn:
        if not repo.delete_cart_lines(conn, principal.user_id, [menu_item_id]):
            raise NotFound
        return _cart_view(conn, principal, None, None)


def remove_unavailable(principal: Principal) -> CartView:
    """The customer confirms removal of dishes that became unavailable (CU-14)."""
    _require(principal, P.CUSTOMER_ORDERS_PLACE)
    with get_engine().begin() as conn:
        view = _cart_view(conn, principal, None, None)
        gone = [v.line.menu_item_id for v in view.lines if not v.available]
        if gone:
            repo.delete_cart_lines(conn, principal.user_id, gone)
        return _cart_view(conn, principal, None, None)


def clear_cart(principal: Principal) -> None:
    _require(principal, P.CUSTOMER_ORDERS_PLACE)
    with get_engine().begin() as conn:
        repo.delete_cart_lines(conn, principal.user_id, None)
