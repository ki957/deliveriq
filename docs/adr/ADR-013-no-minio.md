# ADR-013 No MinIO, Parquet or DuckDB initially

**Status:** Accepted · **Date:** 2026-11-12

## Context
#10 §14 and #11 list MinIO/Parquet/DuckDB as baseline; other documents treat them as optional. RAM is limited.

## Decision
None of them is in the initial Compose stack. DuckDB or Parquet may be used as files inside data-engineering tooling if a task needs them. MinIO is added only if RAG source binaries need object storage.

## Consequences
- One fewer container; analytics stays in PostgreSQL (dbt).
- Adding any of them later needs a DDR and this ADR updated.

## References
DDR-28.
