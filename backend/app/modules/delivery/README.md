# Delivery module (assignment at kitchen acceptance)

**Purpose and scope:** the assignment state machine and the offer made when the kitchen accepts an order (DDR-51, DDR-111 (6); #7 §3). Agent response, the 60-second timeout, the pool, online/offline, reassignment by a manager and every delivery screen are Task 9.

| Item | Value |
| --- | --- |
| UI screens | None yet (Delivery portal, Task 9); the kitchen card shows the offer or agent (Task 8B) |
| API endpoints | None yet (Task 9) |
| Service functions | In the caller's transaction: `offer_on_acceptance`, `revoke`, `live_for` |
| Tables | `app.delivery_assignments`, `app.users` and `app.role_assignments` (read) |
| Permissions | Called by the orders service under the kitchen actor's context; no route of its own |
| Tests | `orders/tests/test_kitchen_integration.py` (offer at acceptance, one per agent, revoke on reject); `migrations/tests/test_state_machines.py` (one live assignment per agent) |

## Rules implemented

- **Offer at acceptance (DDR-51):** in the acceptance transaction, an `OFFERED` assignment goes to an active agent of the order's region with no open offer or live delivery, least recently offered first. None eligible → no offer ("Awaiting agent"); the kitchen is never blocked.
- **One live assignment per agent:** a unique index on open offers and live deliveries (DDR-111 (6)), beyond DL-03; a race between kitchens loses quietly (no offer).
- **Revoke:** a rejection revokes the live offer or assignment (DL-07). A failure request stays with the manager.
- Assignment never changes the order's fulfilment status (DDR-16, DDR-17). "Agent Assigned" shows only once the agent accepts (Task 9).

## Assumptions and integration points

- Until online/offline exists (Task 9), every active agent counts as available; this is labelled in the kitchen UI.
- `delivery.assigned` is emitted when an agent accepts (Task 9), not at the offer.
