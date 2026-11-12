from __future__ import annotations

from itertools import pairwise

import pytest

from app.modules.orders.domain import (
    FULFILMENT_TERMINAL,
    FULFILMENT_TRANSITIONS,
    Fulfilment,
    ItemPrep,
    can_fulfil,
    can_prepare,
)

pytestmark = pytest.mark.unit
F = Fulfilment

HAPPY_PATH = [
    F.PLACED,
    F.PENDING_KITCHEN,
    F.ACCEPTED,
    F.PREPARING,
    F.READY_FOR_PICKUP,
    F.PICKED_UP,
    F.OUT_FOR_DELIVERY,
    F.DELIVERED,
]


def test_happy_path_is_allowed() -> None:
    assert all(can_fulfil(a, b) for a, b in pairwise(HAPPY_PATH))


@pytest.mark.parametrize("terminal", sorted(FULFILMENT_TERMINAL))
def test_terminal_states_have_no_exits(terminal: Fulfilment) -> None:
    assert not any(a == terminal for a, _ in FULFILMENT_TRANSITIONS)


def test_no_cancellation_after_acceptance() -> None:
    # CU-19: cancellation only before kitchen acceptance.
    assert can_fulfil(F.PENDING_KITCHEN, F.CANCELLED)
    for state in (F.ACCEPTED, F.PREPARING, F.READY_FOR_PICKUP, F.PICKED_UP, F.OUT_FOR_DELIVERY):
        assert not can_fulfil(state, F.CANCELLED)


def test_pickup_only_from_ready() -> None:
    # KI-08: pickup is blocked until Ready.
    assert [a for a, b in FULFILMENT_TRANSITIONS if b == F.PICKED_UP] == [F.READY_FOR_PICKUP]


def test_out_for_delivery_only_after_pickup() -> None:
    # DDR-16: never entered because of assignment.
    assert [a for a, b in FULFILMENT_TRANSITIONS if b == F.OUT_FOR_DELIVERY] == [F.PICKED_UP]


def test_item_preparation_is_linear() -> None:
    assert can_prepare(ItemPrep.PENDING, ItemPrep.PREPARING)
    assert can_prepare(ItemPrep.PREPARING, ItemPrep.PREPARED)
    assert not can_prepare(ItemPrep.PENDING, ItemPrep.PREPARED)
    assert not can_prepare(ItemPrep.PREPARED, ItemPrep.PENDING)
