# Data & Pipelines feature

**Purpose and scope:** the Management "Data & Pipelines" area (MG-12; DATA_PIPELINE_DESIGN §12; DDR-63, DDR-64, DDR-105, DDR-108). Overview, pipeline page with run history and the Run control, and run detail. The P2 schedule toggle, freshness and outbox backlog arrive with P2 (Task 12); knowledge approval with Task 15.

| Item          | Value                                                                                                                                                                                                                   |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UI screens    | `/management/data-pipelines`, `/management/data-pipelines/:pipeline`, `/management/data-pipelines/runs/:runId`                                                                                                          |
| API endpoints | `GET /api/v1/pipelines`, `GET/POST /api/v1/pipelines/runs`, `GET /api/v1/pipelines/runs/{id}`, `POST …/cancel`, `POST …/retry`, `GET …/report` (generated client)                                                       |
| Permissions   | `pipelines.view` for every screen (CA; RM own region, scoped by the backend). `pipelines.operate` (CA) shows Run, Cancel and Retry. Others see the denied state                                                         |
| States        | Loading, empty (no runs), error, denied (missing permission or backend 403), not found (404), success; active runs refresh every 2 s                                                                                    |
| Tests         | `data-pipelines.test.tsx` (states, CA vs RM controls, request bodies, polling rule); `tests/e2e/specs/data-pipelines.spec.ts` (P1 from the UI with persisted counts, fault run reasons, RM view only, axe, screenshots) |

## Behaviour

- Everything shown comes from the run records in the database; nothing is hardcoded.
- Pipelines without code are listed as "Not built yet (Task N)" and cannot be opened.
- The Run control offers only the inputs the backend lists for this environment; TEST fault inputs appear only in local/test and are labelled.
- Test runs carry a "Test run" badge everywhere.
- Polling stops when the run is no longer queued or running (WebSockets replace it in Task 11).
