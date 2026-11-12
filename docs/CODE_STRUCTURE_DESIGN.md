# DeliverIQ — Application Code Structure Design

**Version:** 1.1 (approved 2026-11-12; v1.1 adds `knowledge/`, `ai_models.yaml` and AI shared packages per `RAG_AI_DESIGN.md`)
**Status:** Approved design; implementation not started
**Related:** `DELIVERIQ_EXECUTION_PLAN.md` v2.6 (Tasks 1, 2, 4, 15–17 and every task's review), `RAG_AI_DESIGN.md`, `DOCKER_DEPLOYMENT_DESIGN.md`, `DATA_PIPELINE_DESIGN.md`, `DESIGN_DECISION_REGISTER.md` (DDR-03, 57, 63, 68–71, 76, 80–84), Requirements spec §4.7 and §5.6, Harness blueprint §5, RAG specs (#3 §23, #6 §24, #9 §22).

---

## 1. Objective and scope

A modular monolith that a reviewer can follow:
- one feature lives in one place;
- business rules are separate from HTTP, the database and the UI;
- each AI harness is its own unit;
- dependency directions are enforced by tooling, not just convention.

Scope: repository layout, backend and frontend structure, dependency rules, conventions, API contract flow, data access, dependency management, testing layout, and the code-review checklist.

## 2. Repository layout

```text
deliveriq/
├── .kiro/steering/rules.md        # Kiro build rules (created after the designs)
├── .github/workflows/             # CI jobs per DOCKER_DEPLOYMENT_DESIGN §11
├── docs/                          # planning docs + adr/ + runbooks/
├── data/source/                   # committed read-only SOP copy (hash-checked, DDR-60)
├── knowledge/                     # drafted RAG documents: customer/ kitchen/ management/ (DDR-76, DDR-94)
├── backend/                       # FastAPI app + worker + CLI (one codebase)
├── frontend/                      # React + Vite app (four portals)
├── analytics/dbt/                 # dbt project (staging, core, marts, tests)
├── infra/                         # Dockerfiles, compose.yaml, postgres init, proxy config
├── tests/e2e/                     # Playwright suites, fixtures, screenshot baselines
├── Makefile
├── .env.example  .gitignore  .python-version  .nvmrc
└── README.md
```

## 3. Backend layout

```text
backend/app/
├── main.py                 # app factory, router registration only
├── core/                   # config, db session, security, logging, errors, permissions, time, money
├── shared/                 # events (outbox writer, envelope), idempotency, pagination, geospatial adapter
├── modules/                # business domains, one folder each
│   ├── identity/  customers/  regions/  menu/  pricing/  orders/  payments/
│   ├── kitchen_ops/  recipes/  inventory/  delivery/  promotions/
│   ├── support/  reviews/  reporting/  audit/  realtime/
├── pipelines/
│   ├── framework/          # job queue, runner, stages, run records, retry, cancel
│   ├── p1_sop/  p2_elt/  p3_synthetic/
├── ai/
│   ├── shared/             # model_gateway (adapters, routing, overrides), embeddings (adapters), ingestion, retrieval, guardrails, memory, evaluation, observability
│   └── harnesses/
│       ├── customer/  kitchen/  management_copilot/
│       ├── management_actions/  builder_agent/
├── worker/                 # worker entry point, heartbeat, timer
└── cli/                    # `deliveriq ...` commands (same entry points as the UI)
```

Non-code config sits beside the package: `backend/config/ai_models.yaml` holds LLM providers, logical models and harness routing, with no secrets (DDR-85). It is a Builder Agent protected path (DDR-87).

### 3.1 Business module template

A layer exists only if the module needs it.

```text
modules/orders/
├── api.py          # routes: validate input, check permission, call service, map response
├── schemas.py      # Pydantic request/response models (API contract)
├── service.py      # business rules, transactions, outbox events
├── domain.py       # state machine, invariants, value objects (pure, no I/O)
├── repository.py   # SQLAlchemy queries only
├── models.py       # ORM tables
├── permissions.py  # module permission names and scope checks
└── tests/          # unit (domain/service) + integration (api/repository)
```

## 4. Dependency rules

Enforced in CI with `import-linter`.

| From | May import | Must not import |
|---|---|---|
| `api` | own `schemas`, `service`, `permissions`; `core` | `repository`/`models` directly; other modules' internals |
| `service` | own `domain`, `repository`; other modules' public `service` functions only; `shared` | other modules' `repository`/`models`; `api` |
| `domain` | standard library only | anything with I/O |
| `pipelines`, `worker`, `cli` | module services, `shared`, `core` | module repositories directly |
| `ai/harnesses/<x>` | `ai/shared`; module read services (Copilots); module action services (Operational Actions only) | another harness's package; any `*_rag` other than its own |
| `ai/shared` | `core` | any harness or business module |

These rules make access boundaries a structural property: for example, the Customer harness cannot import Kitchen retrieval code.

## 5. AI harness layout

Same shape for every harness:

```text
ai/harnesses/kitchen/
├── README.md          # pipeline card (see 5.1)
├── prompt.md          # versioned system prompt
├── policy.py          # allowed roles, scope resolver, deny-by-default checks
├── tools.py           # allowlisted tools, typed input/output
├── retrieval.py       # filters + this portal's DB role, version pinning
├── context.py         # bounded, provenance-tagged context builder
├── harness.py         # request lifecycle (Phase 6 §4)
├── validators.py      # output checks, citations, abstention
├── ingestion.py       # K-pipeline stage definitions for this portal
└── tests/             # isolation, injection, role, retrieval, evaluation dataset
```

Harnesses without retrieval (Operational Actions, Builder Agent) omit `retrieval.py` and `ingestion.py`.

### 5.1 Harness README card (required)

Each harness `README.md` documents:
1. Purpose and permitted users
2. Data sources and access boundaries
3. Ingestion and document processing
4. Chunking and metadata strategy
5. Embedding model and vector storage
6. Retrieval and filtering
7. Prompt construction and model invocation
8. Output handling and error handling
9. Logging, evaluation and testing
10. Security controls and authorization checks

Sections that do not apply are marked "Not applicable" with a reason.

## 6. Frontend layout

```text
frontend/src/
├── app/            # router, providers (QueryClient, auth, theme), portal layouts, route guards
├── shared/
│   ├── api/        # generated client + fetch wrapper (auth, errors, correlation id)
│   ├── ui/         # shadcn components themed by tokens; StatusBadge, EmptyState, ErrorState…
│   ├── auth/  realtime/  maps/  hooks/  utils/
│   └── theme/      # tokens.css + one theme per portal (Customer B, Delivery A, Kitchen, Management)
├── portals/
│   ├── customer/  kitchen/  delivery/  management/   # pages + portal navigation only
└── features/
    ├── menu/  cart/  checkout/  orders/  tracking/
    ├── kitchen-queue/  preparation/  recipes/  inventory/
    ├── assignments/  delivery-run/
    ├── staff/  approvals/  reports/  data-pipelines/  knowledge-approval/
    └── ai-copilot/  ops-actions/  builder-agent/
```

Each feature folder holds `api.ts` (TanStack Query hooks), `components/`, `schemas.ts` (Zod form schemas), `types.ts` and `*.test.tsx`.

**Rules:**
- Portals compose features.
- Features never import another feature's internals; shared code moves to `shared/`.
- No feature makes permission decisions on its own. The UI only hides controls based on the backend's `/me/permissions`; the backend enforces.

## 7. Conventions

| Topic | Convention |
|---|---|
| Naming | Python `snake_case`; TS `camelCase`, components `PascalCase`; API paths `/api/v1/<module>/...`, plural nouns |
| Errors | One error envelope (`code`, `message`, `request_id`); stable error codes per module |
| Money | Integer paise in DB and API; formatted only in the UI |
| Time | UTC everywhere; `Asia/Kolkata` only at display |
| Config | One Pydantic `Settings`; no `os.environ` outside `core/config.py` |
| Logging | Structured JSON; correlation ID; redaction filter for OTP, token and phone |
| File size | Soft limit ~300 lines per file; split by responsibility before exceeding it |
| Lint / format / types | Ruff + mypy (strict on `domain` and `service`); ESLint + TypeScript strict + Prettier |
| Docs | Feature and harness README cards; ADRs for decisions; comments only for non-obvious decisions |
| Dead code | CI fails on unused imports; no commented-out code; no TODO without an issue reference |

## 8. Feature card template

Each feature (backend module or frontend feature) has a short `README.md`:
- Purpose and scope
- UI screens, API endpoints, service functions, tables and events
- Permissions
- States handled (loading, empty, success, error, denied)
- Tests
- Assumptions and integration points

## 9. API contract flow (DDR-81)

```text
FastAPI Pydantic schemas → OpenAPI document → openapi-typescript → frontend/src/shared/api/generated (committed)
```

- The generated client is committed so contract changes are visible in diffs.
- CI regenerates it and fails if the committed copy differs.

## 10. Data access (DDR-82)

- Sync SQLAlchemy 2.x with psycopg 3 for repositories and services.
- One session per request (API), per job (worker) and per command (CLI).
- Transaction boundaries live in services, never in routes or repositories.
- FastAPI runs sync endpoints in its threadpool.
- Async is used only for WebSockets, Redis pub/sub and outbound HTTP (httpx to LLM providers and OSRM).
- CPU-heavy work (embedding) runs only in the worker, never in the API event loop.

## 11. Dependency management (DDR-83, DDR-84)

| Area | Tooling |
|---|---|
| Python | uv with `pyproject.toml` + `uv.lock`; dependency groups `api`, `worker`, `dev`; Python 3.12 |
| Images | api target installs `api`; worker target installs `api` + `worker` |
| Node | npm with committed `package-lock.json`; Node 26 pinned (`.nvmrc`, `engines`) |
| Frontend routing | React Router (Requirements spec baseline) |
| Server state / forms | TanStack Query; React Hook Form + Zod |

New dependencies need a stated reason and phase (Requirements spec §19).

## 12. Testing layout

| Layer | Location | Tooling |
|---|---|---|
| Backend unit | `backend/app/**/tests/` (`unit` marker) | pytest |
| Backend integration | same, `integration` marker, real Postgres | pytest |
| Backend security | same, `security` marker (RBAC, scope, isolation) | pytest |
| dbt | `analytics/dbt/tests/` | dbt tests |
| Frontend | `*.test.tsx` beside the code | Vitest + Testing Library |
| E2E, accessibility, visual | `tests/e2e/` | Playwright + axe |

## 13. Code-review checklist

Run at the end of every task. Findings are graded **Blocker / High / Medium / Low**.

- Correctness and completeness
- Architecture and separation of concerns (`import-linter` passes)
- Security and authorization (negative tests present)
- Secret handling
- Error and edge-case handling
- Data integrity
- Logging and observability
- Test coverage
- Naming and readability
- Duplicate or unnecessary code
- Documentation and traceability (feature/harness cards up to date)

## 14. Alternatives and open items

| Chosen | Alternative | Reason |
|---|---|---|
| Domain modules with thin layers | Strict hexagonal ports everywhere | Too much ceremony for a POC |
| Feature folders | Layer-by-type folders (`routers/`, `models/`) | Layer-by-type scatters a feature |
| import-linter enforcement | Convention only | Boundaries become testable |
| OpenAPI-generated client | Hand-written types | Prevents drift |
| Sync data access | Fully async; mixed | One code path for API, worker and CLI |
| React Router | TanStack Router | Spec baseline; no recorded need to change |

**Open items:** none specific to this design. Harness prompts for Operational Actions and Builder Agent are in `RAG_AI_DESIGN.md` §13 (DDR-93).
