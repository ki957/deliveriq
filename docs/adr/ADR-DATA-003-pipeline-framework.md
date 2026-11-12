# ADR-DATA-003 Shared pipeline-runs framework

**Status:** Accepted · **Date:** 2026-11-12

## Context
P1 (SOP ETL), P2 (operational ELT), P3 (synthetic data) and K1–K3 (RAG ingestion) all need runs, stages, errors, retries and a UI with real status.

## Decision
One framework: PostgreSQL job queue, a single heartbeating worker, and tables `ops.pipeline_runs`, `ops.pipeline_stage_runs`, `ops.ingestion_errors`, `ops.dq_results`, `ops.source_registry`. Each job connects with its own DB role. The CA runs, cancels and retries; the RM views own-region runs. Operating rules per DDR-67.

## Consequences
- Every status shown in the UI comes from persisted execution, never simulated states.
- The CLI uses the same entry points as the UI.
- The Task 0 source-registry check gains its DB write to `ops.source_registry` in Task 5.

## References
DDR-63, DDR-64, DDR-67; `DATA_PIPELINE_DESIGN.md` §5, §11–12.
