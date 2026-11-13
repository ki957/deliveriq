# Ordering feature (Customer)

**Purpose and scope:** the customer journey from location to a placed order: serviceability, menu with search and filters, dish page, persisted cart, bill, coupon, checkout, simulated payment, order list and detail with cancellation (CU-01–CU-21, DDR-109, DDR-110). Live tracking (Task 9), support and profile pages are separate.

| Item          | Value                                                                                                                                                                                                                                                                                        |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UI screens    | `/customer/menu`, `/customer/menu/:dishId` (public); `/customer/cart`, `/customer/orders`, `/customer/orders/:orderId` (session required)                                                                                                                                                    |
| API endpoints | `GET /api/v1/serviceability`, `GET /api/v1/menu/items`, `/menu/filters`, `/menu/items/{id}`, `/api/v1/me/addresses`, `/api/v1/cart` (+ `items/{id}`, `accept-price`, `remove-unavailable`), `POST /api/v1/orders`, `/orders/{id}/payment/simulate`, `/orders/{id}/cancel` (generated client) |
| Permissions   | Browsing is public. Cart, checkout and orders need a customer session; `customer.orders.place` / `customer.orders.cancel` and order ownership are enforced by the backend                                                                                                                    |
| States        | Loading, empty, error, denied, not found; backend refusals (stable `code`) are worded in `messages.ts` and shown as alerts                                                                                                                                                                   |
| Tests         | `ordering.test.tsx`; `tests/e2e/specs/customer-checkout.spec.ts` (`@devices`: desktop, phone-360, phone-390, tablet)                                                                                                                                                                         |

## Behaviour

- A location is chosen first (browser location, typed coordinates or a saved address). A visitor's choice is kept in this browser only (`location.ts`); a denied location never produces a made-up position.
- The menu is shown only when both distance rules pass. Out of area shows a message only (DDR-110 (7)). Road distance is labelled "estimated" until OSRM (Task 9).
- Filter options come from the data (`/menu/filters`); the bestseller filter appears only when a dish is flagged. Dishes are added from the dish page; the food-card Add button waits for DDR-06.
- The bill, blockers, coupon result and serviceability all come from the backend quote. A changed price (after the 30-minute hold) needs "Accept new price"; unavailable dishes are removed only after confirmation.
- Placement sends the prices the customer saw and one `Idempotency-Key` per attempt; a refusal gets a new key on retry (DDR-109).
- Prepaid orders show a labelled payment simulator (success, failure, timeout); failure or timeout cancels the order. Cancellation is offered until kitchen acceptance, after confirmation; prepaid is refunded in full.
- TEST dishes and TEST orders carry a "Test data" / "Test order" badge.

## Not built here

- Cart count in the navigation (CU-N1), address search and maps, customization options (none configured, DDR-110 (10)).
