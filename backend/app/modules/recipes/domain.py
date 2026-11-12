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


# Workflow actions executed by the Kitchen Manager (DDR-10, DDR-107): action -> (from, to).
ACTIONS: dict[str, tuple[RecipeStatus, RecipeStatus]] = {
    "submit": (R.DRAFT, R.PENDING_VALIDATION),
    "return": (R.PENDING_VALIDATION, R.DRAFT),
    "validate": (R.PENDING_VALIDATION, R.VALIDATED),
    "reject": (R.VALIDATED, R.REJECTED),
    "activate": (R.VALIDATED, R.ACTIVE),
}
# Who records which sign-off (DDR-54, DDR-106): the KM four, a CA account the product-owner one.
KM_SIGNOFFS = frozenset(
    {SignoffType.CHEF, SignoffType.FOOD_SAFETY_LEAD, SignoffType.INVENTORY_OWNER, SignoffType.KITCHEN_MANAGER}
)
CA_SIGNOFFS = frozenset({SignoffType.PRODUCT_OWNER})
# Sign-offs are recorded during validation, before activation; TEST recipes only (DDR-54).
SIGNOFF_STATUSES = frozenset({R.PENDING_VALIDATION, R.VALIDATED})


def action_target(action: str, current: RecipeStatus) -> RecipeStatus | None:
    """The status an action leads to from `current`, or None if the action does not apply."""
    step = ACTIONS.get(action)
    if step is None or step[0] != current:
        return None
    return step[1]
