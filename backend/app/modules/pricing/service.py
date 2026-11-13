"""Coupons and checkout amounts (CU-12–CU-16; DDR-38, DDR-53, DDR-110).

Functions take the caller's connection: the orders service owns the checkout transaction, so a coupon
use and its order commit together or not at all.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Connection, text

from app.modules.pricing import domain as d
from app.modules.pricing import repository as repo
from app.shared import config_values

Coupon = d.Coupon
Bill = d.Bill


class CouponRefused(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(d.COUPON_MESSAGES[code])
        self.code = code


def now(conn: Connection) -> datetime:
    """Database time, so price-protection windows compare against the same clock as `added_at`."""
    value: datetime = conn.execute(text("SELECT now()")).scalar_one()
    return value


def protection_minutes(conn: Connection) -> int:
    return int(config_values.value(conn, "PRICE_PROTECTION_MINUTES"))


def minimum_paise(conn: Connection, kitchen_id: uuid.UUID) -> int:
    return int(config_values.value(conn, "MINIMUM_FOOD_SUBTOTAL", kitchen_id=kitchen_id))


def delivery_fee_paise(conn: Connection, kitchen_id: uuid.UUID) -> int:
    return int(config_values.value(conn, "DELIVERY_FEE_FLAT", kitchen_id=kitchen_id))


def coupon(
    conn: Connection,
    code: str,
    *,
    food_subtotal_paise: int,
    order_is_fixture: bool,
    production: bool,
    lock: bool = False,
) -> d.Coupon:
    found = repo.find_coupon(conn, code.strip().upper(), lock=lock)
    problem = d.coupon_problem(
        found,
        food_subtotal_paise=food_subtotal_paise,
        order_is_fixture=order_is_fixture,
        production=production,
        now=now(conn),
    )
    if problem is not None or found is None:
        raise CouponRefused(problem or "coupon_unknown")
    return found


def redeem(conn: Connection, found: d.Coupon) -> None:
    """Count one use; refused if a concurrent checkout took the last one."""
    if not repo.increment_use(conn, found.id):
        raise CouponRefused("coupon_used_up")
