# Pipelines: framework, worker and P1 SOP import

**Purpose and scope:** the shared run framework, the single heartbeating worker and P1, the SOP master-data ETL (DATA_PIPELINE_DESIGN §2.3, §5, §11; KITCHEN_SOURCE_VALIDATION §7–9; DDR-63, DDR-67, DDR-102–DDR-105). Fault injection, fixtures and the recipe workflow are 5B.

| Item | Value |
|---|---|
| Entry points | Worker `python -m app.worker` (Compose profile `worker`, `make worker`); health `python -m app.worker --health`. Runs are queued by the API or `make pipeline NAME=p1_sop` |
| Framework | `framework/queue.py` (claim with `FOR UPDATE SKIP LOCKED`, heartbeat, backoff, stale release), `runner.py` (connects as the pipeline's own role, classifies failures), `context.py` (stage, error, dq and report records on an autocommit connection), `registry.py` |
| P1 | `p1_sop/parser.py` (line parser), `checks.py` (record faults, duplicates, reconciliation), `review_rules.py` (KITCHEN_SOURCE_VALIDATION §5.1–5.3 verbatim), `report.py` (deterministic), `pipeline.py` (stages) |
| Tables | `ops.*` run records, `ops.workers`, `staging.sop_cards`, `staging.sop_ingredient_lines`, `app.ingredients`, `app.recipes`, `app.recipe_versions`, `app.recipe_ingredients`, `app.recipe_review_items` (migration 0007) |
| DB roles | `worker`: claim and heartbeat only (no `app` access). `p1_sop`: P1 data and its own run records |
| Inputs | Read-only mounts: `data/source` (hash-checked), `docs/SOURCE_DOCUMENT_INVENTORY.md`, `backend/test_inputs` (5B; never copied into images) |
| Tests | `p1_sop/tests/test_real_sop.py`, `test_parser_rules.py` (unit); `framework/tests/test_queue_integration.py`; `modules/pipelines/tests/test_pipelines_integration.py` |

## P1 stages

register (SHA-256 against the inventory; mismatch fails) → parse → validate structure (fails with nothing loaded) → transform (footer stripping logged) → quality checks → stage → load DRAFT → reconcile → report.

## Rules implemented

- **Counts are proved, never assumed:** 104 cards and 616 ingredient lines must match the SOP's own claims, with no gaps in MENU001–MENU104, before anything loads.
- **DRAFT only (DDR-50):** 102 cards load as `DRAFT`; MENU008 and MENU057 (identical BOMs) load as `QUARANTINED_DUPLICATE_CANDIDATE`, neither merged nor deleted (DDR-13). The reconcile stage fails the run if any SOP version is `ACTIVE`.
- **Lineage (§9):** every version stores file, SHA-256, line range, card ID, page, candidate category and run; every ingredient line stores its source line and original text.
- **Idempotent (DDR-103):** deterministic uuid5 IDs and insert-if-absent; a re-run adds zero rows and produces an identical report.
- **Review queue (DDR-102, DDR-103):** 8 missing batch recipes, composite and ambiguous ingredients become open review items with reasons and source references; open items block submission (trigger).
- **Failures (DDR-67):** transient errors retry after 5 s, 30 s, 2 min, then fail as `transient`; data and structural errors never retry; a worker with no heartbeat for 60 s has its job released.
- **Report:** stored in `ops.pipeline_runs.report_md`; states that the PDF and Excel sources are unavailable.

## Measured (2026-11-12, laptop)

P1 runs in about 1–2 s. Worker 44 MiB idle, about 80 MiB peak during P1 (limit 1.2 GB).
