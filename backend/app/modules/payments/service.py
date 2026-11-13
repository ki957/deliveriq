"""Simulated payments (#15 §9; Phase 4 §13; DDR-109). No real gateway, account or credential exists.

Every function runs in the caller's transaction (the orders service owns it), so an order and its
payment change together. The caller sets the actor context; the database checks each transition.
Simulated transactions keep a reference, timestamps, status and history (#7 §8).
"""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import Connection

from app.modules.payments import domain as d
from app.modules.payments import repository as repo

PaymentRow = repo.PaymentRow


class PaymentConflict(Exception):
    """The payment is not in a state that allows this step."""


def _reference() -> str:
    return f"SIM-{secrets.token_hex(6).upper()}"


def open_payment(
    conn: Connection, order_id: uuid.UUID, method: d.PaymentMethod, amount_paise: int
) -> PaymentRow:
    """One payment per order: PENDING for prepaid, COLLECTION_PENDING for COD."""
    repo.insert(conn, order_id, method.value, d.initial_status(method).value, amount_paise, _reference())
    payment = repo.for_order(conn, order_id)
    if payment is None:  # pragma: no cover - just inserted in this transaction
        raise PaymentConflict("payment missing after insert")
    return payment


def for_order(conn: Connection, order_id: uuid.UUID, *, lock: bool = False) -> PaymentRow | None:
    return repo.for_order(conn, order_id, lock=lock)


def apply_outcome(conn: Connection, payment: PaymentRow, outcome: d.SimOutcome) -> d.PaymentStatus:
    """Record the simulator result for a prepaid payment (PENDING only)."""
    if not d.is_prepaid(d.PaymentMethod(payment.method)):
        raise PaymentConflict("Cash on delivery has no online payment step")
    if payment.status != d.PaymentStatus.PENDING:
        raise PaymentConflict(f"Payment is already {payment.status}")
    target = d.OUTCOME_STATUS[outcome]
    repo.set_status(conn, payment.id, target.value)
    return target


def refund_routine(conn: Connection, payment: PaymentRow) -> bool:
    """Routine refund (DDR-109): a succeeded prepaid payment is refunded in full at once.

    Returns False when nothing is refunded (COD, or no successful payment). The caller sets a reason:
    SUCCEEDED → REFUND_PENDING requires one. Exceptional refunds stay disabled (DDR-44).
    """
    if payment.status != d.PaymentStatus.SUCCEEDED:
        return False
    repo.set_status(conn, payment.id, d.PaymentStatus.REFUND_PENDING.value)
    repo.set_status(conn, payment.id, d.PaymentStatus.REFUNDED.value)
    return True


def record_cod(conn: Connection, payment: PaymentRow, *, collected: bool) -> d.PaymentStatus:
    """COD at the door (Task 9): collected, or a mismatch escalated to the manager (reason required)."""
    if payment.method != d.PaymentMethod.COD:
        raise PaymentConflict("Prepaid orders never collect cash")
    if payment.status != d.PaymentStatus.COLLECTION_PENDING:
        raise PaymentConflict(f"Cash collection is already {payment.status}")
    target = d.PaymentStatus.COLLECTED if collected else d.PaymentStatus.MISMATCH
    repo.set_status(conn, payment.id, target.value)
    return target
