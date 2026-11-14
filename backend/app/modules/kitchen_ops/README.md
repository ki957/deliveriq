# Kitchen operations module (mode, capacity, intake)

**Purpose and scope:** kitchen mode (Normal, Busy, Paused) and capacity, and the intake rule that kitchen acceptance and customer checkout both use (#4 §3; KI-12–KI-15; DDR-42, DDR-111 (1)–(3), (14)). Accept, reject and preparation live in the orders module; stock in the inventory module. The Kitchen Settings UI is Task 8B; the Management UI for mode changes is Task 10.

| Item | Value |
| --- | --- |
| UI screens | Kitchen → Settings (Task 8B) |
| API endpoints | `GET /api/v1/kitchen/settings?kitchen_id=` · `PUT /api/v1/kitchen/settings?kitchen_id=` (mode, normal and Busy capacity, reason) |
| Service functions | `get_settings`, `update_settings`; in the caller's transaction: `intake`, `intake_for`, `lock`, `acceptance_timeout_minutes`; scope helpers `resolve`, `acting_role`, `allowed` |
| Tables | `app.kitchens` (mode), `app.config_settings` (`MAX_CONCURRENT_ORDERS`, `MAX_CONCURRENT_ORDERS_BUSY`, `KITCHEN_ACCEPTANCE_TIMEOUT`), `app.orders` (read-only count), `audit.events` |
| Permissions | Read: `kitchen.orders.view` (own kitchen) or `management.operations.view` (RM region, CA). Change: `kitchen.mode.change` (KM own kitchen, RM region, CA). Kitchen Staff get 403; another kitchen is 404 |
| States | 200 · 401 · 403 · 404 · 409 setting not configured · 422 invalid capacity or missing reason |
| Tests | `tests/test_domain.py` (modes and capacity); `orders/tests/test_kitchen_integration.py` (concurrent acceptance at capacity, Paused, audit, labels) |

## Rules implemented

- **Capacity (#4 §3; DDR-111 (2)):** counts orders in `ACCEPTED`, `PREPARING` and `READY_FOR_PICKUP`. Normal uses the normal capacity, Busy the Busy capacity (never higher), Paused accepts nothing new. Accepted orders always continue (KI-14).
- **Intake (DDR-111 (3)):** refusal codes `kitchen_paused` and `kitchen_at_capacity`; checkout refuses with 422 and the cart lists the code as a blocker; acceptance refuses with 409.
- **Concurrency:** acceptance locks the kitchen row, so two acceptances never pass the capacity check together.
- **Test defaults (DDR-42 open):** 10 / 5 orders and 5 minutes are labelled `is_test_default`; the API returns the label and the UI shows it. Only a changed value becomes a configured value.
- **Audit:** every change records actor, role, reason and before/after (`kitchen.settings.changed`). No event type is approved for it (DDR-109 (6)).

## Assumptions and integration points

- The acceptance timeout only drives an on-screen "Overdue" warning (KI-02); screens update live (Task 11A); notifications are Task 11B.
- Equipment failure (KI-16) is covered by switching to Paused; no separate workflow (DDR-111 (12)).
