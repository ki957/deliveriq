"""SQL for coupons. Parameterised; callers own the transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import Connection, text

from app.modules.pricing.domain import Coupon

_COLUMNS = (
    "id, code, discount_paise, min_food_subtotal_paise, usage_limit, used_count, valid_from, valid_until, "
    "is_active, is_test_fixture"
)


def find_coupon(conn: Connection, code: str, *, lock: bool = False) -> Coupon | None:
    sql = f"SELECT {_COLUMNS} FROM app.coupons WHERE code = :c"  # noqa: S608 - fixed SQL
    row = conn.execute(text(sql + (" FOR UPDATE" if lock else "")), {"c": code}).first()
    return Coupon(*row) if row else None


def increment_use(conn: Connection, coupon_id: uuid.UUID) -> bool:
    """Atomic: never exceeds the usage limit even under concurrent checkouts."""
    updated = conn.execute(
        text(
            "UPDATE app.coupons SET used_count = used_count + 1 WHERE id = :id "
            "AND (usage_limit IS NULL OR used_count < usage_limit)"
        ),
        {"id": coupon_id},
    ).rowcount
    return bool(updated)
