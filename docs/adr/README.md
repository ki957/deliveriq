# Architecture Decision Records

One file per ADR from `DESIGN_DECISION_REGISTER.md` Part D. Each records context, decision, consequences and the DDRs it comes from. The register stays the master record; an ADR changes only through an approved DDR.

Format: **Status** (Accepted / Superseded), **Date**, **Context**, **Decision**, **Consequences**, **References**.

| ADR | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-modular-monolith.md) | Modular monolith boundaries | Accepted |
| [ADR-002](ADR-002-postgresql-only.md) | PostgreSQL only; no MongoDB | Accepted |
| [ADR-003](ADR-003-schema-layout.md) | Schema layout | Accepted |
| [ADR-004](ADR-004-outbox-and-worker.md) | Outbox + worker; no message broker | Accepted |
| [ADR-005](ADR-005-canonical-status-machines.md) | Canonical status machines | Accepted |
| [ADR-006](ADR-006-rbac-and-scope.md) | RBAC with region and kitchen scope | Accepted |
| [ADR-007](ADR-007-provider-neutral-model-gateway.md) | Provider-neutral model gateway | Accepted |
| [ADR-008](ADR-008-embedding-adapter-and-benchmark.md) | Embedding adapter and selection by benchmark | Accepted |
| [ADR-009](ADR-009-per-portal-rag-schemas.md) | Per-portal RAG schemas and DB roles | Accepted |
| [ADR-012](ADR-012-docker-compose-ram-budget.md) | Docker Compose with profiles; RAM budget | Accepted |
| [ADR-013](ADR-013-no-minio.md) | No MinIO, Parquet or DuckDB initially | Accepted |
| [ADR-UI-001](ADR-UI-001-tailwind-shadcn.md) | Tailwind + shadcn/ui | Accepted |
| [ADR-UI-002](ADR-UI-002-portal-themes.md) | Per-portal theme tokens and palettes | Accepted |
| [ADR-DATA-001](ADR-DATA-001-sop-sole-recipe-source.md) | SOP Markdown as the sole recipe source | Accepted |
| [ADR-DATA-002](ADR-DATA-002-dbt-no-dagster.md) | dbt Core; no Dagster | Accepted |
| [ADR-DATA-003](ADR-DATA-003-pipeline-framework.md) | Shared pipeline-runs framework | Accepted |
| [ADR-DATA-004](ADR-DATA-004-synthetic-analytics.md) | Synthetic data through shared dbt models | Accepted |
| [ADR-CODE-001](ADR-CODE-001-import-linter.md) | Module boundaries enforced with import-linter | Accepted |
| [ADR-CODE-002](ADR-CODE-002-openapi-client.md) | OpenAPI-generated TypeScript client | Accepted |
| [ADR-CODE-003](ADR-CODE-003-sync-data-access.md) | Sync data access | Accepted |
| [ADR-AI-001](ADR-AI-001-read-only-ai.md) | Read-only AI except Operational Actions and Builder Agent | Accepted |
| [ADR-AI-002](ADR-AI-002-builder-agent-sandbox.md) | Builder Agent sandbox | Accepted |
| [ADR-AI-003](ADR-AI-003-operational-action-tools.md) | Operational Action tools | Accepted |
| [ADR-AI-004](ADR-AI-004-local-cpu-embeddings.md) | Local CPU embeddings | Accepted |
| [ADR-TEST-001](ADR-TEST-001-accessibility-visual-tests.md) | axe-core, device emulation, screenshot regression | Accepted |

Numbers ADR-010 and ADR-011 are unassigned.
