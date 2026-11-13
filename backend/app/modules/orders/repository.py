"""SQL for orders, order items and their live delivery assignment.

Parameterised queries only; callers own the transaction.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, Row, text

_ORDER_COLUMNS = """
    o.id, o.customer_user_id, o.kitchen_id, o.region_id, o.fulfilment_status, o.special_instructions,
    o.is_test_fixture, o.idempotency_key, o.request_hash, o.food_subtotal_paise, o.delivery_fee_paise,
    o.payable_paise, o.placed_at, o.updated_at,
    EXISTS (SELECT 1 FROM app.delivery_assignments a WHERE a.order_id = o.id AND a.status = 'ACCEPTED')
        AS assignment_accepted
"""


@dataclass(frozen=True)
class OrderRow:
    id: uuid.UUID
    customer_user_id: uuid.UUID
    kitchen_id: uuid.UUID
    region_id: uuid.UUID
    fulfilment_status: str
    special_instructions: str | None
    is_test_fixture: bool
    idempotency_key: str | None
    request_hash: str | None
    food_subtotal_paise: int | None
    delivery_fee_paise: int | None
    payable_paise: int | None
    placed_at: datetime
    updated_at: datetime
    assignment_accepted: bool


@dataclass(frozen=True)
class ItemRow:
    menu_item_id: uuid.UUID
    item_name: str | None
    unit_price_paise: int | None
    quantity: int
    prep_status: str


@dataclass(frozen=True)
class MenuItemRow:
    id: uuid.UUID
    name: str
    price_paise: int | None
    publication_status: str
    is_test_fixture: bool


@dataclass(frozen=True)
class AssignmentRow:
    id: uuid.UUID
    agent_user_id: uuid.UUID
    status: str


def _order(row: Row[Any]) -> OrderRow:
    return OrderRow(**row._mapping)


def find(conn: Connection, order_id: uuid.UUID, *, lock: bool = False) -> OrderRow | None:
    sql = f"SELECT {_ORDER_COLUMNS} FROM app.orders o WHERE o.id = :id"  # noqa: S608 - fixed SQL
    row = conn.execute(text(sql + (" FOR UPDATE OF o" if lock else "")), {"id": order_id}).first()
    return _order(row) if row else None


def find_by_key(conn: Connection, customer: uuid.UUID, key: str) -> OrderRow | None:
    row = conn.execute(
        text(
            f"SELECT {_ORDER_COLUMNS} FROM app.orders o "  # noqa: S608 - fixed SQL, values bound
            "WHERE o.customer_user_id = :c AND o.idempotency_key = :k"
        ),
        {"c": customer, "k": key},
    ).first()
    return _order(row) if row else None


def list_for_customer(conn: Connection, customer: uuid.UUID, limit: int) -> list[OrderRow]:
    rows = conn.execute(
        text(
            f"SELECT {_ORDER_COLUMNS} FROM app.orders o WHERE o.customer_user_id = :c "  # noqa: S608
            "ORDER BY o.placed_at DESC LIMIT :lim"
        ),
        {"c": customer, "lim": limit},
    ).all()
    return [_order(r) for r in rows]


def menu_items(conn: Connection, ids: list[uuid.UUID]) -> dict[uuid.UUID, MenuItemRow]:
    rows = conn.execute(
        text(
            "SELECT id, name, price_paise, publication_status, is_test_fixture FROM app.menu_items "
            "WHERE id = ANY(:ids)"
        ),
        {"ids": ids},
    ).all()
    return {r.id: MenuItemRow(*r) for r in rows}


def create(
    conn: Connection,
    *,
    customer: uuid.UUID,
    menu_item_ids: list[uuid.UUID],
    idempotency_key: str,
    request_hash: str,
    special_instructions: str | None,
    food_subtotal_paise: int,
    delivery_fee_paise: int,
) -> uuid.UUID:
    """Controlled creation (migration 0008): the database derives kitchen, region and fixture flag."""
    order_id: uuid.UUID = conn.execute(
        text("SELECT app.create_order(:c, :items, :key, :hash, :si, :sub, :fee)"),
        {
            "c": customer,
            "items": menu_item_ids,
            "key": idempotency_key,
            "hash": request_hash,
            "si": special_instructions,
            "sub": food_subtotal_paise,
            "fee": delivery_fee_paise,
        },
    ).scalar_one()
    return order_id


def insert_item(
    conn: Connection,
    order_id: uuid.UUID,
    menu_item_id: uuid.UUID,
    quantity: int,
    name: str,
    unit_price_paise: int,
) -> None:
    conn.execute(
        text(
            "INSERT INTO app.order_items (order_id, menu_item_id, quantity, prep_status, item_name, "
            "unit_price_paise) VALUES (:o, :m, :q, 'PENDING', :n, :p)"
        ),
        {"o": order_id, "m": menu_item_id, "q": quantity, "n": name, "p": unit_price_paise},
    )


def items(conn: Connection, order_id: uuid.UUID) -> list[ItemRow]:
    rows = conn.execute(
        text(
            "SELECT menu_item_id, item_name, unit_price_paise, quantity, prep_status FROM app.order_items "
            "WHERE order_id = :o ORDER BY created_at, id"
        ),
        {"o": order_id},
    ).all()
    return [ItemRow(*r) for r in rows]


def set_status(conn: Connection, order_id: uuid.UUID, status: str) -> None:
    conn.execute(
        text("UPDATE app.orders SET fulfilment_status = :s WHERE id = :id"), {"s": status, "id": order_id}
    )


def live_assignment(conn: Connection, order_id: uuid.UUID) -> AssignmentRow | None:
    row = conn.execute(
        text(
            "SELECT id, agent_user_id, status FROM app.delivery_assignments WHERE order_id = :o "
            "AND status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED')"
        ),
        {"o": order_id},
    ).first()
    return AssignmentRow(*row) if row else None
