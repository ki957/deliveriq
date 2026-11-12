"""Recipe version lifecycle and release sign-offs (DDR-09, DDR-10, DDR-13, DDR-50, DDR-54; #13).

Standard library only. Mirrored in PostgreSQL (migrations 0002-0003).
"""

from __future__ import annotations

from enum import StrEnum


class RecipeStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_VALIDATION = "PENDING_VALIDATION"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    DISABLED = "DISABLED"
    QUARANTINED_DUPLICATE_CANDIDATE = "QUARANTINED_DUPLICATE_CANDIDATE"


class SignoffType(StrEnum):
    """The five #13 release-checklist sign-offs: required audit records, not activation."""

    CHEF = "CHEF"
    FOOD_SAFETY_LEAD = "FOOD_SAFETY_LEAD"
    INVENTORY_OWNER = "INVENTORY_OWNER"
    KITCHEN_MANAGER = "KITCHEN_MANAGER"
    PRODUCT_OWNER = "PRODUCT_OWNER"


R = RecipeStatus
RECIPE_INITIAL = frozenset({R.DRAFT, R.QUARANTINED_DUPLICATE_CANDIDATE})
RECIPE_TRANSITIONS = frozenset(
    {
        (R.DRAFT, R.PENDING_VALIDATION),
        (R.PENDING_VALIDATION, R.DRAFT),
        (R.PENDING_VALIDATION, R.VALIDATED),
        (R.VALIDATED, R.ACTIVE),
        (R.VALIDATED, R.REJECTED),
        (R.ACTIVE, R.SUPERSEDED),
        (R.ACTIVE, R.DISABLED),
    }
)
# Quarantined records have no way out until the owner decides (DDR-13, DDR-35 open).
REQUIRED_SIGNOFFS = frozenset(SignoffType)
ACTIVATION_ROLE = "KITCHEN_MANAGER"  # DDR-10 / DDR-30


def can_transition(current: RecipeStatus, target: RecipeStatus) -> bool:
    return (current, target) in RECIPE_TRANSITIONS


def missing_signoffs(recorded: set[SignoffType]) -> frozenset[SignoffType]:
    return REQUIRED_SIGNOFFS - recorded


def can_activate(current: RecipeStatus, recorded: set[SignoffType], is_test_fixture: bool) -> bool:
    """VALIDATED → ACTIVE needs all five sign-offs; no SOP recipe is activated in the POC (DDR-50)."""
    return can_transition(current, R.ACTIVE) and not missing_signoffs(recorded) and is_test_fixture
