"""Delivery rules (DL-04, DL-11, DDR-52, DDR-113 (6), (8), (18))."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.delivery.domain import (
    Assignment,
    can_transition,
    codes_match,
    delivery_code,
    mask_phone,
    point_refusal,
)

pytestmark = pytest.mark.unit
NOW = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)


def test_delivery_code_is_six_digits_stable_and_secret_dependent() -> None:
    code = delivery_code("secret-a", "order-1", "n" * 48)
    assert len(code) == 6 and code.isdigit()
    assert code == delivery_code("secret-a", "order-1", "n" * 48)
    assert code != delivery_code("secret-b", "order-1", "n" * 48)  # the database alone cannot derive it
    assert code != delivery_code("secret-a", "order-1", "m" * 48)  # a new nonce = a new code
    assert codes_match(code, f" {code} ") and not codes_match(
        code, "000000" if code != "000000" else "111111"
    )


@pytest.mark.parametrize(
    ("recorded", "last", "why"),
    [
        (NOW - timedelta(seconds=5), None, None),
        (NOW - timedelta(seconds=121), None, "stale"),
        (NOW - timedelta(seconds=5), NOW - timedelta(seconds=5), "out_of_order"),
        (NOW - timedelta(seconds=10), NOW - timedelta(seconds=5), "out_of_order"),
        (NOW + timedelta(minutes=5), None, "future"),
    ],
)
def test_points_refused_when_stale_out_of_order_or_future(
    recorded: datetime, last: datetime | None, why: str | None
) -> None:
    assert point_refusal(recorded, now=NOW, last=last, stale_seconds=120) == why


def test_phone_is_masked_except_the_last_two_digits() -> None:
    assert mask_phone("+919876543210") == "+91********10"


def test_manager_may_return_a_failure_request_to_the_agent() -> None:
    assert can_transition(Assignment.FAILURE_REQUESTED, Assignment.ACCEPTED)
    assert can_transition(Assignment.FAILURE_REQUESTED, Assignment.FAILED)
    assert not can_transition(Assignment.FAILED, Assignment.ACCEPTED)
