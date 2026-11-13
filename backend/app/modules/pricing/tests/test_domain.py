"""Price protection, coupon rules and the bill (CU-12–CU-16; DDR-38, DDR-53, DDR-110)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.modules.pricing.domain import Coupon, bill, charge_price, coupon_problem

pytestmark = pytest.mark.unit
NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("minutes_ago", "expected"),
    [(0, 11100), (29, 11100), (30, 11100), (31, 12000)],
)
def test_price_is_protected_for_30_minutes_after_adding(minutes_ago: int, expected: int) -> None:
    added = NOW - timedelta(minutes=minutes_ago)
    charged = charge_price(
        current_price_paise=12000, cart_price_paise=11100, added_at=added, now=NOW, window_minutes=30
    )
    assert charged == expected


def test_without_a_cart_line_the_current_price_applies() -> None:
    assert (
        charge_price(
            current_price_paise=12000, cart_price_paise=None, added_at=None, now=NOW, window_minutes=30
        )
        == 12000
    )


@pytest.mark.parametrize(("subtotal", "met"), [(49900, False), (50000, True)])
def test_minimum_is_on_the_food_subtotal(subtotal: int, met: bool) -> None:
    """₹499 rejected, ₹500 accepted (plan Task 6)."""
    assert (
        bill(
            food_subtotal_paise=subtotal, minimum_paise=50000, delivery_fee_paise=3000, discount_paise=0
        ).minimum_met
        is met
    )


def test_coupon_may_take_the_payable_below_500_and_the_fee_always_applies() -> None:
    b = bill(food_subtotal_paise=50000, minimum_paise=50000, delivery_fee_paise=3000, discount_paise=5000)
    assert (b.minimum_met, b.delivery_fee_paise, b.payable_paise) == (True, 3000, 48000)  # DDR-53, DDR-38
    assert (
        bill(food_subtotal_paise=100, minimum_paise=0, delivery_fee_paise=0, discount_paise=500).payable_paise
        == 0
    )
    assert "include" in b.tax_note  # DDR-110 (4): no invented tax breakdown


BASE = Coupon(
    id=uuid.uuid4(),
    code="TEST50",
    discount_paise=5000,
    min_food_subtotal_paise=0,
    usage_limit=None,
    used_count=0,
    valid_from=None,
    valid_until=None,
    is_active=True,
    is_test_fixture=True,
)


def coupon(**overrides: Any) -> Coupon:
    return replace(BASE, **overrides)


def problem(
    c: Coupon | None, *, subtotal: int = 50000, fixture: bool = True, production: bool = False
) -> str | None:
    return coupon_problem(
        c, food_subtotal_paise=subtotal, order_is_fixture=fixture, production=production, now=NOW
    )


def test_coupon_rules() -> None:
    assert problem(coupon()) is None
    assert problem(None) == "coupon_unknown"
    assert problem(coupon(is_active=False)) == "coupon_inactive"
    assert problem(coupon(valid_from=NOW + timedelta(days=1))) == "coupon_not_started"
    assert problem(coupon(valid_until=NOW)) == "coupon_expired"
    assert problem(coupon(usage_limit=3, used_count=3)) == "coupon_used_up"
    assert problem(coupon(min_food_subtotal_paise=60000)) == "coupon_minimum"


def test_test_coupons_only_on_test_orders_and_never_in_production() -> None:
    assert problem(coupon(), fixture=False) == "coupon_not_for_order"
    assert problem(coupon(), production=True) == "coupon_unknown"
    real = coupon(code="REAL10", is_test_fixture=False)
    assert problem(real, fixture=True) == "coupon_not_for_order"
    assert problem(real, fixture=False) is None
