# Delivery module (assignment, availability, delivery code, GPS)

**Purpose and scope:** the delivery-agent side of an order after kitchen acceptance (#7 §3–§10; DL-01–DL-17, DL-G1–DL-G5; DDR-14, DDR-16, DDR-43, DDR-51, DDR-52, DDR-78, DDR-113). Order status changes (pickup, delivered, failed) are in the orders service; this module never writes an order. The Delivery PWA is Task 9B; the manager UI is Task 10; realtime hints are Task 11A (`realtime` module); OSRM is optional and deferred (DDR-55).

| Item | Value |
| --- | --- |
| UI screens | Delivery PWA (Task 9B); customer order page shows the code and live position after pickup |
| API endpoints | Agent: `GET /api/v1/delivery/me` · `PUT …/me/availability` · `POST …/assignments/{id}/respond` · `GET …/orders/{id}/customer-phone` (audited) · `POST …/orders/{id}/pickup`, `/deliver` (code), `/cod`, `/customer-unavailable`, `/contact-manager`, `/failure-request` · `POST …/locations` (≤ 100 points) · `GET …/history` · `PUT …/me/name`. Manager (`/api/v1/delivery/manage`): `GET /agents` · `POST /orders/{id}/assign` · `POST /agents/{id}/force-offline` · `POST /orders/{id}/failure-decision` · `POST /orders/{id}/code` |
| Service functions | Agent: `my_work`, `set_availability`, `respond`, `reveal_phone`, `ingest`, `history`, `rename`; manager: `manager_assign`, `force_offline`, `agents`; caller's transaction (orders service): `offer_on_acceptance`, `revoke`, `held_by`, `move`, `issue_otp`, `check_otp`, `code_for_customer`, `latest_point`, `gps_summary` |
| Tables | `app.delivery_assignments`, `app.agent_availability`, `app.delivery_otps`, `app.delivery_locations`; functions `app.offer_next`, `app.expire_and_reoffer`, `app.purge_delivery_locations` (migration 0011) |
| Permissions | `delivery.assignments.view` (agent, own region; only their own offer or delivery, others read as 404). `management.agents.assign` (RM assigned regions, CA). The `worker` DB role has EXECUTE on the two job functions only (DDR-113 (17)) |
| States | 200 · 204 · 401 · 403 · 404 · 409 wrong step, expired offer, locked code · 422 missing reason, wrong code, bad points |
| Tests | `tests/test_domain.py`; `tests/test_delivery_integration.py` (12 tests: online-only offers, Agent Assigned, rejection reason and re-offer, 60 s expiry incl. the worker role, pickup gate, code and tracking only after pickup, GPS stale/out-of-order, 3 wrong codes and reissue, cannot set Delivered without the code, unavailable wait, failure request approve/return, reassignment revokes, phone reveal audited, retention day 29/31) |

## Rules implemented

- **Availability (DL-01, DL-06):** no row = OFFLINE; only ONLINE agents get offers. Going offline expires an open offer; never with an accepted delivery. Going online picks up a waiting order at once.
- **Offers (DL-04, DDR-113 (2), (3)):** `app.offer_next` is the one rule: active agent of the order's region, ONLINE, no open offer or live delivery, never one who rejected or let this order expire; least recently offered first. Accept within 60 s or it expires (refused on accept, and the worker sweep every 10 s); rejection needs a reason. Accept emits `delivery.assigned` and shows "Agent Assigned" to the customer; the fulfilment status never changes.
- **Delivery code (DL-11, DDR-113 (6)):** created at pickup; the six digits are HMAC(server secret, order, random nonce) and are never stored; shown only on the customer's own order while Out for delivery. Three wrong codes lock it and set `delivery_exception_open`; a manager issues a new one with a reason. Only the verified code sets DELIVERED (assignment COMPLETED, `delivery.completed` with a GPS summary).
- **Exceptions (#7 §7):** customer unavailable starts the 5-minute wait (DDR-14); afterwards, or any time with a reason, "contact manager" sets the exception flag (audited). Refusal or failure needs a reason → FAILURE_REQUESTED; the manager approves (DELIVERY_FAILED, `delivery.failed`) or returns it (FAILURE_REQUESTED → ACCEPTED, DDR-113 (18)). No automatic refund on failure (DDR-44 open).
- **GPS (DDR-52, DDR-113 (8)):** only the agent holding the accepted delivery may send; stale (> `GPS_STALE_SECONDS`, 120 s test default), future and out-of-order points are refused and counted; REAL or SIMULATED per point. The customer sees only the latest point and only after pickup. No per-point events (DDR-78). Retention deletes points older than 30 days daily, audited.
- **Privacy (DL-08):** the masked number by default; the full number only for the agent's own accepted delivery, every reveal audited. The address is shown after the agent accepts.

## Assumptions and integration points

- COD collection is not required before delivery (no rule in the sources); `record_cod_collection` records it or a mismatch.
- `history` duration is pickup → delivered from the status history.
- Agent profile photos are not stored (no file storage, DDR-28).
