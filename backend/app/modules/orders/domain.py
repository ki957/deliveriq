"""Order fulfilment and item preparation state machines (Matrix §7.1–7.2, DDR-16, DDR-17).

Pure domain code: standard library only. The same transitions are enforced in PostgreSQL
(migration 0003); a test asserts both definitions are identical.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

# DDR-38: flat ₹30 per order, no waiver or free-delivery threshold. Integer paise.
DELIVERY_FEE_PAISE = 3000
SPECIAL_INSTRUCTIONS_MAX = 250  # DDR-07


class Fulfilment(StrEnum):
    PLACED = "PLACED"
    PENDING_KITCHEN = "PENDING_KITCHEN"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    PICKED_UP = "PICKED_UP"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    DELIVERY_FAILED = "DELIVERY_FAILED"


class ItemPrep(StrEnum):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"


F = Fulfilment
FULFILMENT_INITIAL = frozenset({F.PLACED})
FULFILMENT_TRANSITIONS = frozenset(
    {
        (F.PLACED, F.PENDING_KITCHEN),
        (F.PLACED, F.CANCELLED),
        (F.PENDING_KITCHEN, F.ACCEPTED),
        (F.PENDING_KITCHEN, F.REJECTED),
        (F.PENDING_KITCHEN, F.CANCELLED),
        (F.ACCEPTED, F.PREPARING),
        (F.PREPARING, F.READY_FOR_PICKUP),
        (F.READY_FOR_PICKUP, F.PICKED_UP),
        (F.PICKED_UP, F.OUT_FOR_DELIVERY),
        (F.OUT_FOR_DELIVERY, F.DELIVERED),
        (F.OUT_FOR_DELIVERY, F.DELIVERY_FAILED),
    }
)
FULFILMENT_TERMINAL = frozenset({F.DELIVERED, F.CANCELLED, F.REJECTED, F.DELIVERY_FAILED})

ITEM_INITIAL = frozenset({ItemPrep.PENDING})
ITEM_TRANSITIONS = frozenset(
    {(ItemPrep.PENDING, ItemPrep.PREPARING), (ItemPrep.PREPARING, ItemPrep.PREPARED)}
)


def can_fulfil(current: Fulfilment, target: Fulfilment) -> bool:
    return (current, target) in FULFILMENT_TRANSITIONS


def can_prepare(current: ItemPrep, target: ItemPrep) -> bool:
    return (current, target) in ITEM_TRANSITIONS


# ---------------------------------------------------- display mapping (Matrix §7.3, DDR-16, DDR-17)
@dataclass(frozen=True)
class DisplayLabels:
    """Per-portal labels. None = not shown in that portal ("—" in the Matrix)."""

    customer: str
    kitchen: str | None
    delivery: str | None
    management: str
    # Derived from the assignment machine; never changes the fulfilment status (DDR-16).
    agent_assigned: bool


# (customer, kitchen, delivery, management) for each fulfilment status, without an accepted assignment.
_LABELS: dict[Fulfilment, tuple[str, str | None, str | None, str]] = {
    F.PLACED: ("Order placed", None, None, "Placed"),
    F.PENDING_KITCHEN: ("Awaiting kitchen acceptance", "Incoming", None, "Awaiting kitchen"),
    F.ACCEPTED: ("Accepted", "Accepted", None, "Accepted"),
    F.PREPARING: ("Preparing", "Preparing", None, "Preparing"),
    F.READY_FOR_PICKUP: ("Ready for pickup", "Ready for Pickup", None, "Ready"),
    F.PICKED_UP: ("Picked up", "Handed Over", "Picked up", "Picked up"),
    F.OUT_FOR_DELIVERY: ("Out for delivery", "Handed Over", "In transit", "Out for delivery"),
    F.DELIVERED: ("Delivered", "Handed Over", "Delivered", "Delivered"),
    F.CANCELLED: ("Cancelled", "Cancelled", None, "Cancelled"),
    F.REJECTED: ("Rejected", "Rejected", None, "Rejected"),
    F.DELIVERY_FAILED: ("Delivery failed", "Handed Over", "Failed", "Delivery failed"),
}
# An accepted assignment is shown while the kitchen still has the order (Matrix §7.3 row 6).
AGENT_ASSIGNED_STATUSES = frozenset({F.ACCEPTED, F.PREPARING, F.READY_FOR_PICKUP})


def display(status: Fulfilment, assignment_accepted: bool) -> DisplayLabels:
    customer, kitchen, delivery, management = _LABELS[status]
    if assignment_accepted and status in AGENT_ASSIGNED_STATUSES:
        # Customer and kitchen keep the fulfilment label (the kitchen card shows the agent).
        return DisplayLabels(customer, kitchen, "Go to kitchen", "Agent assigned", agent_assigned=True)
    return DisplayLabels(customer, kitchen, delivery, management, agent_assigned=False)


# ---------------------------------------------------------------- checkout idempotency (DDR-109)
def request_hash(lines: list[tuple[str, int]], payment_method: str, special_instructions: str | None) -> str:
    """Stable fingerprint of a placement request: same key + different request is a conflict."""
    canonical = {
        "lines": sorted([menu_item_id, quantity] for menu_item_id, quantity in lines),
        "payment_method": payment_method,
        "special_instructions": special_instructions or "",
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
