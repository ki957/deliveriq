# DeliverIQ

A cloud-kitchen platform for one kitchen in Chennai, built as a portfolio/interview POC. It has four role-based portals (Customer, Kitchen, Delivery Agent, Unified Management), an ETL/ELT data platform and five AI harnesses, sized to run on a 16 GB laptop.

> Status: under construction, milestone by milestone. See `docs/DELIVERIQ_EXECUTION_PLAN.md`.

## Stack

React + TypeScript + Vite + Tailwind + shadcn/ui · FastAPI modular monolith · PostgreSQL + PostGIS + pgvector · Redis · dbt Core · Leaflet + OpenStreetMap + OSRM · provider-neutral LLM gateway (Groq by default) · local CPU embeddings · Docker Compose · GitHub Actions.

## Repository layout

| Path | Contents |
|---|---|
| `docs/` | Planning docs, decision register, designs, `adr/`, `runbooks/` |
| `.kiro/steering/rules.md` | Build rules for Kiro |
| `data/source/` | Read-only, hash-checked copies of the 21 source documents (`data/SOURCE_PROVENANCE.md`) |
| `knowledge/` | RAG knowledge documents drafted from sources, approved in-app |
| `backend/` | FastAPI app, worker and CLI (`backend/app`), config (`backend/config`) |
| `frontend/` | React app for the four portals |
| `analytics/dbt/` | dbt project |
| `infra/` | Dockerfiles, Compose, Postgres init, proxy config |
| `tests/e2e/` | Playwright suites |

## Planning documents

Start with `docs/DELIVERIQ_EXECUTION_PLAN.md`, then:
- `docs/DESIGN_DECISION_REGISTER.md`: every decision (DDR-nn)
- `docs/PORTAL_REQUIREMENTS_MATRIX.md`: requirements per portal and the AI guardrail matrix
- `docs/DOCKER_DEPLOYMENT_DESIGN.md`, `docs/DATA_PIPELINE_DESIGN.md`, `docs/CODE_STRUCTURE_DESIGN.md`, `docs/RAG_AI_DESIGN.md`
- `docs/SOURCE_DOCUMENT_INVENTORY.md`, `docs/KITCHEN_SOURCE_VALIDATION.md`

## Getting started (current state)

Requires uv, Python 3.12 and Node 26 (`.python-version`, `.nvmrc`).

```bash
make install         # create .venv with locked dev tools
make check           # lint, types, import contracts, tests, source hash check
```

Docker Compose targets arrive in Task 2. Copy `.env.example` to `.env` only when a task needs it; never commit `.env`.

## Data honesty

- All demo dishes are synthetic `TEST –` items. No real SOP recipe is activated.
- Simulated payments, GPS and synthetic analytics are always labelled.
- Source documents are never edited; CI verifies their hashes.
