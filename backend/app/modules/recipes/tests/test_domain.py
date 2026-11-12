from __future__ import annotations

import pytest

from app.modules.recipes.domain import (
    RECIPE_TRANSITIONS,
    RecipeStatus,
    SignoffType,
    can_activate,
    can_transition,
    missing_signoffs,
)

pytestmark = pytest.mark.unit
R = RecipeStatus
ALL = set(SignoffType)


def test_exactly_five_signoff_types() -> None:
    assert len(SignoffType) == 5


def test_activation_needs_validated_five_signoffs_and_test_fixture() -> None:
    assert can_activate(R.VALIDATED, ALL, is_test_fixture=True)
    assert not can_activate(R.VALIDATED, ALL - {SignoffType.PRODUCT_OWNER}, is_test_fixture=True)
    assert not can_activate(R.DRAFT, ALL, is_test_fixture=True)
    # DDR-50: no SOP recipe is ever activated in the POC.
    assert not can_activate(R.VALIDATED, ALL, is_test_fixture=False)


def test_missing_signoffs_lists_what_is_absent() -> None:
    assert missing_signoffs({SignoffType.CHEF}) == ALL - {SignoffType.CHEF}


def test_quarantined_has_no_exit() -> None:
    assert not any(a == R.QUARANTINED_DUPLICATE_CANDIDATE for a, _ in RECIPE_TRANSITIONS)


def test_return_to_draft_only_from_pending_validation() -> None:
    assert can_transition(R.PENDING_VALIDATION, R.DRAFT)
    assert [a for a, b in RECIPE_TRANSITIONS if b == R.DRAFT] == [R.PENDING_VALIDATION]


def test_workflow_actions_follow_ddr_10() -> None:
    from app.modules.recipes.domain import ACTIONS, action_target

    assert {a: (f.value, t.value) for a, (f, t) in ACTIONS.items()} == {
        "submit": ("DRAFT", "PENDING_VALIDATION"),
        "return": ("PENDING_VALIDATION", "DRAFT"),
        "validate": ("PENDING_VALIDATION", "VALIDATED"),
        "reject": ("VALIDATED", "REJECTED"),
        "activate": ("VALIDATED", "ACTIVE"),
    }
    assert all(can_transition(f, t) for f, t in ACTIONS.values())
    assert action_target("activate", R.PENDING_VALIDATION) is None
    assert action_target("submit", R.QUARANTINED_DUPLICATE_CANDIDATE) is None  # DDR-13: no way out
    assert action_target("unknown", R.DRAFT) is None


def test_signoff_authority_matches_ddr_54_and_106() -> None:
    from app.modules.recipes.domain import CA_SIGNOFFS, KM_SIGNOFFS

    assert KM_SIGNOFFS | CA_SIGNOFFS == ALL
    assert not KM_SIGNOFFS & CA_SIGNOFFS
    assert {SignoffType.PRODUCT_OWNER} == CA_SIGNOFFS
