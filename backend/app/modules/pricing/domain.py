"""Price protection, coupon rules and the bill (#1 §8–9; CU-12–CU-17; DDR-38, DDR-53, DDR-110).

Standard library only. Money is integer paise; prices are tax-inclusive (CU-15).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

TAX_NOTE = "Prices include applicable taxes."  # DDR-110 (4): no breakdown until DDR-32


# ---------------------------------------------------------------- price protection (DDR-110 (5))
def charge_price(
    *,
    current_price_paise: int,
    cart_price_paise: int | None,
    added_at: datetime | None,
    now: datetime,
    window_minutes: int,
) -> int:
    """The price charged now: the cart price while protected, otherwise the current published price."""
    if (
        cart_price_paise is not None
        and added_at is not None
        and now - added_at <= timedelta(minutes=window_minutes)
    ):
        return cart_price_paise
    return current_price_paise


def protected_until(added_at: datetime, window_minutes: int) -> datetime:
    return added_at + timedelta(minutes=window_minutes)


@dataclass(frozen=True)
class PriceChange:
    menu_item_id: uuid.UUID
    stated_price_paise: int
    current_price_paise: int


# ---------------------------------------------------------------- coupons (CU-16, DDR-53, DDR-110 (3))
@dataclass(frozen=True)
class Coupon:
    id: uuid.UUID
    code: str
    discount_paise: int
    min_food_subtotal_paise: int
    usage_limit: int | None
    used_count: int
    valid_from: datetime | None
    valid_until: datetime | None
    is_active: bool
    is_test_fixture: bool


COUPON_MESSAGES = {
    "coupon_unknown": "This coupon code is not valid.",
    "coupon_inactive": "This coupon is not active.",
    "coupon_not_started": "This coupon is not valid yet.",
    "coupon_expired": "This coupon has expired.",
    "coupon_used_up": "This coupon has reached its usage limit.",
    "coupon_minimum": "The food subtotal is below this coupon's minimum.",
    "coupon_not_for_order": "This coupon cannot be used with these dishes.",
}


def coupon_problem(
    coupon: Coupon | None,
    *,
    food_subtotal_paise: int,
    order_is_fixture: bool,
    production: bool,
    now: datetime,
) -> str | None:
    """None when the coupon applies; otherwise a code from COUPON_MESSAGES."""
    if coupon is None:
        return "coupon_unknown"
    if coupon.is_test_fixture and (production or not order_is_fixture):
        # TEST coupons only on TEST orders, never in production (plan §5.2).
        return "coupon_unknown" if production else "coupon_not_for_order"
    if not coupon.is_test_fixture and order_is_fixture:
        return "coupon_not_for_order"
    if not coupon.is_active:
        return "coupon_inactive"
    if coupon.valid_from is not None and now < coupon.valid_from:
        return "coupon_not_started"
    if coupon.valid_until is not None and now >= coupon.valid_until:
        return "coupon_expired"
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        return "coupon_used_up"
    if food_subtotal_paise < coupon.min_food_subtotal_paise:
        return "coupon_minimum"
    return None


# ---------------------------------------------------------------- bill (CU-12, CU-15, DDR-38, DDR-53)
@dataclass(frozen=True)
class Bill:
    food_subtotal_paise: int
    minimum_food_subtotal_paise: int
    minimum_met: bool
    delivery_fee_paise: int
    discount_paise: int
    payable_paise: int
    tax_note: str = TAX_NOTE


def bill(
    *, food_subtotal_paise: int, minimum_paise: int, delivery_fee_paise: int, discount_paise: int
) -> Bill:
    """The ₹500 minimum is checked on the food subtotal before any coupon; a coupon may take the payable
    total below ₹500 (DDR-53), never below zero. The ₹30 fee applies at every subtotal (DDR-38)."""
    return Bill(
        food_subtotal_paise=food_subtotal_paise,
        minimum_food_subtotal_paise=minimum_paise,
        minimum_met=food_subtotal_paise >= minimum_paise,
        delivery_fee_paise=delivery_fee_paise,
        discount_paise=discount_paise,
        payable_paise=max(food_subtotal_paise + delivery_fee_paise - discount_paise, 0),
    )
