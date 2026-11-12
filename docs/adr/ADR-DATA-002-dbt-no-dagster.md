# ADR-DATA-002 dbt Core; no Dagster

**Status:** Accepted · **Date:** 2026-11-12

## Context
The ETL spec planned Dagster at DE-10. An orchestrator adds a service and RAM for a POC with a handful of jobs.

## Decision
dbt Core on the existing PostgreSQL, run as a subprocess by the worker. Jobs are triggered from the Management UI or the CLI; optional schedules use a timer inside the worker (P2 schedule off by default). Synthetic data lives in `synthetic` and is modelled into `analytics_synthetic`.

## Consequences
- No Dagster UI; run history and stages come from `ops.pipeline_runs` / `ops.pipeline_stage_runs` in the Data Pipelines screen.
- dbt `threads` 2, one heavy job at a time.

## References
DDR-20, DDR-59, DDR-66; `DATA_PIPELINE_DESIGN.md`.
