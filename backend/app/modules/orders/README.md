# Orders module (placement, fulfilment rules, display mapping)

**Purpose and scope:** the persisted cart with a live quote, order placement with the full checkout sequence and idempotency, the simulated-payment outcome, customer cancellation before acceptance, the canonical display mapping, and the fulfilment rules later tasks call (Matrix §7; DDR-16, DDR-17, DDR-38, DDR-109). Kitchen acceptance, rejection and preparation are here too (Task 8A; DDR-111), using the kitchen_ops, inventory and delivery services. The checkout UI is Task 6B; the kitchen UI Task 8B; delivery endpoints Task 9; the outbox relay Task 12.

| Item | Value |
| --- | --- |
| UI screens | Customer checkout and order tracking (Task 6); Kitchen Live Orders and Preparation Board (Task 8B) |
| API endpoints | `GET /api/v1/cart?address_id=&coupon_code=` (lines, protected prices, bill, serviceability, blockers) · `PUT/DELETE /api/v1/cart/items/{id}` · `POST /api/v1/cart/items/{id}/accept-price` · `POST /api/v1/cart/remove-unavailable` · `DELETE /api/v1/cart` · `POST /api/v1/orders` (`Idempotency-Key` header; 422 with `code` for checkout rules, 409 `price_changed` with `price_changes`; 201 new, 200 repeat, 409 key reused for a different request) · `GET /api/v1/orders` · `GET /api/v1/orders/{id}` · `POST /api/v1/orders/{id}/payment/simulate` (SUCCESS, FAILED, TIMEOUT) · `POST /api/v1/orders/{id}/cancel` · Kitchen: `GET /api/v1/kitchen/orders?kitchen_id=` (incoming, held FIFO by acceptance time, intake) · `POST /api/v1/kitchen/orders/{id}/accept` (409 `kitchen_paused`, `kitchen_at_capacity`, `recipe_not_active`, `stock_short` with `shortages`) · `POST …/{id}/reject` (reason) · `POST …/{id}/start` · `POST …/{id}/items/{item_id}/status` |
| Service functions | `place`, `get`, `list_mine`, `simulate_payment`, `cancel`; kitchen: `kitchen_queue`, `kitchen_accept`, `kitchen_reject`, `kitchen_start`, `kitchen_set_item`; for Task 9: `record_pickup` (deducts stock), `record_cod_collection` |
| Tables | `app.orders`, `app.order_items`, `app.payments`, `app.delivery_assignments` (read), `app.outbox`, `app.status_history`; function `app.create_order()` (migration 0008) |
| Permissions | `customer.orders.read`, `customer.orders.place`, `customer.orders.cancel` (CUSTOMER, own orders; others' orders are 404). Kitchen: `kitchen.orders.view` / `management.operations.view` to read the queue; `kitchen.orders.process` (KS, KM) to accept, reject incoming and prepare; `kitchen.orders.reject_accepted` (KM, RM, CA) after acceptance. Another kitchen's order is 404. Pickup and COD: a delivery agent of the order's region holding its accepted assignment |
| States | 201/200 · 401 · 403 · 404 · 409 wrong step or key reuse · 422 invalid input or a dish that cannot be ordered |
| Tests | `tests/test_domain.py` (Matrix §7.3 label table, hashing, fee, automatic order steps); `tests/test_orders_integration.py` (paths, idempotency incl. concurrency, privacy, refunds, Agent Assigned, pickup, COD, outbox atomicity, fixture flags); `tests/test_kitchen_integration.py` (Task 8 acceptance criteria) |

## Rules implemented

- **Checkout sequence (#1 §9, CU-17):** dishes available → stated prices match what is charged (protected cart price or current price; else 409) → own saved address, serviceable (revalidated) → ₹500 food minimum before coupon → coupon → ₹30 fee → place → payment step. The order stores the accepted prices, the discount and a delivery snapshot (address, straight-line and road distance, estimated flag); ordered dishes leave the cart.
- **Placement:** one transaction writes the order (via `app.create_order()`), its items with name and price snapshots, one payment and `order.placed`. Payable = food subtotal + ₹30 (DDR-38). Only published, priced dishes from one kitchen; in production, fixture dishes are refused.
- **Fixture flag (DDR-109):** derived in the database from the dishes (all TEST or all real); items and payments inherit it. The API never sends it.
- **COD** goes straight to `PENDING_KITCHEN`. **Prepaid** stays `PLACED` until the simulator: SUCCESS → `PENDING_KITCHEN` (`payment.succeeded`); FAILED or TIMEOUT → `CANCELLED` (`payment.failed`, `order.cancelled`), never the kitchen. Repeating the same outcome is idempotent.
- **Cancel (CU-19):** only in `PENDING_KITCHEN`; prepaid is refunded in full at once (`REFUND_PENDING` → `REFUNDED`, reason recorded); COD has no refund. A `PLACED` order must finish or fail its payment first.
- **Display mapping:** `domain.display()` returns the Matrix §7.3 labels for every portal and state, plus the "Agent Assigned" indicator for an accepted assignment while the kitchen has the order. Assignment never changes the fulfilment status.
- **Pickup (DDR-16):** `PICKED_UP` then `OUT_FOR_DELIVERY` in the same transaction; the only code path into either; emits `delivery.picked_up`; deducts the reserved stock once (`inventory.consumed`).
- **Checkout intake (KI-13; DDR-111 (3)):** refused with `kitchen_paused` or `kitchen_at_capacity`; the cart lists them as blockers.
- **Kitchen acceptance (Task 8):** one transaction locked per kitchen: mode and capacity → pin each item to its dish's ACTIVE recipe version (share-locked; a later version never changes pinned items) → reserve all stock or none → `accepted_at` → offer to an agent (DDR-51) → `order.accepted`. Any refusal leaves the order Incoming with nothing pinned or reserved.
- **Kitchen queue (KI-01, KI-03):** incoming orders by placement; held orders FIFO by acceptance time. The "Overdue" warning (acceptance timeout, a DDR-42 test default) never reorders it. Kitchen cards carry no customer name, phone or address.
- **Reject (DDR-111 (5)):** incoming by KS or KM; after acceptance ("cannot fulfil", KI-11) by KM, RM or CA only, enforced by permission and by the database transition roles. Reason required (≤ 500). Releases stock, refunds prepaid in full, revokes the agent offer; `order.rejected`.
- **Preparation (KI-05, KI-06):** items Pending → Preparing → Prepared; the first Preparing item moves the order to Preparing, all Prepared make it Ready for Pickup (`order.preparing`, `order.ready_for_pickup`); any staff member may continue another's order and each change keeps its actor. "Start order" starts every pending item.

## Assumptions and integration points

- Input-size guards (at most 50 lines, quantity 1–99) protect the API; they are not business limits, none are defined in the sources.
- Refund and COD-collection events are not emitted until event types are approved (DDR-109; Task 12).
- A cancelled COD order keeps payment `COLLECTION_PENDING`: the payment machine has no transition for it (Matrix §7.2).
