from __future__ import annotations

import pytest

from app.modules.menu.domain import MENU_TRANSITIONS, Publication, can_transition, is_test_name

pytestmark = pytest.mark.unit
M = Publication


def test_publish_path() -> None:
    assert can_transition(M.DRAFT, M.READY_FOR_PUBLICATION)
    assert can_transition(M.READY_FOR_PUBLICATION, M.PUBLISHED)
    assert not can_transition(M.DRAFT, M.PUBLISHED)


def test_availability_toggle_and_retirement() -> None:
    assert can_transition(M.PUBLISHED, M.TEMPORARILY_UNAVAILABLE)
    assert can_transition(M.TEMPORARILY_UNAVAILABLE, M.PUBLISHED)
    assert can_transition(M.PUBLISHED, M.RETIRED)
    assert not any(a == M.RETIRED for a, _ in MENU_TRANSITIONS)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("TEST – Paneer", True), ("TEST - Paneer", False), ("Paneer", False), ("test – paneer", False)],
)
def test_test_prefix_uses_exact_en_dash(name: str, expected: bool) -> None:
    assert is_test_name(name) is expected
