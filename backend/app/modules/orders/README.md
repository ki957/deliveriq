# Orders module (placement, fulfilment rules, display mapping)

**Purpose and scope:** order placement with checkout idempotency, the simulated-payment outcome, customer cancellation before acceptance, the canonical display mapping, and the fulfilment rules later tasks call (Matrix §7; DDR-16, DDR-17, DDR-38, DDR-109). Cart, ₹500 minimum, coupons, price protection, serviceability and the checkout UI are Task 6; kitchen accept/reject Task 8; delivery endpoints Task 9; the outbox relay Task 12.

| Item | Value |
| --- | --- |
| UI screens | Customer checkout and order tracking (Task 6) |
| API endpoints | `POST /api/v1/orders` (`Idempotency-Key` header; 201 new, 200 repeat, 409 key reused for a different request) · `GET /api/v1/orders` · `GET /api/v1/orders/{id}` · `POST /api/v1/orders/{id}/payment/simulate` (SUCCESS, FAILED, TIMEOUT) · `POST /api/v1/orders/{id}/cancel` |
| Service functions | `place`, `get`, `list_mine`, `simulate_payment`, `cancel`; for Tasks 8–9: `record_pickup`, `record_cod_collection` (payments: `refund_routine` for rejection) |
| Tables | `app.orders`, `app.order_items`, `app.payments`, `app.delivery_assignments` (read), `app.outbox`, `app.status_history`; function `app.create_order()` (migration 0008) |
| Permissions | `customer.orders.read`, `customer.orders.place`, `customer.orders.cancel` (CUSTOMER, own orders; others' orders are 404). Pickup and COD: a delivery agent of the order's region holding its accepted assignment |
| States | 201/200 · 401 · 403 · 404 · 409 wrong step or key reuse · 422 invalid input or a dish that cannot be ordered |
| Tests | `tests/test_domain.py` (Matrix §7.3 label table, hashing, fee); `tests/test_orders_integration.py` (paths, idempotency incl. concurrency, privacy, refunds, Agent Assigned, pickup, COD, outbox atomicity, fixture flags) |

## Rules implemented

- **Placement:** one transaction writes the order (via `app.create_order()`), its items with name and price snapshots, one payment and `order.placed`. Payable = food subtotal + ₹30 (DDR-38). Only published, priced dishes from one kitchen; in production, fixture dishes are refused.
- **Fixture flag (DDR-109):** derived in the database from the dishes (all TEST or all real); items and payments inherit it. The API never sends it.
- **COD** goes straight to `PENDING_KITCHEN`. **Prepaid** stays `PLACED` until the simulator: SUCCESS → `PENDING_KITCHEN` (`payment.succeeded`); FAILED or TIMEOUT → `CANCELLED` (`payment.failed`, `order.cancelled`), never the kitchen. Repeating the same outcome is idempotent.
- **Cancel (CU-19):** only in `PENDING_KITCHEN`; prepaid is refunded in full at once (`REFUND_PENDING` → `REFUNDED`, reason recorded); COD has no refund. A `PLACED` order must finish or fail its payment first.
- **Display mapping:** `domain.display()` returns the Matrix §7.3 labels for every portal and state, plus the "Agent Assigned" indicator for an accepted assignment while the kitchen has the order. Assignment never changes the fulfilment status.
- **Pickup (DDR-16):** `PICKED_UP` then `OUT_FOR_DELIVERY` in the same transaction; the only code path into either; emits `delivery.picked_up`.

## Assumptions and integration points

- Input-size guards (at most 50 lines, quantity 1–99) protect the API; they are not business limits, none are defined in the sources.
- Refund and COD-collection events are not emitted until event types are approved (DDR-109; Task 12).
- A cancelled COD order keeps payment `COLLECTION_PENDING`: the payment machine has no transition for it (Matrix §7.2).
