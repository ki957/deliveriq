"""Stock rules (#4 §7.2; DDR-111 (1), (9))."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.inventory.domain import adjustment_error, available, is_low

pytestmark = pytest.mark.unit
D = Decimal


def test_available_is_on_hand_minus_reserved() -> None:
    assert available(D("10000"), D("700")) == D("9300")


def test_low_stock_needs_a_threshold_set_by_the_kitchen_manager() -> None:
    assert not is_low(D("0"), None)  # no threshold, no alert (no invented default)
    assert is_low(D("500"), D("500"))
    assert not is_low(D("501"), D("500"))


@pytest.mark.parametrize(
    ("on_hand", "reserved", "delta", "ok"),
    [("100", "0", "-100", True), ("100", "40", "-60", True), ("100", "40", "-61", False),
     ("100", "0", "0", False), ("0", "0", "250.5", True)],
)  # fmt: skip
def test_adjustments_never_go_below_reserved(on_hand: str, reserved: str, delta: str, ok: bool) -> None:
    assert (adjustment_error(D(on_hand), D(reserved), D(delta)) is None) is ok
