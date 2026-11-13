"""Ingredient stock (#4 §7; KI-21–KI-23; DDR-18, DDR-37, DDR-111 (4), (8), (9)).

Order-time functions run in the caller's transaction (the orders service owns it):
- `reserve` at kitchen acceptance: all or nothing; locked rows plus table checks prevent oversell.
- `release` on reject; `consume` at the validated handover, once (ledger unique per order and line).

Stock reads and manager actions are separate transactions. The opening stock is test-only (DDR-37):
every stock row carries its fixture flag, and the UI labels it "Test stock". AI never changes stock
(DDR-18). Adjustments and thresholds are audited; no approved event type exists for them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Connection

from app.core.db import get_engine
from app.core.permissions import Permission, Principal
from app.core.request_context import current_request_id
from app.modules.inventory import domain as d
from app.modules.inventory import repository as repo
from app.modules.kitchen_ops import service as kitchens
from app.shared.audit import write_event
from app.shared.events import emit

P = Permission
StockRow = repo.StockRow
Shortage = d.Shortage


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Invalid(Exception):
    pass


class InsufficientStock(Exception):
    """Acceptance refused: not enough available stock (DDR-111 (4)). Nothing was reserved."""

    def __init__(self, shortages: list[d.Shortage]) -> None:
        super().__init__("Not enough stock to accept this order")
        self.shortages = shortages


@dataclass(frozen=True)
class OrderRef:
    id: uuid.UUID
    kitchen_id: uuid.UUID
    region_id: uuid.UUID
    is_test_fixture: bool


def _event(
    conn: Connection, order: OrderRef, event_type: str, lines: list[tuple[uuid.UUID, Decimal]]
) -> None:
    emit(
        conn,
        event_type=event_type,
        aggregate_type="order",
        aggregate_id=order.id,
        is_test_fixture=order.is_test_fixture,
        region_id=order.region_id,
        kitchen_id=order.kitchen_id,
        correlation_id=current_request_id(),
        data={
            "order_id": str(order.id),
            "lines": [{"ingredient_id": str(i), "quantity": str(q)} for i, q in lines],
        },
    )


# ---------------------------------------------------------------- order-time (caller's transaction)
def reserve(conn: Connection, order: OrderRef) -> None:
    """Reserve every ingredient of the pinned recipes, or nothing (raises InsufficientStock)."""
    needs = repo.requirements(conn, order.id)
    if not needs:
        raise InsufficientStock([])  # a pinned recipe with no ingredient lines cannot be reserved
    rows = repo.lock_stock(conn, order.kitchen_id, [n.ingredient_id for n in needs])
    shortages = []
    for need in needs:
        row = rows.get(need.ingredient_id)
        free = d.available(row.on_hand, row.reserved) if row else Decimal(0)
        if free < need.quantity:
            shortages.append(d.Shortage(need.name, need.unit, need.quantity, free))
    if shortages:
        raise InsufficientStock(shortages)
    for need in needs:
        repo.change_stock(
            conn, order.kitchen_id, need.ingredient_id, on_hand=Decimal(0), reserved=need.quantity
        )
        repo.insert_reservation(conn, order.id, order.kitchen_id, need.ingredient_id, need.quantity)
    _event(conn, order, "inventory.reserved", [(n.ingredient_id, n.quantity) for n in needs])


def release(conn: Connection, order: OrderRef) -> bool:
    """Return the order's open reservations to available stock. False when nothing was reserved."""
    open_lines = repo.open_reservations(conn, order.id)
    if not open_lines:
        return False
    repo.lock_stock(conn, order.kitchen_id, [r.ingredient_id for r in open_lines])
    for line in open_lines:
        repo.change_stock(
            conn, order.kitchen_id, line.ingredient_id, on_hand=Decimal(0), reserved=-line.quantity
        )
        repo.set_reservation_status(conn, line.id, "RELEASED")
    _event(conn, order, "inventory.released", [(r.ingredient_id, r.quantity) for r in open_lines])
    return True


def consume(conn: Connection, order: OrderRef, *, actor_user_id: uuid.UUID, actor_role: str) -> bool:
    """Deduct the reserved stock at handover. Runs once: a repeat finds no open reservation."""
    open_lines = repo.open_reservations(conn, order.id)
    if not open_lines:
        return False
    repo.lock_stock(conn, order.kitchen_id, [r.ingredient_id for r in open_lines])
    for line in open_lines:
        repo.change_stock(
            conn, order.kitchen_id, line.ingredient_id, on_hand=-line.quantity, reserved=-line.quantity
        )
        repo.set_reservation_status(conn, line.id, "CONSUMED")
        repo.insert_movement(
            conn,
            kitchen_id=order.kitchen_id,
            ingredient_id=line.ingredient_id,
            delta=-line.quantity,
            kind="CONSUMPTION",
            order_id=order.id,
            reason=None,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
    _event(conn, order, "inventory.consumed", [(r.ingredient_id, r.quantity) for r in open_lines])
    return True


# ---------------------------------------------------------------- reads and manager actions
def _kitchen(conn: Connection, principal: Principal, kitchen_id: uuid.UUID | None) -> kitchens.KitchenRow:
    try:
        return kitchens.resolve(conn, principal, kitchen_id)
    except kitchens.NotFound:
        raise NotFound from None


def _require(principal: Principal, permission: Permission, kitchen: kitchens.KitchenRow) -> None:
    if kitchens.allowed(principal, permission, kitchen):
        return
    # Own kitchen without the permission is Forbidden; anyone else's kitchen reads as not found.
    if kitchens.allowed(principal, P.KITCHEN_ORDERS_VIEW, kitchen):
        raise Forbidden
    raise NotFound


def stock(principal: Principal, kitchen_id: uuid.UUID | None) -> list[StockRow]:
    """Full stock list (KM; Matrix §3.1 "manage ingredient records")."""
    with get_engine().connect() as conn:
        kitchen = _kitchen(conn, principal, kitchen_id)
        _require(principal, P.KITCHEN_INVENTORY_VIEW, kitchen)
        return repo.stock(conn, kitchen.id)


def low_stock(principal: Principal, kitchen_id: uuid.UUID | None) -> list[StockRow]:
    """Low-stock alerts for both kitchen roles: items at or below a threshold the KM set."""
    with get_engine().connect() as conn:
        kitchen = _kitchen(conn, principal, kitchen_id)
        _require(principal, P.KITCHEN_LOW_STOCK_VIEW, kitchen)
        return [
            s
            for s in repo.stock(conn, kitchen.id)
            if d.is_low(d.available(s.on_hand, s.reserved), s.low_stock_threshold)
        ]


def _reason(reason: str) -> str:
    cleaned = reason.strip()
    if not cleaned:
        raise Invalid("A reason is required")
    if len(cleaned) > d.REASON_MAX:
        raise Invalid(f"The reason can be at most {d.REASON_MAX} characters")
    return cleaned


def _locked_row(conn: Connection, kitchen: kitchens.KitchenRow, ingredient_id: uuid.UUID) -> StockRow:
    row = repo.lock_stock(conn, kitchen.id, [ingredient_id]).get(ingredient_id)
    if row is None:
        raise NotFound
    return row


def _updated(conn: Connection, kitchen: kitchens.KitchenRow, ingredient_id: uuid.UUID) -> StockRow:
    row = next((s for s in repo.stock(conn, kitchen.id) if s.ingredient_id == ingredient_id), None)
    if row is None:  # pragma: no cover - locked above
        raise NotFound
    return row


def adjust(
    principal: Principal,
    kitchen_id: uuid.UUID | None,
    ingredient_id: uuid.UUID,
    *,
    delta: Decimal,
    reason: str,
) -> StockRow:
    """Signed adjustment with a reason (KM; #4 §7.2), recorded in the ledger and the audit log."""
    with get_engine().begin() as conn:
        kitchen = _kitchen(conn, principal, kitchen_id)
        _require(principal, P.KITCHEN_STOCK_ADJUST, kitchen)
        text_reason = _reason(reason)
        role = kitchens.acting_role(
            principal, P.KITCHEN_STOCK_ADJUST, kitchen_id=kitchen.id, region_id=kitchen.region_id
        )
        row = _locked_row(conn, kitchen, ingredient_id)
        error = d.adjustment_error(row.on_hand, row.reserved, delta)
        if error:
            raise Invalid(error)
        repo.change_stock(conn, kitchen.id, ingredient_id, on_hand=delta, reserved=Decimal(0))
        repo.insert_movement(
            conn,
            kitchen_id=kitchen.id,
            ingredient_id=ingredient_id,
            delta=delta,
            kind="ADJUSTMENT",
            order_id=None,
            reason=text_reason,
            actor_user_id=principal.user_id,
            actor_role=role,
        )
        write_event(
            conn,
            action="inventory.stock.adjusted",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_type="ingredient_stock",
            target_id=str(ingredient_id),
            region_id=kitchen.region_id,
            kitchen_id=kitchen.id,
            reason=text_reason,
            correlation_id=current_request_id(),
            before={"on_hand": row.on_hand, "is_test_fixture": row.is_test_fixture},
            after={"on_hand": row.on_hand + delta, "delta": delta},
        )
        return _updated(conn, kitchen, ingredient_id)


def set_threshold(
    principal: Principal,
    kitchen_id: uuid.UUID | None,
    ingredient_id: uuid.UUID,
    *,
    threshold: Decimal | None,
    reason: str,
) -> StockRow:
    """The KM sets or clears an ingredient's low-stock threshold (DDR-42 open: no default exists)."""
    with get_engine().begin() as conn:
        kitchen = _kitchen(conn, principal, kitchen_id)
        _require(principal, P.KITCHEN_INGREDIENTS_MANAGE, kitchen)
        text_reason = _reason(reason)
        if threshold is not None and not Decimal(0) <= threshold <= d.QUANTITY_MAX:
            raise Invalid(f"The threshold must be between 0 and {d.QUANTITY_MAX}")
        role = kitchens.acting_role(
            principal, P.KITCHEN_INGREDIENTS_MANAGE, kitchen_id=kitchen.id, region_id=kitchen.region_id
        )
        row = _locked_row(conn, kitchen, ingredient_id)
        repo.set_threshold(conn, kitchen.id, ingredient_id, threshold)
        write_event(
            conn,
            action="inventory.threshold.changed",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_type="ingredient_stock",
            target_id=str(ingredient_id),
            region_id=kitchen.region_id,
            kitchen_id=kitchen.id,
            reason=text_reason,
            correlation_id=current_request_id(),
            before={"low_stock_threshold": row.low_stock_threshold},
            after={"low_stock_threshold": threshold},
        )
        return _updated(conn, kitchen, ingredient_id)
