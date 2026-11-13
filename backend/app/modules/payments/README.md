# Payments module (simulated payments)

**Purpose and scope:** the payment simulator for UPI, card and COD (#15 §9; Phase 4 §13; DDR-109). No real gateway, account, UPI ID, card number or credential exists anywhere. Called by the orders service inside its transaction; it has no routes of its own.

| Item | Value |
| --- | --- |
| UI screens | Customer payment-simulator step (Task 6); Management payment views (Task 10) |
| API endpoints | None directly; `POST /api/v1/orders/{id}/payment/simulate` (orders module) |
| Service functions | `open_payment`, `for_order`, `apply_outcome`, `refund_routine`, `record_cod` |
| Tables | `app.payments` (one per order; amount, `SIM-` reference), `app.status_history` |
| Permissions | Enforced by the calling orders service |
| Tests | `tests/test_domain.py` (machine, families, outcomes); orders integration tests |

## Rules implemented

- Prepaid starts `PENDING`; COD starts `COLLECTION_PENDING` (separate status families, Matrix §7.2).
- The simulator result is chosen by the caller: SUCCESS → `SUCCEEDED`, FAILED → `FAILED`, TIMEOUT → `TIMED_OUT` (a chosen result, not a clock).
- Routine refund: full amount, at once, for a succeeded prepaid payment (`REFUND_PENDING` → `REFUNDED`). Exceptional refunds stay disabled (DDR-44). COD is never refunded.
- COD at the door: `COLLECTED`, or `MISMATCH` with a reason (escalated to the manager in Task 9).
- Every transition is checked by the database and recorded with actor, role, time and reason.
