"""SQL for simulated payments. Parameterised; callers own the transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Connection, text


@dataclass(frozen=True)
class PaymentRow:
    id: uuid.UUID
    order_id: uuid.UUID
    method: str
    status: str
    amount_paise: int | None
    sim_reference: str | None
    is_test_fixture: bool
    created_at: datetime
    updated_at: datetime


_COLUMNS = (
    "id, order_id, method, status, amount_paise, sim_reference, is_test_fixture, created_at, updated_at"
)


def insert(
    conn: Connection, order_id: uuid.UUID, method: str, status: str, amount_paise: int, sim_reference: str
) -> uuid.UUID:
    payment_id: uuid.UUID = conn.execute(
        text(
            "INSERT INTO app.payments (order_id, method, status, amount_paise, sim_reference) "
            "VALUES (:o, :m, :s, :a, :r) RETURNING id"
        ),
        {"o": order_id, "m": method, "s": status, "a": amount_paise, "r": sim_reference},
    ).scalar_one()
    return payment_id


def for_order(conn: Connection, order_id: uuid.UUID, *, lock: bool = False) -> PaymentRow | None:
    sql = f"SELECT {_COLUMNS} FROM app.payments WHERE order_id = :o"  # noqa: S608 - fixed SQL
    row = conn.execute(text(sql + (" FOR UPDATE" if lock else "")), {"o": order_id}).first()
    return PaymentRow(**row._mapping) if row else None


def set_status(conn: Connection, payment_id: uuid.UUID, status: str) -> None:
    conn.execute(text("UPDATE app.payments SET status = :s WHERE id = :id"), {"s": status, "id": payment_id})
