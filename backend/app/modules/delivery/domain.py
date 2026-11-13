"""Delivery assignment state machine (Matrix §7.2; #7 §3, §7). Standard library only.

Assignment is independent of fulfilment: no assignment transition changes the order's status
(DDR-16, DDR-17).
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta
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
        # The manager rejects a failure request (DDR-113 (18)).
        (A.FAILURE_REQUESTED, A.ACCEPTED),
    }
)
# DL-03: statuses that count as the agent's one active delivery.
ACTIVE_FOR_AGENT = frozenset({A.ACCEPTED, A.FAILURE_REQUESTED})
# "Agent Assigned" indicator for the customer (DDR-16).
SHOWS_AGENT_ASSIGNED = frozenset({A.ACCEPTED})


def can_transition(current: Assignment, target: Assignment) -> bool:
    return (current, target) in ASSIGNMENT_TRANSITIONS


# ---------------------------------------------------------------- delivery OTP (DL-11; DDR-113 (6))
OTP_MAX_ATTEMPTS = 3
REASON_MAX = 500


def delivery_code(secret: str, order_id: str, nonce: str) -> str:
    """The six digits shown to the customer; derived from a nonce and the server secret, never stored."""
    digest = hmac.new(secret.encode(), f"delivery-otp|{order_id}|{nonce}".encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 1_000_000:06d}"


def codes_match(expected: str, given: str) -> bool:
    return hmac.compare_digest(expected, given.strip())


# ---------------------------------------------------------------- GPS points (DDR-52; DDR-113 (8))
GPS_BATCH_MAX = 100


def point_refusal(
    recorded_at: datetime, *, now: datetime, last: datetime | None, stale_seconds: int
) -> str | None:
    """Why a point is refused: stale (older than the limit), out of order, or from the future."""
    if recorded_at > now + timedelta(seconds=30):
        return "future"
    if recorded_at < now - timedelta(seconds=stale_seconds):
        return "stale"
    if last is not None and recorded_at <= last:
        return "out_of_order"
    return None


def mask_phone(mobile: str) -> str:
    """DL-08: masked by default; the last two digits only."""
    return mobile[:3] + "*" * max(len(mobile) - 5, 0) + mobile[-2:]
