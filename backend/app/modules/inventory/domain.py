"""Stock rules (#4 §7; KI-21–KI-23; DDR-111 (4), (8), (9)). Standard library only.

Ingredient-level ledger without lots or expiry (DDR-18, KI-25). Quantities are in the ingredient's
own unit (g, ml or piece). Available = on hand minus reserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

REASON_MAX = 500
# Input-size guard for a single adjustment or threshold (not an operational limit).
QUANTITY_MAX = Decimal("1000000")
# Largest on-hand quantity the stock column holds (numeric(14, 3)).
ON_HAND_MAX = Decimal("99999999999.999")


@dataclass(frozen=True)
class Shortage:
    ingredient_name: str
    unit: str
    needed: Decimal
    available: Decimal


def available(on_hand: Decimal, reserved: Decimal) -> Decimal:
    return on_hand - reserved


def is_low(available_qty: Decimal, threshold: Decimal | None) -> bool:
    """Low only against a threshold the KM set; no threshold means no alert (DDR-111 (1))."""
    return threshold is not None and available_qty <= threshold


def adjustment_error(on_hand: Decimal, reserved: Decimal, delta: Decimal) -> str | None:
    """A signed adjustment may never take stock below what is reserved (DDR-111 (9))."""
    if delta == 0:
        return "The adjustment cannot be zero"
    if abs(delta) > QUANTITY_MAX:
        return f"An adjustment can be at most {QUANTITY_MAX}"
    if on_hand + delta < reserved:
        return "Stock cannot go below the quantity reserved for accepted orders"
    if on_hand + delta > ON_HAND_MAX:
        return "Stock would exceed the largest quantity that can be recorded"
    return None
