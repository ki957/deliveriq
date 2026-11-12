# Pipelines module (Data & Pipelines API)

**Purpose and scope:** list pipelines, inspect runs and queue, cancel or retry them (DATA_PIPELINE_DESIGN §11–12; DDR-63, DDR-64, DDR-105). The API only records requests; the worker executes runs (`app/pipelines`). The Data & Pipelines UI is Task 5C.

| Item | Value |
|---|---|
| UI screens | Management → Data & Pipelines (Task 5C) |
| API endpoints | `GET /api/v1/pipelines` (with last run, `implemented`) · `GET /api/v1/pipelines/runs?pipeline=&limit=` · `POST /api/v1/pipelines/runs` (202) · `GET /api/v1/pipelines/runs/{id}` (stages, errors, dq results) · `POST /api/v1/pipelines/runs/{id}/cancel` · `POST /api/v1/pipelines/runs/{id}/retry` (202) · `GET /api/v1/pipelines/runs/{id}/report` (Markdown download) |
| CLI | `make pipeline NAME=p1_sop` = `python -m app.cli.pipelines run p1_sop --wait` in the api container (same entry point, `trigger = cli`) |
| Service functions | `list_pipelines`, `list_runs`, `run_detail`, `run_report`, `trigger`, `cancel`, `retry`, `trigger_from_cli`, `run_status` |
| Tables | `ops.pipelines`, `ops.pipeline_runs`, `ops.pipeline_stage_runs`, `ops.ingestion_errors`, `ops.dq_results`, `ops.job_queue` (read; insert run + queue row only); `ops.cancel_run()`; `audit.events` |
| Permissions | `pipelines.view`: CA all runs, RM runs of own region only. `pipelines.operate`: CA only. Every other role 403 |
| States | 202 queued · 401 no session · 403 role or CSRF · 404 unknown or out-of-scope run (existence not revealed) · 409 already active / not cancellable / not retryable / not implemented yet · 422 bad input |
| Tests | `core/tests/test_permissions.py` (policy); `tests/test_fault_inputs.py` (production refusal, test flag, images); `tests/test_pipelines_integration.py` (RBAC matrix, real P1 run through the worker, idempotency, cancel, retry, one active run, audit, DB role limits, fault runs quarantine or fail with nothing loaded) |

## Rules implemented

- **Deny by default (DDR-64):** RM calling trigger, cancel or retry directly gets 403; another region's RM gets 404 on the run and an empty list.
- **One active run per pipeline (DDR-67 rule 5):** a unique index; a second request gets 409.
- **Cancel (DDR-105):** queued runs are cancelled at once through `ops.cancel_run()`; running runs get `cancel_requested` and stop at the next stage boundary.
- **Retry:** only failed or cancelled runs; the new run keeps `pipeline`, `input_ref`, `is_test`, region, and sets `retry_of`.
- **Audit:** run, cancel and retry each write `audit.events` (actor, role, region, request ID).
- **Region:** P1 runs carry the region of `KIT-CHN-001` (DDR-105).
- **Inputs:** P1 accepts `sop` (default) and the TEST fault inputs `fault:records` and `fault:structural` (DDR-65, DDR-104). Fault inputs are refused with 403 outside local/test, always run as test runs, and the worker refuses them again unless the run is a test run in local/test. `make pipeline NAME=p1_sop INPUT=fault:records`.

## Assumptions and integration points

- `TRIGGERABLE` in `service.py` lists pipelines that have code; later tasks add P2 (Task 12), P3 (14), K3 (15), K2 (16) and K1 (17).
- The UI polls run detail every 2 s until WebSockets (Task 11).
