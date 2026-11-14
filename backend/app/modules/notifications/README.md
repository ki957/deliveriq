# Notifications module (in-app notifications, 30-day history)

**Purpose and scope:** in-app notifications for the events the sources name (CU-25, DL-16, KI-23; DDR-115 (10)–(12)). In-app only: SMS is "Not configured (DDR-40)" and stated on screen; no browser push. Live delivery uses the realtime `me` topic (Task 11A).

| Item | Value |
| --- | --- |
| UI screens | `/customer/notifications` (signed in), `/kitchen/notifications` (Kitchen Manager), `/delivery/notifications`; a header bell with the unread count wherever the page is in the portal's navigation (`frontend/src/features/notifications`) |
| API endpoints | `GET /api/v1/me/notifications` (last 30 days, newest first, at most 100, unread count, `history_days`, `sms`) · `POST /api/v1/me/notifications/read` (`ids`, or none for all; others' ids ignored) |
| Service functions | `inbox`, `mark_read` |
| Tables | `app.notifications` (migration 0013): person, kind, order / kitchen / ingredient ids, fixture flag, created and read times; ids only, never names, phones, addresses or codes. Written by SECURITY DEFINER triggers on orders (fulfilment), delivery assignments (status) and ingredient stock (threshold crossing), so the API, the worker sweep and SQL functions are all covered. Purges: `app.purge_notifications(days)`, `app.purge_auth(days)`, run daily by the worker (EXECUTE only), audited |
| Kinds | Customer: `order.accepted`, `.preparing`, `.ready_for_pickup`, `.out_for_delivery`, `.delivered`, `.cancelled`, `.rejected`, `.delivery_failed`, `.agent_assigned`. Agent: `delivery.offered`, `.withdrawn` (reassigned or cancelled), `.failure_returned`, `.failure_approved`. Kitchen Manager: `stock.low` |
| Permissions | Signed in; a person sees and marks only their own rows. The kitchen page is shown to the KM (`kitchen.inventory.view`) |
| States | 200 · 204 · 401 · 403 (CSRF) · 422 (more than 100 ids) |
| Tests | `tests/test_notifications_integration.py` (4: customer lifecycle and only-own rows and read marks; agent offer and withdrawal plus the customer's rejection; KM low stock once per crossing, KS none; purges keep day 29 and delete day 31 for notifications, OTP challenges and sessions, as the worker, audited, idempotent); frontend `notifications.test.tsx`; E2E `realtime.spec.ts` (a rejection arrives live on the customer's open page) |

## Rules implemented

- **Kinds from the sources only (DDR-115 (10)):** lifecycle statuses after payment (CU-25); offer, reassignment or cancellation and the manager's failure decision (DL-16); the KM is told when available stock falls to the threshold (KI-23), once per crossing. "Manager instructions" (DL-16) have no model in the sources and are not built.
- **Agent Assigned (DDR-16):** the customer is told when the agent accepts while the kitchen still holds the order; the fulfilment label is unchanged.
- **Retention (DDR-115 (11), (12)):** notifications are kept 30 days (DL-16). OTP challenges are deleted 30 days after expiry; sessions 30 days after revocation, absolute expiry or 2 hours idle (DDR-98). Each daily run writes one audit row with the counts. This closes DDR-107 (8).
- **Test data:** rows about TEST orders and TEST stock carry the fixture flag, are badged "Test data" and are counted by the production fixture guard.

## Assumptions and integration points

- The UI words each kind; the API never sends text, so wording changes need no migration.
- Trusted devices are not purged (not in DDR-115 (12)); they expire after 7 days (DDR-98).
