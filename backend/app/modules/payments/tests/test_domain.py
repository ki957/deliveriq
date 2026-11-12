from __future__ import annotations

import pytest

from app.modules.payments.domain import (
    PAYMENT_TRANSITIONS,
    PaymentMethod,
    PaymentStatus,
    can_transition,
    initial_status,
    status_fits_method,
)

pytestmark = pytest.mark.unit
P = PaymentStatus


def test_initial_status_depends_on_method() -> None:
    assert initial_status(PaymentMethod.COD) is P.COLLECTION_PENDING
    assert initial_status(PaymentMethod.SIM_UPI) is P.PENDING
    assert initial_status(PaymentMethod.SIM_CARD) is P.PENDING


@pytest.mark.parametrize("status", [P.COLLECTION_PENDING, P.COLLECTED, P.MISMATCH])
def test_cod_statuses_belong_to_cod_only(status: PaymentStatus) -> None:
    assert status_fits_method(PaymentMethod.COD, status)
    assert not status_fits_method(PaymentMethod.SIM_UPI, status)


def test_transitions_never_cross_families() -> None:
    for a, b in PAYMENT_TRANSITIONS:
        assert status_fits_method(PaymentMethod.COD, a) == status_fits_method(PaymentMethod.COD, b)


def test_failed_payment_cannot_later_succeed() -> None:
    assert not can_transition(P.FAILED, P.SUCCEEDED)
    assert not can_transition(P.TIMED_OUT, P.SUCCEEDED)


def test_refund_only_after_success() -> None:
    assert [a for a, b in PAYMENT_TRANSITIONS if b == P.REFUND_PENDING] == [P.SUCCEEDED]
