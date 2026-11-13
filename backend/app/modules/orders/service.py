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

from sqlalchemy import Connection
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.permissions import Permission, Principal, can
from app.core.request_context import current_request_id
from app.modules.orders import domain as d
from app.modules.orders import repository as repo
from app.modules.payments import service as payments
from app.modules.payments.domain import OUTCOME_STATUS, PaymentMethod, PaymentStatus, SimOutcome, is_prepaid
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


class Unavailable(Exception):
    """A requested dish cannot be ordered (unknown, unpublished, unpriced, or a fixture in production)."""


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


# ---------------------------------------------------------------- placement (checkout idempotency)
def place(
    principal: Principal,
    *,
    idempotency_key: str,
    lines: list[tuple[uuid.UUID, int]],
    method: PaymentMethod,
    special_instructions: str | None,
) -> tuple[OrderView, bool]:
    """Returns (order, created). A repeat of the same request returns the original order (DDR-109)."""
    _require(principal, P.CUSTOMER_ORDERS_PLACE)
    fingerprint = d.request_hash([(str(m), q) for m, q in lines], method.value, special_instructions)
    with get_engine().begin() as conn:
        existing = repo.find_by_key(conn, principal.user_id, idempotency_key)
        if existing is not None:
            return _replay(conn, existing, fingerprint), False

        dishes = repo.menu_items(conn, [m for m, _ in lines])
        production = not get_settings().is_local_or_test
        for menu_item_id, _ in lines:
            dish = dishes.get(menu_item_id)
            if (
                dish is None
                or dish.publication_status != "PUBLISHED"
                or dish.price_paise is None
                or (production and dish.is_test_fixture)
            ):
                raise Unavailable(str(menu_item_id))
        subtotal = sum((dishes[m].price_paise or 0) * q for m, q in lines)

        set_actor(
            conn, role="CUSTOMER", user_id=principal.user_id, reason=None, correlation_id=current_request_id()
        )
        try:
            with conn.begin_nested():
                order_id = repo.create(
                    conn,
                    customer=principal.user_id,
                    menu_item_ids=[m for m, _ in lines],
                    idempotency_key=idempotency_key,
                    request_hash=fingerprint,
                    special_instructions=special_instructions,
                    food_subtotal_paise=subtotal,
                    delivery_fee_paise=d.DELIVERY_FEE_PAISE,
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
                raise Unavailable(str(getattr(diag, "message_primary", "") or "order refused")) from None
            raise

        for menu_item_id, quantity in lines:
            dish = dishes[menu_item_id]
            repo.insert_item(conn, order_id, menu_item_id, quantity, dish.name, dish.price_paise or 0)
        order = _reread(conn, order_id)
        payments.open_payment(conn, order_id, method, order.payable_paise or 0)
        _event(
            conn,
            order,
            "order.placed",
            {"payment_method": method.value, "payable_paise": order.payable_paise, "lines": len(lines)},
        )
        if not is_prepaid(method):
            # COD goes straight to the kitchen queue (Matrix §7.1; plan Task 7).
            repo.set_status(conn, order_id, F.PENDING_KITCHEN.value)
            order = _reread(conn, order_id)
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
