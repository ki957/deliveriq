"""Kitchen modes and capacity (#4 §3; KI-12–KI-14; DDR-111 (1)–(3)). Standard library only.

Capacity counts the orders the kitchen holds (ACCEPTED, PREPARING, READY_FOR_PICKUP). Normal uses the
normal capacity, Busy the lower Busy capacity, and Paused accepts nothing new. Accepted orders always
continue (KI-14). The same rule refuses checkout, so customers are not left waiting (KI-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class KitchenMode(StrEnum):
    NORMAL = "NORMAL"
    BUSY = "BUSY"
    PAUSED = "PAUSED"


# Input-size guard for configured capacities; the values themselves stay DDR-42 test defaults.
CAPACITY_MIN = 1
CAPACITY_MAX = 50
REASON_MAX = 500

# Stable refusal codes, shared by checkout (422) and kitchen acceptance (409).
REFUSAL_PAUSED = "kitchen_paused"
REFUSAL_AT_CAPACITY = "kitchen_at_capacity"


@dataclass(frozen=True)
class Intake:
    mode: KitchenMode
    # None while Paused: no new order is accepted.
    capacity: int | None
    active: int
    refusal: str | None

    @property
    def accepting(self) -> bool:
        return self.refusal is None


def intake(mode: KitchenMode, *, capacity: int | None, active: int) -> Intake:
    """`capacity` is the active mode's capacity (normal or Busy); ignored while Paused."""
    if mode is KitchenMode.PAUSED or capacity is None:
        return Intake(mode, None, active, REFUSAL_PAUSED)
    return Intake(mode, capacity, active, REFUSAL_AT_CAPACITY if active >= capacity else None)


def capacity_error(normal_capacity: int, busy_capacity: int) -> str | None:
    """Busy is a lower (or equal) configured capacity (#4 §3); both within the input guard."""
    for value in (normal_capacity, busy_capacity):
        if not CAPACITY_MIN <= value <= CAPACITY_MAX:
            return f"Capacity must be between {CAPACITY_MIN} and {CAPACITY_MAX} orders"
    if busy_capacity > normal_capacity:
        return "Busy capacity cannot be higher than normal capacity"
    return None
