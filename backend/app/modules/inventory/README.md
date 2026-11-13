# Inventory module (ingredient stock, reservations, ledger)

**Purpose and scope:** ingredient stock per kitchen, reservation at kitchen acceptance, release on reject, deduction at handover, manager adjustments and low-stock thresholds (#4 §7; KI-21–KI-23; DDR-18, DDR-37, DDR-111 (4), (8), (9)). Ingredient-level ledger without lots or expiry (KI-25). AI never changes stock (DDR-18). The Inventory UI is Task 8B.

| Item | Value |
| --- | --- |
| UI screens | Kitchen → Inventory, Exceptions (Task 8B) |
| API endpoints | `GET /api/v1/kitchen/inventory` (KM) · `GET /api/v1/kitchen/inventory/low-stock` (KS, KM) · `POST /api/v1/kitchen/inventory/{ingredient_id}/adjust` (signed delta, reason) · `PUT /api/v1/kitchen/inventory/{ingredient_id}/threshold` (value or null, reason) |
| Service functions | In the caller's transaction: `reserve`, `release`, `consume`; reads and actions: `stock`, `low_stock`, `adjust`, `set_threshold` |
| Tables | `app.ingredient_stock`, `app.stock_reservations`, `app.stock_movements` (append-only), `app.order_items` and `app.recipe_ingredients` (read), `app.outbox`, `audit.events` |
| Permissions | `kitchen.inventory.view` (KM), `kitchen.low_stock.view` (KS, KM), `kitchen.stock.adjust` (KM), `kitchen.ingredients.manage` (KM, thresholds). Own kitchen only; Kitchen Staff get 403 on KM actions; another kitchen is 404 |
| States | 200 · 401 · 403 · 404 · 422 invalid quantity, below reserved, or missing reason |
| Tests | `tests/test_domain.py`; `orders/tests/test_kitchen_integration.py` (all-or-nothing and concurrent reservation, release, deduct once, roles, low stock) |

## Rules implemented

- **Reserve (KI-22):** at acceptance, the total of the pinned recipe lines × quantity per ingredient; rows locked in ingredient order; all or nothing. A shortage refuses acceptance with the short ingredients (`stock_short`); nothing is reserved (DDR-111 (4)). The `reserved <= on_hand` check makes oversell impossible even for a caller that skips the service.
- **Release:** a rejection (before or after acceptance) returns open reservations; `inventory.released`.
- **Consume:** the validated pickup deducts reserved stock once; reservations move to `CONSUMED` once and the ledger allows one consumption per order and ingredient; `inventory.consumed`.
- **Adjust (#4 §7.2):** KM, signed amount, required reason, never below reserved; ledger row and audit event.
- **Low stock:** only against a threshold the KM set; unset means no alert (DDR-42 open). Each ingredient lists the dishes whose ACTIVE recipe uses it (KI-23).
- **Test stock (DDR-37):** opening stock is loaded only by `fixtures load-stock` (10,000 g per TEST ingredient). Every stock, reservation and ledger row derives `is_test_fixture` in the database (never written by the API); TEST and real rows cannot mix (foreign keys on the flag); the production startup check counts all three tables.

## Assumptions and integration points

- Quantities use the ingredient's unit (g, ml, piece); no purchase-unit conversion (DDR-111 (8)).
- Adjustments, thresholds and low stock have no approved event type; they are audit-only (DDR-109 (6)).
- Shortage notifications to the KM wait for Task 11; the UI shows persisted low-stock state.
