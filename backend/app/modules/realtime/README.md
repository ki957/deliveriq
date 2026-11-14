# Realtime module (change notices → Redis → WebSocket hints)

**Purpose and scope:** live screen updates for every portal (plan Task 11; PL-04, PL-06, PL-14; ADR-004, ADR-006; DDR-115). Sockets carry invalidate hints only; every screen still reads its REST view, so labels (Matrix §7.3), PII rules and scope stay as REST has them. In-app notifications and the purge jobs are Task 11B.

| Item | Value |
| --- | --- |
| UI | `frontend/src/shared/realtime` (one socket per tab, `useLiveRefresh`, `useRealtimeStatus`); `PollNote` and the customer tracking note say "Live" or "Live updates paused · updates every 10 s" |
| Endpoint | WebSocket `/api/v1/realtime` (not in OpenAPI). Client → `{"type": "subscribe"\|"unsubscribe", "topics": [...]}` (≤ 50). Server → `{"type": "ready"}`, `{"type": "subscribed"\|"denied", "topic"}`, hints `{topic, kind, id}`. Close 4401 signed out or revoked, 1013 realtime unavailable; a foreign Origin is refused at the handshake |
| Topics | `order:{id}` (owning customer), `kitchen:{id}` (that kitchen's staff, RM of its region, CA), `region:{id}` (management views; RM own regions, CA), `agent:me` (the agent's own offers, deliveries and their order progress), `pipelines` (CA all runs; RM own-region runs only) |
| Code | `domain.py` (pure: topics, notice → hints, frames), `service.py` (subscription checks with `can()`, session re-validation), `hub.py` (Postgres LISTEN → Redis PUBLISH; Redis SUBSCRIBE → sockets), `api.py` (handshake, per-socket writer queue, 60 s re-validation) |
| Tables | Migration 0012: `app.rt_notify()` triggers on orders, order items (prep status), delivery assignments, delivery locations, kitchens, ingredient stock, dish availability requests, agent availability, `ops.pipeline_runs`, `ops.pipeline_stage_runs`, sessions (revoked) and users (deactivated); `app.rt_live_agent(order)`. Notices carry ids and scope only (`k, id, o, c, a, ki, r, st, s, u`) |
| Permissions | Same as the REST views: `customer.orders.read` (own), `kitchen.orders.view` (own kitchen), `management.operations.view` (region), `delivery.assignments.view` (agent), `pipelines.view` (`view_scope`) |
| Tests | `tests/test_domain.py` (9: topic parsing, `agent:me` is always the caller, routing per kind, kitchen never hears unpaid orders, agent hears its order's progress, frames are only `{topic, kind, id}`, malformed input); `tests/test_realtime_integration.py` (6, real socket: session and Origin required, scope per role incl. cross-customer / cross-kitchen / cross-region, bare hints and no kitchen hint before payment, Agent Assigned with the fulfilment label unchanged plus the agent's pickup progress, own-region pipeline hints, logout and deactivation close within 2 s and the revoked session cannot reconnect); E2E `realtime.spec.ts` (kitchen board live, polling fallback) and `delivery.spec.ts` (customer sees Agent Assigned live) |

## Rules implemented

- **Change capture (DDR-115 (2), (13)):** NOTIFY is delivered on commit from every writer, including the worker's SECURITY DEFINER sweep and the pipeline roles, so the outbox stays the analytics path (Task 12). The trigger function is SECURITY DEFINER to resolve an order's scope for writers without table grants.
- **Relay (DDR-115 (3)):** one async Postgres listener in the API publishes each notice to Redis `deliveriq:rt`; the hub subscribes. If either side is down the hub is not ready: open sockets close with 1013, new ones are refused, and every page polls (DOCKER §8). Both loops retry with backoff 1 → 30 s.
- **Scope (DDR-115 (5)):** each subscription is checked when it is made, with the REST rules; a refused topic gets `denied`, never silence. Pipeline hints are filtered per socket by the run's region. Before payment (`PLACED`) the kitchen gets no hint.
- **Revocation (DDR-115 (7)):** a revoked session or a deactivated user closes its sockets at once (4401); every socket also re-validates its session every 60 s without counting as activity. Role changes already revoke sessions (DDR-98).
- **Client (DDR-115 (8)):** pages stop polling while their topics are live; on a drop they poll again and the socket reconnects with backoff 1 → 30 s; every (re)subscription refetches the REST views.

## Assumptions and integration points

- One API process (DDR-62); Redis keeps the design ready for more processes without a change.
- Hints can repeat (Postgres merges identical notices per transaction only); refetching is idempotent.
- GPS points produce a hint per point for the customer and managers only (DDR-115 (9)); no per-point events (DDR-78).
