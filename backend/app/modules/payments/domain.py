"""Payment state machine (Matrix §7.2; simulator scenarios #15 §9). Standard library only.

Payment state is independent of fulfilment (PL-07). COD and prepaid use separate status families.
"""

from __future__ import annotations

from enum import StrEnum


class PaymentMethod(StrEnum):
    SIM_UPI = "SIM_UPI"
    SIM_CARD = "SIM_CARD"
    COD = "COD"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"
    COLLECTION_PENDING = "COLLECTION_PENDING"
    COLLECTED = "COLLECTED"
    MISMATCH = "MISMATCH"


P = PaymentStatus
PREPAID_STATUSES = frozenset({P.PENDING, P.SUCCEEDED, P.FAILED, P.TIMED_OUT, P.REFUND_PENDING, P.REFUNDED})
COD_STATUSES = frozenset({P.COLLECTION_PENDING, P.COLLECTED, P.MISMATCH})

PAYMENT_INITIAL = frozenset({P.PENDING, P.COLLECTION_PENDING})
PAYMENT_TRANSITIONS = frozenset(
    {
        (P.PENDING, P.SUCCEEDED),
        (P.PENDING, P.FAILED),
        (P.PENDING, P.TIMED_OUT),
        (P.SUCCEEDED, P.REFUND_PENDING),
        (P.REFUND_PENDING, P.REFUNDED),
        (P.COLLECTION_PENDING, P.COLLECTED),
        (P.COLLECTION_PENDING, P.MISMATCH),
    }
)


def initial_status(method: PaymentMethod) -> PaymentStatus:
    return P.COLLECTION_PENDING if method is PaymentMethod.COD else P.PENDING


def status_fits_method(method: PaymentMethod, status: PaymentStatus) -> bool:
    return status in (COD_STATUSES if method is PaymentMethod.COD else PREPAID_STATUSES)


def can_transition(current: PaymentStatus, target: PaymentStatus) -> bool:
    return (current, target) in PAYMENT_TRANSITIONS


class SimOutcome(StrEnum):
    """Simulator scenarios for prepaid methods (#15 §9); chosen by the caller (DDR-109)."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


OUTCOME_STATUS: dict[SimOutcome, PaymentStatus] = {
    SimOutcome.SUCCESS: P.SUCCEEDED,
    SimOutcome.FAILED: P.FAILED,
    SimOutcome.TIMEOUT: P.TIMED_OUT,
}


def is_prepaid(method: PaymentMethod) -> bool:
    return method is not PaymentMethod.COD
