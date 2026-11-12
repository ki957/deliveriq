"""Delivery assignment state machine (Matrix §7.2; #7 §3, §7). Standard library only.

Assignment is independent of fulfilment: no assignment transition changes the order's status
(DDR-16, DDR-17).
"""

from __future__ import annotations

from enum import StrEnum


class Assignment(StrEnum):
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    COMPLETED = "COMPLETED"
    FAILURE_REQUESTED = "FAILURE_REQUESTED"
    FAILED = "FAILED"


A = Assignment
ASSIGNMENT_INITIAL = frozenset({A.OFFERED})
ASSIGNMENT_TRANSITIONS = frozenset(
    {
        (A.OFFERED, A.ACCEPTED),
        (A.OFFERED, A.REJECTED),
        (A.OFFERED, A.EXPIRED),
        (A.OFFERED, A.REVOKED),
        (A.ACCEPTED, A.REVOKED),
        (A.ACCEPTED, A.COMPLETED),
        (A.ACCEPTED, A.FAILURE_REQUESTED),
        (A.FAILURE_REQUESTED, A.FAILED),
    }
)
# DL-03: statuses that count as the agent's one active delivery.
ACTIVE_FOR_AGENT = frozenset({A.ACCEPTED, A.FAILURE_REQUESTED})
# "Agent Assigned" indicator for the customer (DDR-16).
SHOWS_AGENT_ASSIGNED = frozenset({A.ACCEPTED})


def can_transition(current: Assignment, target: Assignment) -> bool:
    return (current, target) in ASSIGNMENT_TRANSITIONS
