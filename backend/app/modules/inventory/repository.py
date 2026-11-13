"""SQL for ingredient stock, reservations and the stock ledger. Parameterised; callers own the transaction.

Requirements read pinned recipe lines (`app.order_items`, `app.recipe_ingredients`) read only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Connection, text


@dataclass(frozen=True)
class Requirement:
    ingredient_id: uuid.UUID
    name: str
    unit: str
    quantity: Decimal


@dataclass(frozen=True)
class StockRow:
    ingredient_id: uuid.UUID
    name: str
    unit: str
    on_hand: Decimal
    reserved: Decimal
    low_stock_threshold: Decimal | None
    is_test_fixture: bool
    updated_at: datetime
    used_in: list[str]


@dataclass(frozen=True)
class ReservationRow:
    id: uuid.UUID
    ingredient_id: uuid.UUID
    quantity: Decimal


_STOCK = """
    SELECT s.ingredient_id, i.name, i.unit, s.on_hand, s.reserved, s.low_stock_threshold, s.is_test_fixture,
           s.updated_at,
           -- Dishes whose ACTIVE recipe uses the ingredient (KI-23, read only).
           coalesce((SELECT array_agg(DISTINCT m.name ORDER BY m.name)
                       FROM app.recipe_ingredients ri
                       JOIN app.recipe_versions v ON v.id = ri.recipe_version_id AND v.status = 'ACTIVE'
                       JOIN app.menu_items m ON m.recipe_id = v.recipe_id AND m.kitchen_id = s.kitchen_id
                      WHERE ri.ingredient_id = s.ingredient_id), '{}') AS used_in
      FROM app.ingredient_stock s JOIN app.ingredients i ON i.id = s.ingredient_id
"""


def requirements(conn: Connection, order_id: uuid.UUID) -> list[Requirement]:
    """Total quantity per ingredient for the order's pinned recipe versions, in ingredient order."""
    rows = conn.execute(
        text(
            "SELECT ri.ingredient_id, i.name, i.unit, sum(ri.quantity * oi.quantity) "
            "FROM app.order_items oi "
            "JOIN app.recipe_ingredients ri ON ri.recipe_version_id = oi.recipe_version_id "
            "JOIN app.ingredients i ON i.id = ri.ingredient_id WHERE oi.order_id = :o "
            "GROUP BY ri.ingredient_id, i.name, i.unit ORDER BY ri.ingredient_id"
        ),
        {"o": order_id},
    ).all()
    return [Requirement(r[0], r[1], r[2], Decimal(r[3])) for r in rows]


def lock_stock(
    conn: Connection, kitchen_id: uuid.UUID, ingredient_ids: list[uuid.UUID]
) -> dict[uuid.UUID, StockRow]:
    """Lock the rows in ingredient order, so concurrent reservations never deadlock."""
    rows = conn.execute(
        text(
            _STOCK + " WHERE s.kitchen_id = :k AND s.ingredient_id = ANY(:ids) "
            "ORDER BY s.ingredient_id FOR UPDATE OF s"
        ),
        {"k": kitchen_id, "ids": ingredient_ids},
    ).all()
    return {r[0]: StockRow(*r) for r in rows}


def stock(conn: Connection, kitchen_id: uuid.UUID) -> list[StockRow]:
    rows = conn.execute(text(_STOCK + " WHERE s.kitchen_id = :k ORDER BY i.name"), {"k": kitchen_id}).all()
    return [StockRow(*r) for r in rows]


def change_stock(
    conn: Connection, kitchen_id: uuid.UUID, ingredient_id: uuid.UUID, *, on_hand: Decimal, reserved: Decimal
) -> None:
    """Relative change; the table's checks refuse negative stock or reservations above stock."""
    conn.execute(
        text(
            "UPDATE app.ingredient_stock SET on_hand = on_hand + :oh, reserved = reserved + :rs "
            "WHERE kitchen_id = :k AND ingredient_id = :i"
        ),
        {"oh": on_hand, "rs": reserved, "k": kitchen_id, "i": ingredient_id},
    )


def set_threshold(
    conn: Connection, kitchen_id: uuid.UUID, ingredient_id: uuid.UUID, threshold: Decimal | None
) -> None:
    conn.execute(
        text(
            "UPDATE app.ingredient_stock SET low_stock_threshold = :t "
            "WHERE kitchen_id = :k AND ingredient_id = :i"
        ),
        {"t": threshold, "k": kitchen_id, "i": ingredient_id},
    )


def insert_reservation(
    conn: Connection, order_id: uuid.UUID, kitchen_id: uuid.UUID, ingredient_id: uuid.UUID, quantity: Decimal
) -> None:
    conn.execute(
        text(
            "INSERT INTO app.stock_reservations (order_id, kitchen_id, ingredient_id, quantity, status) "
            "VALUES (:o, :k, :i, :q, 'RESERVED')"
        ),
        {"o": order_id, "k": kitchen_id, "i": ingredient_id, "q": quantity},
    )


def open_reservations(conn: Connection, order_id: uuid.UUID) -> list[ReservationRow]:
    rows = conn.execute(
        text(
            "SELECT id, ingredient_id, quantity FROM app.stock_reservations "
            "WHERE order_id = :o AND status = 'RESERVED' ORDER BY ingredient_id FOR UPDATE"
        ),
        {"o": order_id},
    ).all()
    return [ReservationRow(r[0], r[1], Decimal(r[2])) for r in rows]


def set_reservation_status(conn: Connection, reservation_id: uuid.UUID, status: str) -> None:
    conn.execute(
        text("UPDATE app.stock_reservations SET status = :s WHERE id = :id"),
        {"s": status, "id": reservation_id},
    )


def insert_movement(
    conn: Connection,
    *,
    kitchen_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    delta: Decimal,
    kind: str,
    order_id: uuid.UUID | None,
    reason: str | None,
    actor_user_id: uuid.UUID | None,
    actor_role: str,
) -> None:
    conn.execute(
        text(
            "INSERT INTO app.stock_movements (kitchen_id, ingredient_id, delta, kind, order_id, reason, "
            "actor_user_id, actor_role) VALUES (:k, :i, :d, :kind, :o, :r, :u, :role)"
        ),
        {
            "k": kitchen_id,
            "i": ingredient_id,
            "d": delta,
            "kind": kind,
            "o": order_id,
            "r": reason,
            "u": actor_user_id,
            "role": actor_role,
        },
    )
