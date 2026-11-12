from __future__ import annotations

import pytest

from app.modules.delivery.domain import (
    ACTIVE_FOR_AGENT,
    ASSIGNMENT_TRANSITIONS,
    SHOWS_AGENT_ASSIGNED,
    Assignment,
    can_transition,
)

pytestmark = pytest.mark.unit
A = Assignment


def test_offer_outcomes() -> None:
    for outcome in (A.ACCEPTED, A.REJECTED, A.EXPIRED, A.REVOKED):
        assert can_transition(A.OFFERED, outcome)


def test_agent_cannot_cancel_accepted_assignment() -> None:
    # #7 §3: only manager intervention (REVOKED) or completion/failure request leave ACCEPTED.
    exits = {b for a, b in ASSIGNMENT_TRANSITIONS if a == A.ACCEPTED}
    assert exits == {A.REVOKED, A.COMPLETED, A.FAILURE_REQUESTED}


def test_failure_needs_request_first() -> None:
    assert [a for a, b in ASSIGNMENT_TRANSITIONS if b == A.FAILED] == [A.FAILURE_REQUESTED]


def test_active_and_indicator_sets() -> None:
    assert {A.ACCEPTED, A.FAILURE_REQUESTED} == ACTIVE_FOR_AGENT
    assert {A.ACCEPTED} == SHOWS_AGENT_ASSIGNED
