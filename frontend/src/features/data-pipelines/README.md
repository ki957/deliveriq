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
- Live stage hints refresh the views (DDR-115 (13)); while they are down, polling runs every 2 s and only while a run is queued or running.
- The Data group shows "P2 event landing (outbox → raw)" to a Central Administrator only: waiting events, the oldest one's age, landed and rejected counts, live; a warning when the oldest waits more than 5 min (labelled test default, DDR-116 (12)). The P2 run is on the P2 page.
- The P2 page shows freshness of the real marts and the schedule to every viewer, the note that real marts are empty because every POC order is TEST (DDR-116 (7)), and, for a Central Administrator only, Run ("Build analytics from landed events" or the TEST fault input) and the schedule form (timer on/off, 15–240 min, reason). A Regional Manager is told that P2 runs cover every region and are shown to the CA only.
