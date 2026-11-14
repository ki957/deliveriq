# P2 operational ELT: landing and the dbt run

**Purpose and scope:** the continuous first step of P2 (DATA_PIPELINE §2.2, §4, §10, §13; ADR-004; DDR-66, DDR-116 (1), (5), (6), (10), (12)). Every business change writes one event to `app.outbox` in the same transaction (`shared/events.py`); this loop lands them in `raw.events`. The P2 run (`pipeline.py`, Task 12B) lands once more, then runs dbt staging → core → marts → tests and publishes freshness; the dbt project is `analytics/dbt` (its README).

| Item | Value |
| --- | --- |
| Runs | Worker thread `p2-landing` (`worker/main.py`), every 2 s, as the `p2_elt` DB role; independent of queued jobs, so a dbt run never blocks it |
| Code | `landing.py`: `problem(row)` (pure envelope check), `land_batch(conn)` (one transaction) |
| Tables | Reads and marks `app.outbox`; inserts `raw.events` (append-only). Migration 0014: `ops.outbox_backlog()` (counts and the oldest waiting time only, for the API) and a statement-level realtime `backlog` notice |
| API / UI | `GET /api/v1/pipelines/p2/backlog` (CA only: waiting, oldest age, landed, rejected, warning threshold); Data & Pipelines overview panel "P2 event landing", live |
| P2 run | Stages `land`, `dbt staging`, `dbt core`, `dbt marts`, `dbt tests`, `publish freshness`; every dbt test → `ops.dq_results` (critical); warnings `raw_freshness` (24 h) and `outbox_backlog_age` (5 min), labelled test defaults, recorded only; a failed critical test fails the run (data, never retried) and freshness is not published. Counts: events landed and rejected, real events, TEST events excluded, `fact_orders`, dbt tests. Inputs `run` and the TEST `fault:reconciliation` (local/test only). Runs have no region (CA only, DDR-116 (10)) |
| Schedule | `ops.pipeline_schedules` (migration 0015): off by default, 15 / 30 / 60 / 240 min, 60 labelled test default; `PUT /api/v1/pipelines/p2/schedule` (CA, reason, audited); the worker calls `ops.queue_due_schedules()` every 10 s and queues one `timer` run when due |
| Freshness | `ops.dataset_freshness`; `GET /api/v1/pipelines/p2/status` (freshness and schedule; RM included) |
| Tests | `tests/test_landing.py` (envelope check); `modules/pipelines/tests/test_p2_landing_integration.py` (5: lands once with the pseudonymous key and never the customer id; replay lands nothing twice; a malformed event lands rejected with its reason, no location events accepted, raw refuses deletes; an interrupted batch lands nothing and loses nothing; backlog for CA only); `modules/pipelines/tests/test_p2_run_integration.py` (4: a CA run builds, tests and publishes freshness; a failed critical test fails the run and leaves the marts not fresh; RM sees freshness but no runs or controls; the schedule is CA only, audited, and queues one due timer run); E2E `data-pipelines.spec.ts` (CA runs P2 from the UI; RM sees freshness only) |

## Rules implemented

- **Exactly once into raw:** rows are claimed oldest first with `FOR UPDATE SKIP LOCKED` (a second lander skips them), inserted with `ON CONFLICT (event_id) DO NOTHING`, and marked published in the same transaction. A crash rolls back the whole batch; the next pass lands it. Replaying (clearing `published_at`) adds no row.
- **Rejected, never dropped (§10):** an unknown type, a version other than 1, an aggregate other than `order`, non-object data, or `data.order_id` differing from the aggregate lands with `parse_status = rejected` and the reason. Raw is append-only, so rejected rows stay visible.
- **No location events (DDR-78):** they are not event types, so they can never be accepted.
- **Pseudonymous customer key (DDR-116 (5)):** `order.placed` carries `customer_key` = HMAC-SHA256(`PSEUDONYM_KEY`, customer id) from `shared/pseudonym.py`; no event carries the customer id.
- **Backlog warning (DDR-116 (12)):** an oldest waiting event older than 5 minutes is shown as a warning (labelled test default; recorded only).

## Assumptions and integration points

- Batches of at most 500 (DDR-116 (6)); the loop drains a backlog batch after batch, then waits 2 s.
- Events written before Task 12 (thousands of TEST events in local databases) land on the first start; older `order.placed` events have no `customer_key`.
