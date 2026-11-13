from __future__ import annotations

from itertools import pairwise

import pytest

from app.modules.orders.domain import (
    DELIVERY_FEE_PAISE,
    FULFILMENT_TERMINAL,
    FULFILMENT_TRANSITIONS,
    Fulfilment,
    ItemPrep,
    can_fulfil,
    can_prepare,
    display,
    request_hash,
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


# ---------------------------------------------------------------- display mapping (Matrix §7.3)

# (status, customer, kitchen, delivery, management) — copied from PORTAL_REQUIREMENTS_MATRIX.md §7.3;
# "—" in the Matrix is None, "Cancelled (if seen)" is shown as "Cancelled".
MATRIX = [
    ("PLACED", "Order placed", None, None, "Placed"),
    ("PENDING_KITCHEN", "Awaiting kitchen acceptance", "Incoming", None, "Awaiting kitchen"),
    ("ACCEPTED", "Accepted", "Accepted", None, "Accepted"),
    ("PREPARING", "Preparing", "Preparing", None, "Preparing"),
    ("READY_FOR_PICKUP", "Ready for pickup", "Ready for Pickup", None, "Ready"),
    ("PICKED_UP", "Picked up", "Handed Over", "Picked up", "Picked up"),
    ("OUT_FOR_DELIVERY", "Out for delivery", "Handed Over", "In transit", "Out for delivery"),
    ("DELIVERED", "Delivered", "Handed Over", "Delivered", "Delivered"),
    ("CANCELLED", "Cancelled", "Cancelled", None, "Cancelled"),
    ("REJECTED", "Rejected", "Rejected", None, "Rejected"),
    ("DELIVERY_FAILED", "Delivery failed", "Handed Over", "Failed", "Delivery failed"),
]


@pytest.mark.parametrize(("status", "customer", "kitchen", "delivery", "management"), MATRIX)
def test_labels_match_the_matrix_without_assignment(
    status: str, customer: str, kitchen: str | None, delivery: str | None, management: str
) -> None:
    labels = display(Fulfilment(status), assignment_accepted=False)
    assert (labels.customer, labels.kitchen, labels.delivery, labels.management) == (
        customer,
        kitchen,
        delivery,
        management,
    )
    assert labels.agent_assigned is False


def test_every_status_has_labels() -> None:
    assert {row[0] for row in MATRIX} == {s.value for s in Fulfilment}


@pytest.mark.parametrize("status", ["ACCEPTED", "PREPARING", "READY_FOR_PICKUP"])
def test_agent_assigned_keeps_the_fulfilment_label(status: str) -> None:
    """DDR-16: the customer label is unchanged, plus the indicator; Delivery sees 'Go to kitchen'."""
    plain = display(Fulfilment(status), assignment_accepted=False)
    assigned = display(Fulfilment(status), assignment_accepted=True)
    assert assigned.customer == plain.customer and assigned.kitchen == plain.kitchen
    assert assigned.agent_assigned is True
    assert (assigned.delivery, assigned.management) == ("Go to kitchen", "Agent assigned")


@pytest.mark.parametrize(
    "status", ["PLACED", "PENDING_KITCHEN", "PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED"]
)
def test_indicator_only_while_the_kitchen_has_the_order(status: str) -> None:
    assert display(Fulfilment(status), assignment_accepted=True).agent_assigned is False


def test_delivery_fee_is_flat_30_rupees() -> None:
    assert DELIVERY_FEE_PAISE == 3000  # DDR-38


def test_request_hash_ignores_line_order_but_not_content() -> None:
    a = request_hash([("x", 1), ("y", 2)], "COD", None)
    assert a == request_hash([("y", 2), ("x", 1)], "COD", "")
    assert a != request_hash([("x", 1), ("y", 3)], "COD", None)
    assert a != request_hash([("x", 1), ("y", 2)], "SIM_UPI", None)
    assert a != request_hash([("x", 1), ("y", 2)], "COD", "no onion")
