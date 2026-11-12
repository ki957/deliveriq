# ADR-003 Schema layout

**Status:** Accepted · **Date:** 2026-11-12

## Context
Sources disagree (X-15): #17 suggests per-domain schemas; the ETL spec suggests `app`/`raw`/`staging`/`analytics`/`ai`/`audit`/`ops`; RAG specs require one schema per portal.

## Decision
Schemas: `app` (transactional tables, incl. outbox), `raw`, `staging`, `analytics`, `synthetic`, `analytics_synthetic`, `ops`, `audit`, `customer_rag`, `kitchen_rag`, `management_rag`. Module ownership inside `app` is by table prefix and service boundaries. The ETL spec's `ai` schema is not used: AI request, routing and eval tables are in `ops`; conversations are in `app`.

## Consequences
- Per-pipeline and per-portal DB roles can be granted per schema (ADR-009, ADR-DATA-003).
- Real and synthetic analytics never share a table (ADR-DATA-004).
- Cross-schema reads are explicit and reviewable in grants.

## References
DDR-25, DDR-74; `DATA_PIPELINE_DESIGN.md` §3; `RAG_AI_DESIGN.md` §16.
