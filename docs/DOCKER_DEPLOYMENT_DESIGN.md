# DeliverIQ — Docker & Deployment Design

**Version:** 1.5 (2026-11-12; v1.0 approved 2026-11-12; v1.3 aligns AI egress and keys with `RAG_AI_DESIGN.md`, DDR-85; v1.4 records four owner-approved Task 2 deviations, §17; v1.5 adds Task 5A deviations 6–7)
**Status:** Approved design; `core` profile implemented in Task 2
**Scope:** Local containerised stack for the portfolio demo (DDR-49) on the target laptop, plus GitHub Actions CI. Out of scope: cloud hosting, Kubernetes, TLS, production secret management, backups beyond local dump/restore.
**Related:** `DELIVERIQ_EXECUTION_PLAN.md` v2.3 (Tasks 2, 15B, 15C, 21, 22), `DESIGN_DECISION_REGISTER.md` (DDR-48, 55, 59, 60, 62, 63, 65, 67, 70, 71).

---

## 1. Target environment (measured 2026-11-12)

| Item | Value | Design consequence |
|---|---|---|
| Hardware | Lenovo IdeaPad Slim 5 16IMH9, Intel Core Ultra 5 125H, 16 GB | — |
| OS | Ubuntu 24.04.4 LTS, kernel 7.0 | — |
| Docker / Compose | 29.4.2 / v5.1.3, **rootful**, user in `docker` group | Bind-mount ownership handled with build-time UID/GID. The `docker` group is root-equivalent, so no Docker socket is mounted inside any app container |
| RAM | 15 GiB total; ~8.8 GiB available with the desktop running; 4 GiB swap | Container budget ~8 GB; one heavy profile at a time; `mem_limit` from the start; no zram (owner decision) |
| Disk | 371 GB free | No constraint |
| Host Python | 3.15 via conda (base) | Backend runs Python 3.12 in containers; host tooling uses `uv` with pinned 3.12 |
| Node / npm | v26.11.1 / 11.20 | Pinned via `.nvmrc` and `engines`; Node 24 fallback if Vite is incompatible |
| Git | 2.43 | — |
| GitHub CLI | Not installed | Not required: SSH for git, fine-grained token for the Builder Agent |

## 2. Host setup (performed by Kiro CLI during the build)

These steps are executed by Kiro CLI during the build stage. Any change to the owner's user or shell configuration (e.g. conda auto-activation) requires owner confirmation at the time (DDR-79).
1. Install `uv`; run `uv python install 3.12`. The repo contains `.python-version` = `3.12`.
2. Disable conda auto-activation: `conda config --set auto_activate_base false` (owner approved).
3. Node 26 pinned (`.nvmrc`, `package.json` `engines`). Fallback: Node 24 via `nvm`/`fnm`, without changing system Node.
4. GitHub: SSH key for git; fine-grained token (repo contents + pull requests only) in local `.env` for Task 15C.
5. No zram.

## 3. Services and profiles

| Service | Image | Profile | Purpose | `mem_limit` (start) | RAM estimate* |
|---|---|---|---|---|---|
| `postgres` | Custom: pgvector 0.8.1 / PG16 (bookworm) + PostGIS 3 (§17) | `core` | Source of truth, analytics, RAG vectors | 768 MB | 300–500 MB |
| `redis` | Redis 7 alpine | `core` | WebSocket fan-out, rate limits, cache | 128 MB | 30–64 MB |
| `migrate` | `deliveriq-backend` (api target) | `core`, one-off | `alembic upgrade head`, then exits | — | short-lived |
| `api` | `deliveriq-backend` (api target) | `core` | FastAPI, one Uvicorn worker | 512 MB | 150–300 MB |
| `worker` | `deliveriq-backend` (worker target) | `worker` | Job queue, outbox→raw loop, dbt subprocess, embeddings, timer schedules | 1.2 GB | 200 MB idle; 0.6–1 GB peak |
| `osrm-prep` | OSRM backend | `osrm`, one-off | Build the Chennai graph | — | one-time, higher |
| `osrm` | OSRM backend | `osrm` | Road distance (DDR-55) | 1 GB | few hundred MB (to measure) |
| `e2e` | Official Playwright image, Chromium only | `e2e` | Headless E2E, axe, screenshots; 2 workers | 2 GB | 1–1.5 GB |
| `web` | nginx alpine | `demo` | Serves the built SPA | 64 MB | ~10 MB |
| `api` (demo mode) | same api image, no `--reload` | `demo` | Demo/E2E target | 512 MB | as api |
| `agent` | `deliveriq-agent` | `agent` | Builder Agent sandbox (DDR-70) | 1 GB, 1 CPU | ≤ 1 GB |
| `egress-proxy` | small allowlisting proxy (e.g. tinyproxy) | `agent` | Allows only GitHub + configured LLM provider hosts | 64 MB | ~10 MB |

*Estimates. Task 2 replaces them with `docker stats` measurements and adjusts the `mem_limit`s.

The frontend in development is **not** containerised: Vite runs on the host (DDR-62).

### 3.1 Profile rules (approved)

| Scenario | Profiles | Estimate | Allowed together |
|---|---|---|---|
| Daily dev | core | 0.5–0.9 GB | — |
| Pipelines | core + worker | 1–2 GB | — |
| E2E | core/demo + worker + e2e | 2.5–3.5 GB | **Not** with osrm or agent |
| Road-rule tests | core + osrm | ~1.5 GB | Not with e2e or agent |
| Builder task | core + agent | ≤ 2 GB | Not with e2e or osrm |

Makefile targets stop conflicting profiles before starting `e2e`, `osrm` or `agent`. Running all profiles together is unsupported.

## 4. Images

- **Backend:** one multi-stage Dockerfile with targets `api` and `worker`, built from the same source tree.
  - Builder stage installs locked dependencies.
  - Runtime stage: Python 3.12 slim, non-root user, no compilers.
  - Dependencies come from `uv.lock` (DDR-83). The `api` target installs the uv `api` group only; the `worker` target installs `api` + `worker` (dbt, ONNX Runtime).
  - `migrate` uses the `api` target.
- **UID/GID:** build args `APP_UID`/`APP_GID` default to the host user's IDs, so bind-mounted files stay owned by the owner under rootful Docker.
- **Postgres:** `pgvector/pgvector:0.8.1-pg16-bookworm` base plus `postgresql-16-postgis-3` from PGDG (§17); init scripts create roles (§6.3) and extensions.
- **Agent:** based on the backend image plus git and test tooling; no database client configuration.
- **Frontend demo:** multi-stage Node 26 build → nginx alpine static image.
- All base images are pinned to exact tags at build time, and the tags are recorded in the repo.

## 5. Networks and ports

| Network | Members | Notes |
|---|---|---|
| `backend` (internal) | postgres, redis, migrate, api, worker, osrm, web, e2e | App traffic |
| `edge` | api, postgres (and later osrm, web) | Plain bridge used only to publish `127.0.0.1` ports; internal networks cannot publish (§17) |
| `agent_net` (internal) | agent, egress-proxy | Agent has no route to `backend` |
| `egress` | egress-proxy only | Outbound internet; proxy allowlist = GitHub + configured LLM provider hosts (generated from `ai_models.yaml` at `make agent`) |

Published ports bind to `127.0.0.1` only: API 8000, Postgres 5433 by default (`POSTGRES_HOST_PORT`; the owner's host already uses 5432), OSRM 5000 (when running), web 8080 (demo). Redis is not published.

## 6. Configuration and secrets

### 6.1 Files

- `.env.example` is committed with placeholders only. `.env` is git-ignored and created by the owner.
- Per-service env files are derived from `.env`:
  - `api` / `worker`: DB URLs, Redis URL, LLM provider keys (`GROQ_API_KEY`, optional `OPENROUTER_API_KEY`), app settings.
  - `agent`: only the key of the provider its route uses, the GitHub fine-grained token and the proxy address. Never DB or Redis credentials.
- Pydantic Settings validates at startup. Missing values fail fast, reporting the key name only, never the value.
- Secrets are never baked into images, layers, logs or docs.

### 6.2 `APP_ENV`

Values: `local`, `test`, `production`. It gates MOCK_OTP, the fixture loader (DDR-48), fault injection (DDR-65) and `reset-test-data` (DDR-67). The demo profile runs with `APP_ENV=production` semantics for leak-control checks, unless explicitly started as a test demo.

### 6.3 Database roles (DDR-63)

Created by Postgres init scripts, with passwords from `.env`:

| Role | Purpose |
|---|---|
| `app_migrator` | DDL (migrations) |
| `app_api` | API runtime |
| `p1_sop` | P1 SOP master-data ETL |
| `p2_elt` | P2 operational ELT |
| `p3_synth` | P3 synthetic generation |
| `rag_customer` | Customer RAG ingestion |
| `rag_kitchen` | Kitchen RAG ingestion |
| `rag_management` | Management RAG ingestion |

Each pipeline role can write only its own target schema; tested in Task 3.

### 6.4 CI secrets

GitHub Actions secrets only. Tests use the mock LLM adapter by default, so CI needs no LLM provider key.

## 7. Volumes

| Volume | Contents | Survives `down` |
|---|---|---|
| `pg_data` | PostgreSQL data | Yes; deleted only by `down -v` (documented as destructive) |
| `osrm_data` | Prepared Chennai graph | Yes |
| `models_cache` | Embedding model files | Yes |
| `playwright_cache` | Browser binaries | Yes |
| agent workspace | tmpfs per run | No (by design) |

`data/source/` is bind-mounted read-only into the worker.

## 8. Health checks and startup order

```text
postgres (pg_isready) ─► migrate (must complete successfully) ─► api (/health/ready: DB + Redis)
redis (redis-cli ping) ──────────────────────────────────────────┘
api ready ─► worker (recent heartbeat row in ops.workers; §17 #7)
osrm-prep (completes) ─► osrm (/health)
egress-proxy (healthy) ─► agent
```

- `depends_on` uses `service_healthy` / `service_completed_successfully`.
- Migrations never run inside the API on startup (Requirements spec §10.3).
- `/health/live` and `/health/ready` are separate.
- Restart policy: `unless-stopped` for long-running services; `no` for one-off jobs and the agent.
- Logs: json-file, 10 MB × 3.

## 9. Developer workflow (Makefile)

| Target | Action |
|---|---|
| `make up` / `make down` | Start/stop `core` (data preserved) |
| `make worker` | Add the worker |
| `make db-roles` | Create any missing DB roles on an existing volume (run by `make up` before migrations; §17 #6) |
| `make osrm-setup` | One-time Chennai extract download + graph prep |
| `make osrm` | Start osrm (stops e2e/agent first) |
| `make migrate` / `make seed-test` | Migrations; test fixtures (local/test only) |
| `make test` / `make lint` | Backend in container; frontend on host |
| `make e2e` | Start demo + e2e (stops osrm/agent first) |
| `make agent` | Owner starts the Builder sandbox for a queued task (manual, approved) |
| `make demo` | Production-style build: api + web |
| `make stats` | `docker stats` snapshot |
| `make reset-test-data` | CLI reset, local/test only |
| `make backup` / `make restore` | `pg_dump` to git-ignored `./backups` |

Backend hot reload in dev: source bind-mounted, Uvicorn `--reload`. Not used in `demo`.

## 10. Builder Agent isolation (DDR-70, DDR-71)

- **Start:** the API only queues a task. The owner runs `make agent`; no Docker socket in any app container.
- **Workspace:** throwaway repo copy on tmpfs; the container is removed after the task.
- **Network:** only via the egress-proxy, which allowlists GitHub and the configured LLM provider hosts; no route to postgres or redis.
- **Limits:** 1 GB RAM, 1 CPU; unit tests only inside the sandbox; Playwright runs in CI.
- **Credentials:** the routed provider's key + fine-grained GitHub token (contents + pull requests); branch protection on `main`.

## 11. CI (GitHub Actions)

| Job | Content |
|---|---|
| `source-integrity` | Committed source copies hash-checked against the inventory (DDR-60) |
| `backend` | Lint, type check, pytest with Postgres (PostGIS + pgvector) and Redis service containers |
| `frontend` | Lint, type check, Vitest, build (Node 26) |
| `e2e` | PRs to `main`: Compose demo + worker + e2e; axe; screenshots |
| `images` | Build backend, agent and web images; optional vulnerability scan |

Branch protection on `main` requires these checks.

## 12. Failure handling

| Failure | Behaviour |
|---|---|
| Postgres down | API readiness fails; worker pauses polling and retries with backoff (DDR-67) |
| Redis down | Realtime falls back to REST polling; no data loss |
| OSRM not running | Adapter uses the labelled stub; UI shows "road distance: estimated" |
| LLM provider unavailable | Optional fallback if enabled; otherwise AI shown as unavailable; core flows unaffected (PL-19) |
| Worker crash | Jobs with a stale heartbeat are released and marked failed/retryable |
| Memory pressure | `mem_limit` stops one container, not the desktop; profile rules prevent heavy overlaps |

## 13. Security summary

- Non-root containers; read-only root filesystem where practical.
- No Docker socket in app containers (rootful Docker + `docker` group is root-equivalent).
- Ports bound to localhost only.
- Agent network isolated behind an allowlisting proxy; no DB/Redis credentials in the agent env.
- Secrets only in `.env` / Actions secrets.

## 14. Acceptance criteria (Task 2 and related)

1. Clean clone → `.env` from example → `make up` → core services healthy; `migrate` completes.
2. `down` then `up` preserves data.
3. Each profile starts only when requested; Makefile targets stop conflicting profiles.
4. The agent container cannot connect to postgres or redis; egress to non-allowlisted hosts is blocked (tested in Task 15B).
5. The `api` env does not contain the GitHub token; the `agent` env does not contain DB/Redis credentials.
6. Memory measured for each scenario in §3.1; `mem_limit`s adjusted and recorded.
7. Bind-mounted files remain owned by the host user.
8. Setup steps tested on the target Ubuntu 24.04 laptop.

## 15. Alternatives considered

| Chosen | Alternative | Reason |
|---|---|---|
| Vite on host in dev | Frontend dev container | Avoids a duplicate Node runtime; faster reload |
| One backend image, two targets | Separate codebases/images | Prevents API/worker drift; smaller API image |
| Explicit `migrate` job | Migrate on API start | Spec forbids implicit migrations |
| Postgres job queue | Celery/RQ on Redis | No extra dependency; Redis not durable here |
| Manual `make agent` | Launcher with Docker socket; rootless Docker | Safest for the POC; no socket exposure |
| Allowlisting egress proxy | Open egress | Real network control |
| e2e container | Host-only Playwright | Owner decision; reproducible browser environment |
| Makefile | just / Taskfile | No extra tool |

## 16. Open items affecting this design

- ~~Exact image tags pinned at Task 2.~~ Done: base images pinned by digest in the Dockerfiles and Compose.
- Real `mem_limit` values after measurement. Task 2 idle baseline (`core`): api 90 MiB, postgres 25 MiB, redis 5 MiB. Loaded values measured with worker/e2e (Tasks 5, 6).
- Conda auto-activation (§2 step 2) not yet changed: not needed so far (uv and containers ignore conda); owner to confirm when wanted.
- Egress proxy allowlist hostnames confirmed when the provider and GitHub endpoints are configured (Task 15B).
- Node 26 / Vite compatibility confirmed at frontend scaffold.

## 17. Deviations approved during Task 2 (owner, 2026-11-12)

| # | Design said | Implemented | Reason |
|---|---|---|---|
| 1 | PostGIS 16 base image + pgvector | `pgvector/pgvector:0.8.1-pg16-bookworm` + PostGIS 3 (3.7.0) from PGDG apt, with the PostgreSQL 16 server packages upgraded in the same step (fix found in Task 4B CI) | `postgis/postgis:16-3.5` is Debian bullseye; its PGDG apt repository returns 404, so pgvector could not be installed. PGDG builds PostGIS against the latest 16.x minor; a newer PostGIS on the base image's older server fails at `CREATE EXTENSION` (undefined symbol), so server and PostGIS are installed together |
| 2 | Postgres on host port 5432 | Host port 5433 by default (`POSTGRES_HOST_PORT`) | The owner's laptop already runs a PostgreSQL service on 5432; it was left untouched |
| 3 | Networks `backend`, `agent_net`, `egress` | Plus `edge` for published ports | Docker cannot publish ports from an `internal` network; Redis and `migrate` stay internal-only |
| 4 | All profiles defined in Task 2 | Each profile is added with the task that builds its service (`e2e`/`demo` Task 4+, `worker` Task 5, `osrm` Task 9, `agent` Task 15B) | No profile starts a container without real code behind it |
| 5 (Task 4B, approved 2026-11-12) | `e2e` runs headless against the `demo` web service | `e2e` builds the SPA with `vite build` and serves it with `vite preview` inside the pinned Playwright image, proxying `/api` to `api:8000`; it joins `backend` and `edge` (npm registry for `npm ci`); works on copies in `/tmp`, writing only screenshots and failure artefacts back to the repo | No `demo`/`web` image exists yet; keeps screenshot baselines identical locally and in CI |
| 6 (Task 5A, approved 2026-11-12) | DB roles are created only by the Postgres init script on an empty volume | The init script is idempotent; `make up` starts postgres, runs it (`make db-roles`), then migrates | The ninth role `worker` (DDR-105) must exist on volumes created before Task 5; migration 0007 fails with a clear message if it is missing |
| 7 (Task 5A, approved 2026-11-12) | Worker health: heartbeat row in `ops` + `/health` | Health check `python -m app.worker --health`: a heartbeat from this host within 30 s; no HTTP endpoint | The worker serves no HTTP; a recent heartbeat proves the loop and DB access |
