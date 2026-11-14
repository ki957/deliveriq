# passon.md: DeliverIQ handover guide for Claude Code

**Written:** 2026-11-12 by Kiro; **last updated** after Task 13 (reports). **For:** Claude Code, continuing the build.
**Read this file first.** It tells you where the project stands, what to read, how to work, and what to build next. `CLAUDE.md` loads it and `.kiro/steering/rules.md` (the binding rules) every session.

> ## ⛔ Do not (each of these has broken something, or would)
> 1. **Never edit** `/home/k/Downloads/task1/` or `data/source/**`. `make verify-sources` must stay 21/21.
> 2. **Never print or commit `.env` values**; name secrets by key only. The guard hook blocks staged secret-looking files.
> 3. **Never activate an SOP recipe** or publish a non-`TEST –` dish (DDR-50). Never let the API write `is_test_fixture`; new tables with TEST-derived rows need a derived flag plus a `fixture_guard.py` entry.
> 4. **Never invent values** (prices, thresholds, rules, formulas, copy for business rules). Put them on the decision sheet.
> 5. **Never `git add .` / `-A`, push `main`, force-push, `reset --hard`, `clean -f`, `--no-verify`, or change git config.** The hook blocks these. The owner merges.
> 6. **Never hand-edit or prettier-format** `frontend/src/shared/api/generated/`; regenerate with `make openapi` and `npm run api:generate`.
> 7. **After editing a migration, rebuild the image** (`make up` builds; or `docker compose … build migrate`). The migrate container does not bind-mount migrations.
> 8. **Never leave shared TEST state dirty.** Tests and E2E restore what they change; run `make reset-fixtures` before and after test runs.
> 9. **No broad `sed`/regex edits across files.** Edit precisely; re-read after formatters run.
> 10. **No heavy jobs together** (e2e, dbt, embeddings, agent, osrm-prep); `free -h` ≥ 2 GB first; stop the stack after work.

---

## 1. What DeliverIQ is (one paragraph)

A portfolio/interview POC of a cloud-kitchen platform for **one kitchen in Chennai**. It has four role-based portals:
- **Customer**
- **Kitchen** (Kitchen Staff, Kitchen Manager)
- **Delivery Agent**
- **Unified Management** (Regional Manager, Central Administrator)

It also has an ETL/ELT data platform (pipelines P1–P3, dbt) and five AI harnesses. It runs on the owner's **16 GB Ubuntu laptop** with Docker Compose. Every dish is a synthetic `TEST –` dish, and no real Kitchen SOP recipe is ever activated (DDR-50).

---

## 2. Status at handover

Tasks 0–13 are merged; `main` is at `1465b13` (PR #24, Task 13 reports). This handover refresh is on `tooling-handover-refresh`. The last DDR is **DDR-117**; migration head is **0016**. **Task 14 is next and not planned yet.**

| Task | Scope | State |
|---|---|---|
| 0 | Source registry, hashing, ADRs | ✅ merged (PR #1) |
| 1 | Repo bootstrap | ✅ merged (PR #2) |
| 2 | Engineering foundation (Compose, Make, CI) | ✅ merged (PR #3) |
| 3 | Data model, migrations 0001–0005, state machines | ✅ merged (PR #4) |
| 4A / 4B | Identity, OTP, sessions, RBAC / four portal shells, generated API client | ✅ merged (PR #5, #6) |
| 5A / 5B / 5C | Pipeline framework + worker + P1 SOP import / recipe approval, menu publication, fixtures / pipelines and approvals UI | ✅ merged (PR #7, #8, #9) |
| 7 | Payments (simulated), order state machines, outbox (built before 6, owner choice) | ✅ merged (PR #10) |
| 6A / 6B | Customer serviceability, cart, pricing, checkout API / customer UI | ✅ merged (PR #11, #12) |
| 8A | Kitchen operations and inventory backend (migration 0010, DDR-111) | ✅ merged (PR #13) |
| tooling | `CLAUDE.md`, `.claude/` commands + hook, `make reset-fixtures`, this guide | ✅ merged (PR #14) |
| 8B | Kitchen + Management UI for Task 8, tablet + KDS E2E (DDR-112) | ✅ merged (PR #15) |
| 9A | Delivery backend (migration 0011, DDR-113) | ✅ merged (PR #16) |
| 9B | Delivery PWA UI | ✅ merged (PR #17) |
| 10A | Management backend (DDR-114) | ✅ merged (PR #18) |
| 10B | Management UI | ✅ merged (PR #19) |
| 11A | Realtime (DDR-115) | ✅ merged (PR #20) |
| 11B | In-app notifications, purge jobs | ✅ merged (PR #21) |
| 12A | P2 landing, backlog, pseudonymous key (DDR-116) | ✅ merged (PR #22) |
| 12B | dbt models, P2 run, tests, freshness, schedule | ✅ merged (PR #23) |
| 13 | Marts and management analytics (DDR-117) | ✅ merged (PR #24) |
| tooling | Handover refresh: this guide, `CLAUDE.md`, `.claude/` | 🟡 on `tooling-handover-refresh` |
| 14 – 22 | See §6 | ⬜ not started |

**Milestones** (plan §4.1):
- M1 Foundation (0–4): done.
- M2 Core order flow (5–9): done.
- **M3 Ops & data (10–14): 10–13 merged; only Task 14 remains.**
- M4 AI (15–17), M5 ML & polish (18–22): not started.

**First thing to do:** if `tooling-handover-refresh` is not merged yet, wait for the owner. Then sync `main`, check CI, and plan Task 14 with `/start-task 14` (P3 synthetic data) with a decision sheet (plan "### Task 14", DDR-56, DDR-74; the reports Simulated tab and `analytics_synthetic` grants are waiting for it).

---

## 3. Documents to read, in this order

### 3.1 Binding rules (read every session)
1. **`.kiro/steering/rules.md`**: the build rules (v1.1, tool-neutral). `CLAUDE.md` imports it every session. "Kiro" in it means you.
2. **This file.**

### 3.1a Read cheaply (saves tokens)
- **Grep, don't read whole files.** The plan (50 KB) and the register (52 KB) are large. Use `grep -n "### Task 9" docs/DELIVERIQ_EXECUTION_PLAN.md`, `grep -n "DDR-111" docs/DESIGN_DECISION_REGISTER.md` and `grep -n "KI-2[0-4]" docs/PORTAL_REQUIREMENTS_MATRIX.md`, then read only those line ranges.
- **Read in full only:** `rules.md`, this file, the task's plan section, plan §5.2 and §6, and the README cards of modules you touch.
- **Read only when the task needs them:** `RAG_AI_DESIGN.md` (Tasks 15–17), `DATA_PIPELINE_DESIGN.md` (12–14, or any new event), `DOCKER_DEPLOYMENT_DESIGN.md` (infra), `KITCHEN_SOURCE_VALIDATION.md` (recipes), `adr/*` (platform choices), source files in `data/source/` (to settle an undefined value).
- **Use sub-agents** for broad codebase investigation, so the main context stays small.
- **Don't re-investigate:** §5 holds the brief for the next task; write the following task's brief into §5 when you close a task.

### 3.2 Precedence when documents disagree (rules §1)
Owner's instruction in this session → `docs/DESIGN_DECISION_REGISTER.md` (Decided) → the four design docs → `docs/DELIVERIQ_EXECUTION_PLAN.md` → `docs/PORTAL_REQUIREMENTS_MATRIX.md` → source files. **If two documents conflict, stop, show both and ask.** Never pick silently.

### 3.3 The docs in `docs/` and when to use each

| File | What it is | Read when |
|---|---|---|
| `DELIVERIQ_EXECUTION_PLAN.md` | **The task list.** §5 decision classes (B/A/P/G) and §5.1 matrix; §5.2 TEST fixtures + the **8 leak controls**; §6 cross-cutting acceptance criteria for every UI task; §7 every task with Depends on / Gated features / Acceptance criteria / Status line; §8 dependency map | Start of every task |
| `DESIGN_DECISION_REGISTER.md` | Every decision, DDR-01 → **DDR-117**. Part A Decided (owner tables 2026-11-11 and 2026-11-12; per-task rows DDR-101–117), Part B former proposals (all decided), **Part C open items** (DDR-06, 15, 41, 42, 43, 44, 45, 46), out-of-scope list | Before any design choice; add a new DDR row per task's decisions |
| `PORTAL_REQUIREMENTS_MATRIX.md` | Requirement IDs per portal: CU-*, KI-*, DL-*, MG-*, SH-*, PL-*; role-permission tables (§3.1 Kitchen, §5 Management); **§7 canonical status machines + display labels per portal**; §10 AI guardrails | Writing any feature or label |
| `CODE_STRUCTURE_DESIGN.md` | Repo layout, module template (api/schemas/service/domain/repository), dependency rules, frontend feature layout, testing layers, **§13 review checklist** | Writing code; end-of-task review |
| `DOCKER_DEPLOYMENT_DESIGN.md` | Compose profiles (`core`, `worker`, `e2e`, `osrm`, `agent`), RAM budget, which profiles may run together, §17 approved deviations | Touching infra or starting profiles |
| `DATA_PIPELINE_DESIGN.md` | Pipelines P1/P2/P3 and K1–K3, run framework, **§6.3 the only approved event types**, dbt layers | Tasks 12–14, any event emission |
| `RAG_AI_DESIGN.md` | Model gateway, harnesses, RAG schemas, embedding benchmark, **§13 system prompts**, Builder Agent sandbox | Tasks 15–17 |
| `KITCHEN_SOURCE_VALIDATION.md` | Validation of the Kitchen SOP source (why SOP dishes are not publishable) | Recipe or SOP work |
| `SOURCE_DOCUMENT_INVENTORY.md` | The 21 source files, their numbers (#1–#21) and SHA-256 hashes | Citing a source; the hash check |
| `adr/` (25 ADRs) | Architecture decisions: monolith, Postgres-only, outbox, status machines, RBAC, model gateway, import-linter, OpenAPI client, sync DB access, Tailwind/shadcn, themes | When a platform choice comes up |
| `runbooks/` | Empty so far (Task 22 fills it) | — |

### 3.4 Source documents (the business requirements)
- `data/source/**`: read-only, hash-checked copies of the 21 source documents. Provenance is in `data/SOURCE_PROVENANCE.md`.
- Key ones:
  - `kitchen/Kitchen_Portal_Requirements.md` (#4)
  - `deliver/Delivery_Agent_Portal_Requirements.md` (#7)
  - `shareddsah/Management_Dashboard_Requirements.md` (#10)
  - `customer/Customer_Dashboard_Requirements.md` (#1)
  - `data/*Seed*` (#14, #15 test values)
  - `phases/*` (#16–#21)
- **Never edit them.** `make verify-sources` must report 21/21.
- **Never touch `/home/k/Downloads/task1/`** (the originals).

### 3.5 Per-module "README cards" (current behaviour, kept up to date)
- `backend/app/modules/*/README.md`: identity, menu, recipes, pipelines, customers, pricing, orders, payments, kitchen_ops, inventory, delivery, management, realtime, notifications, reports, health.
- `backend/app/pipelines/README.md` (framework) and `backend/app/pipelines/p2_elt/README.md`; `analytics/dbt/README.md` (models, tests, grants, the `dataset` var).
- `frontend/src/features/*/README.md`: auth, ordering, recipes, approvals, data-pipelines, kitchen, delivery, management, notifications, reports.
- These are the fastest way to learn what a module already does.

---

## 4. How to work (owner's expectations)

### Tooling (Claude Code)
- `CLAUDE.md` imports the rules and this file.
- Slash commands in `.claude/commands/`:
  - `/start-task <n>`: inspect, then present the plan and decision sheet; stops for approval.
  - `/verify`: every gate in order, with evidence.
  - `/report`: the owner's report format, plus the update to this file.
  - `/ship`: after "approve", push and print the PR link and text; after "merged", sync and check CI.
- `.claude/settings.json`: the guard hook (`.claude/hooks/guard-git.sh`) blocks unsafe git commands and commits of secret-looking files; `deny` rules stop reads of `.env` and edits of `task1/`, `data/source/` and the generated client.
- `CLAUDE.md` and the commands are tool-neutral copies of the Kiro workflow; when the workflow changes, update both this file and the matching command.
- `make reset-fixtures`: kitchen NORMAL, the three DDR-42 test defaults with their labels, TEST Dishes A–C PUBLISHED, TEST stock 10,000 g with no threshold (reserved stock is left alone and reported). Idempotent; ledger entries carry the reason "TEST fixture reset".

### Working loop (rules §2)
1. Inspect the task (plan §7), the DDRs and the code it touches.
2. Present a **plan + a decision sheet** in the §9 template: every value or behaviour the sources leave undefined, each with options and a ✔ recommendation. **Never invent** prices, thresholds, rules or formulas. Undefined values go on the sheet.
3. Wait for the owner. Typical replies are "go + approve all" or "will do as u recommend".
4. Record the approved sheet as a new **DDR row** (the next number after the last row; the last is **DDR-117**) in the register's Part A list. Update the Matrix or plan where a decision changes them, and show the change list first.
5. Build one task at a time on branch `task-NN-short-name`. Large tasks split into **A (backend)** and **B (UI)**.
6. Verify (below), self-review against `CODE_STRUCTURE_DESIGN.md` §13 plus security, scope and leak controls, and grade findings Blocker/High/Medium/Low. Blocker and High must be fixed; Medium and Low are fixed or logged.
7. Commit (stage **files by name**, never `git add .`; check no `.env` is staged) and report.
8. After the owner says "approve": push, then give the PR compare link plus a title and description. **`gh` is NOT installed**, so use the link `https://github.com/ki957/deliveriq/compare/main...<branch>?expand=1`. The owner squash-merges. **Never merge, never push to main, never force-push.**
9. After "merged": `git checkout main && git pull --ff-only`, check CI, delete the local branch with `git branch -d` (the hook blocks `-D`; a squash-merged branch may need the owner's OK to force-delete).
10. Tooling or handover-only changes (this file, `CLAUDE.md`, `.claude/`) go on the open task branch as their own commit, or on a `tooling-<name>` branch from `main` when no task branch is open. Run `git fetch` first: a branch whose PR is already merged no longer reaches `main`.

### Report format (rules §10), kept short
What changed (files) · evidence per acceptance criterion (test names or command output) · review findings with grades · not verified and why · memory (`docker stats`, `free -h`) · open items · next task.

### Owner style
- Short replies.
- Approves recommendations quickly.
- Prefers squash merges.
- Is cost-sensitive: be efficient and don't repeat work.

---

## 5. Next task: 14 (Labelled synthetic data generator, P3)

**Not planned yet.** Run `/start-task 14`: plan + decision sheet, then the next DDR row after DDR-117. Read plan "### Task 14", DDR-50, DDR-56, DDR-74, DDR-78, DDR-117 (4), DATA_PIPELINE (P3 and dbt sections; grep `P3`), `backend/app/pipelines/README.md`, `backend/app/pipelines/p2_elt/README.md` and `analytics/dbt/README.md`.

**Plan acceptance criteria (summary):** P3 runs on the pipeline framework in the Data group; writes `synthetic.events`; the same dbt models build `analytics_synthetic`; demo seed 7 days × 10 orders/day and ML set 90 days × 30 orders/day, generated offline once (DDR-56); a few full synthetic GPS tracks (DDR-78); fixed seed is deterministic; every row flagged synthetic; real marts unaffected; "Simulated data" label wherever it appears; RM sees P3 runs read-only; `TEST –` or explicitly synthetic menu items only, never SOP dishes.

**Already in place (don't rebuild):**
- Pipeline row `p3_synthetic` (DATA group, role `p3_synth`) from migration 0005. `p3_synth` has USAGE on `app`, `synthetic`, `analytics_synthetic`, `ops`; CREATE on `analytics_synthetic`; SELECT on `app.menu_items`; SELECT, INSERT on `synthetic.events`. `migrations/tests/test_grants.py` asserts what it must not read.
- dbt macro `analytics/dbt/macros/generate_schema_name.sql`: with `--vars '{dataset: analytics_synthetic}'` the `analytics` models build into `analytics_synthetic`.
- `ops.dataset_freshness` (migration 0015) already allows the dataset `analytics_synthetic`.
- Migration 0016 gives `app_api` USAGE on `analytics_synthetic`; table SELECT comes from dbt `grants`, so it exists only after a P3 dbt run.
- Reports (`modules/reports`, `features/reports`) have a Simulated tab that says "Not built yet (Task 14)".

**Open questions for the sheet (sources leave them undefined):**
- DATA_PIPELINE §2.4 and line ~243 say the same models switch source (`raw` → `synthetic`) by a dbt variable; `analytics/dbt/models/sources.yml` has only the real source today. Not defined: where synthetic staging and core rows land. `staging` is shared today, and real and synthetic must never share a table (DDR-74); `p3_synth` cannot create in `staging`.
- Generator inputs: seed value, order-time distribution, dish mix, synthetic customers and riders, statuses and cancellations. None are defined; offer labelled test defaults.
- Where the 90-day ML set is stored and how "generated offline once" is triggered (CLI vs pipeline input).
- How many GPS tracks and where they live (GPS stays in `app.delivery_locations` for real data, DDR-78).
- What the reports Simulated tab shows once data exists (same KPIs, labelled "Simulated data").

**Must change when P3 is implemented:** framework tests use `p3_synthetic` as the "pipeline with no implementation" stand-in (`pipelines/framework/tests/test_queue_integration.py`, `test_context_integration.py`, `modules/pipelines/tests/test_pipelines_integration.py` line ~314, `test_fault_inputs.py`). Give them another stand-in.

**Known leftovers:** stale TEST orders from customer E2E (D16, Task 21); E2E-created staff use `TEST – E2E Agent …` names and are removed by the spec.

---

## 6. Remaining tasks after 13 (full criteria in plan §7)

| Task | Summary | Key gates / notes |
|---|---|---|
| 14 Synthetic P3 | `synthetic` schema, 7d×10 demo, 90d×30 ML (DDR-56) | DDR-74 separation |
| 15 / 15A / 15B / 15C | AI gateway + Management Copilot; Operational Actions (CA, confirmed, audited); Builder Agent sandbox + harness (PRs only, never merges) | Groq key in `.env` (§5.3 of plan); DDR-46 content approval; DDR-68–71, 85–87 |
| 16 Kitchen RAG | Kitchen Copilot (read-only) | DDR-45 embedding benchmark (B for vector dims) |
| 17 Customer Assistant | Only after all portals complete | DDR-46 |
| 18 / 19 | Demand forecast; ETA + assignment optimisation (advisory) | — |
| 20 / 21 / 22 | Monitoring & reconciliation; E2E hardening; demo handover + runbooks + known limitations | — |

**Still-open decisions** (register Part C): DDR-06 food-card Add (B, Task 6), DDR-15 background GPS (B), DDR-41 lost-mobile recovery (B), DDR-42 final kitchen defaults (A, test defaults in use), DDR-43 GPS interval (A), DDR-44 refund thresholds/KPIs/audit/YAML (B/A), DDR-45 embedding winner (B), DDR-46 knowledge approval (A). Follow plan §5: don't build B items, keep A items behind a disabled flag or labelled test default, and label P items.

---

## 7. Technical cheat-sheet

### Stack
- **Backend:** FastAPI modular monolith; **sync** SQLAlchemy 2 + psycopg 3 (async only for WS/Redis/HTTP); PostgreSQL + PostGIS (+ pgvector later); Redis; Python with `uv`.
- **Frontend:** React + TypeScript strict + Vite + Tailwind + TanStack Query + react-router; **API client generated from OpenAPI, never hand-written**.
- **Realtime:** WebSocket `/api/v1/realtime` sends hints `{topic, kind, id}` (Postgres triggers → listener → Redis → hub); pages refetch REST and poll only while the socket is down (DDR-115).
- **Data:** dbt-core 1.12.7 + dbt-postgres 1.11.0 (worker dependency group only), run by P2 as `p2_elt` (DDR-116); reports read marts and dims only (DDR-117).
- **Tests:** Vitest; Playwright (Chromium, pinned container).

### Repo map
- `backend/app/{core,shared,modules,pipelines,worker,cli}`
- `backend/migrations/versions/0001–0016` (**head = 0016**; `migrations/tests/test_schema_and_seeds.py` asserts the head; bump it with each migration)
- `analytics/dbt/` (P2 models: staging, core, marts; tests; `generate_schema_name` macro)
- `frontend/src/{app,portals,features,shared}`
- `tests/e2e/{specs,__screenshots__}`
- `infra/compose.yaml`, `Makefile`, `.github/workflows/ci.yml` (jobs: source-integrity, backend, frontend, e2e)

### Make targets (from repo root)

| Command | Use |
|---|---|
| `make up` / `make down` | start / stop `core` (Postgres, Redis, API; runs migrations and `db-roles`) |
| `make worker` / `make worker-down` | pipeline worker (needed by the pipelines integration tests); `make worker` rebuilds the image, which carries dbt |
| `make fixtures` | seed users, TEST menu, TEST50 coupon, seed address, **TEST opening stock** (idempotent) |
| `make reset-fixtures` | back to the shared TEST baseline (run before and after test runs) |
| `make check` | ruff, format, mypy strict, import-linter (5 contracts), unit tests, verify-sources (21/21), openapi-check |
| `make frontend-check` | typecheck, lint, Vitest, api:check, build |
| `timeout 1200 make test-integration` | integration tests against the running stack (worker must be up); ~249 tests since Task 13 |
| `make pipeline NAME=p2_elt` | run a pipeline as the UI would (P2 lands events, runs dbt, applies the dbt `grants`) |
| `make e2e` / `make e2e-update` | Playwright in the container (runs `e2e-setup` first); `-update` rewrites baselines (review every image) |
| `make openapi` then `cd frontend && npm run api:generate` | after any API change. **Never run prettier on the generated client** |

### Gotchas learned the hard way
- **The `migrate` container runs a baked image.** After editing a migration, run `docker compose --project-directory . -f infra/compose.yaml --profile core build migrate` (or `make up`, which builds) before upgrading. The API bind-mounts `backend/app` with `--reload`; migrations are not mounted.
- Running one Playwright spec: `PLAYWRIGHT_ARGS="<spec> --update-snapshots"`, and the spec name goes **first**.
- E2E screenshots must avoid data that grows between runs; the recipe workflow publishes a new `TEST – E2E <n>` dish each run. Hide the fixed bottom nav for element screenshots (see `customer-checkout.spec.ts` `screenshot()` helper).
- E2E customers: register a fresh `+91-00000-NNNNN` number per test (`helpers.ts` `registerCustomer` / `newTestMobile`); seed users are `+91-00000-00001`…`06` (customer, agent, KS, KM, RM, CA), OTP `123456` (local/test only).
- Outbox `emit()` has a default idempotency key `"{type}:{aggregate_id}"`, so a second event of the same type for one order needs an explicit key.
- `is_test_fixture` is never writable by `app_api`; new tables holding TEST-derived rows need a derived flag (trigger) plus an entry in `backend/app/shared/fixture_guard.py`.
- New tables need explicit `app_api` grants in the migration.
- New pure `domain.py` modules must be added to the import-linter contract in `pyproject.toml`.
- CI failures: `curl https://api.github.com/repos/ki957/deliveriq/commits/<sha>/check-runs` and `/check-runs/<id>/annotations` (the e2e job posts Playwright failures as annotations).
- Avoid broad `sed` across files; edit precisely. Exact-match edits fail after a formatter rewraps lines: re-read the file first.
- **dbt lives in the worker image.** After changing `pyproject.toml`/`uv.lock` for dbt or the worker, run `make worker` (it rebuilds). `analytics/dbt` is mounted read-only at `/srv/analytics/dbt`.
- **dbt `grants` apply only when dbt builds the model.** After a fresh database or a model change, run P2 (`make pipeline NAME=p2_elt`) before the reports integration tests, or `app_api` gets "permission denied" on the marts.
- **Run Prettier on frontend READMEs too** (`cd frontend && npx prettier --check "src/**/*.md"`); the frontend CI job failed once on a README table.
- E2E helpers retry a superseded OTP sign-in and a taken TEST number (`helpers.ts`); keep that when adding sign-in flows.
- Only `delivery.spec` puts an agent online; two online agents take each other's offers.
- The integration world picks a free `REG-TST-*` code. Leftover `KIT-TST-*` rows from a killed run can shift the CA screenshot; clear them before updating baselines.
- Framework tests use `p3_synthetic` as the unimplemented pipeline (see §5); Task 14 must give them another stand-in.
- `PSEUDONYM_KEY` in `.env` (HMAC for `customer_key`, DDR-116; at least 32 characters) is required by every backend container, so Compose refuses to start without it. Name it, never print it.

### Git
- Remote: `git@github-kiro:ki957/deliveriq.git` (SSH host alias).
- Branch per task; never push to main.
- No force push, `reset --hard`, `clean -f` or `--no-verify`.
- Never change git config.

### Resources (16 GB laptop, rules §6)
- Run `free -h` before heavy jobs (e2e, dbt, embeddings). Stop if under 2 GB available.
- Never run heavy jobs together.
- Stop the stack after work (`make worker-down; make down`).
- Typical memory (Task 13): API ~120 MiB, Postgres ~100–145 MiB, worker ~45–70 MiB (183 MiB peak during dbt), Redis ~5–14 MiB.
- Record `docker stats --no-stream` and `free -h` in each report.

### Security non-negotiables (rules §5)
- Secrets only in `.env` (git-ignored); refer to them by key name, never print values.
- Deny by default; the backend is the security boundary; another kitchen's or region's resource reads as **404**, the wrong role in your own scope as **403**.
- Never weaken auth, RBAC, region scope, audit, DB roles or AI guardrails without an approved DDR.
- All 8 leak controls (plan §5.2) must hold. No SOP recipe is ever activated. Real and synthetic data never share a table (DDR-74).
- Parameterised SQL only.

---

## 8. Definition of done for any task (checklist)
- [ ] Plan + decision sheet approved; DDR row added; affected docs updated with the change list shown first
- [ ] `make check` ✔ · `make frontend-check` ✔ · `timeout 1200 make test-integration` ✔ (stack + worker up) · `make e2e` ✔ (twice for new specs)
- [ ] Every acceptance criterion proven by a named test or by command output
- [ ] New baselines reviewed image by image
- [ ] Undefined-DDR check (every `DDR-nn` used in docs/code exists in the register) and `make verify-sources` 21/21 after doc edits
- [ ] README cards and plan status line updated
- [ ] Self-review graded; no open Blocker or High
- [ ] `make reset-fixtures` run after tests; shared TEST state at the baseline
- [ ] Committed by file name; stack stopped; report sent; push only after "approve"

---

## 9. Decision sheet template (keep this exact shape)

The owner answers "go + approve all", "do as u recommend", or changes by D-number. Keep each item to 2–4 lines.

```
**D1. <short question> (source: #4 §3 / KI-13; gap: <what the sources leave undefined>).**
- A ✔: <recommended option, concrete values, labelled test default if a value is needed>.
- B: <alternative>, <its trade-off>.
- C: <alternative, if any>.

**D2. …**
```

Rules:
- One sheet per task, at the plan step.
- Mark exactly one ✔ per item.
- Name the class when it applies (B = don't build, A = build behind a disabled flag or labelled test default, P = label, G = gate; plan §5).
- After approval, add one register row `DDR-<next>` (the next number after the last row; the last is **DDR-117**) with numbered points (1), (2)…, matching D-numbers, in `docs/DESIGN_DECISION_REGISTER.md` after the last DDR row in Part A. Cite it in code comments as `DDR-nnn (3)`.

---

## 10. Changelog (one line per closed task; newest last)

| Date | Task / PR | Decisions | Note for the next builder |
|---|---|---|---|
| 2026-11-12 | 0–4B / #1–#6 | DDR-01–100 | Source hashes, Compose, migrations 0001–0006, identity, shells, generated client |
| 2026-11-12 | 5A–5C / #7–#9 | DDR-101–108 | Worker + P1 SOP import; TEST fixtures; E2E needs `e2e-setup` (P1 import + fresh E2E recipe) |
| 2026-11-12 | 7 / #10 | DDR-109 | Order DB function derives the fixture flag; idempotent checkout; refunds |
| 2026-11-12 | 6A–6B / #11–#12 | DDR-110 | Cart, pricing, checkout; per-test E2E customers; tablet project; bottom-bar clearance fix |
| 2026-11-12 | 8A / #13 | DDR-111 | Migration 0010; kitchen accept/reject/prep, stock, availability; migrate image must be rebuilt after migration edits |
| 2026-11-12 | tooling / #14 | rules v1.1 | `CLAUDE.md`, `.claude/` commands + guard hook, `make reset-fixtures`, this guide |
| 2026-11-12 | 8B / #15 | DDR-112 | Kitchen screens + Management Dish Availability; `kds` 1920×1080 project (`@kitchen` on tablet + kds only); `e2e-setup` runs `reset-shared`; mask live counts in screenshots |
| 2026-11-12 | 9A / #16 | DDR-113 | Migration 0011; delivery lifecycle, code, GPS, retention; worker uses 2 SECURITY DEFINER functions only |
| 2026-11-12 | 9B / #17 | DDR-113 (19)–(20) | Delivery PWA; Leaflet pinned (lazy chunk); E2E agent fixture `load-e2e-agent`; full flow on phone-390, screens `@devices`. M2 complete |
| 2026-11-12 | 10A / #18 | DDR-114 (1) updated | Management API (`/api/v1/management`); no migration; new code-only permission `management.inventory.view`; staff changes revoke sessions and devices at once |
| 2026-11-12 | 10B / #19 | DDR-114 | Management UI (`features/management`); placeholders say why; `KitchenSettingsPanel` reused by `kitchen_id`; `PollNote` moved to `shared/ui`; 4xx never retried (`shouldRetry`); E2E `load-e2e-region` (REG-ETE-001 + RM `+91-00000-00008`); integration world picks a free REG-TST code |
| 2026-11-12 | 11A / #20 | DDR-115 | Migration 0012 (`app.rt_notify` triggers); `modules/realtime` (listener → Redis → hub); `/api/v1/realtime` hints `{topic, kind, id}`; `shared/realtime` + `useLiveRefresh`; pages poll only while the socket is down; only `delivery.spec` puts an agent online in E2E (two online agents take each other's offers) |
| 2026-11-12 | 11B / #21 | DDR-115 (10)–(12) | Migration 0013 (`app.notifications` by triggers; `purge_notifications`, `purge_auth` for the worker); `/api/v1/me/notifications`; bell + page (customer, KM, agent); `reset-shared` closes pending TEST dish requests; E2E helpers retry superseded OTP sign-ins and taken TEST numbers; mutations refetch in the background and hints refetch once per 250 ms burst |
| 2026-11-12 | 12A / #22 | DDR-116 (5), (6), (10), (12) | Migration 0014 (`ops.outbox_backlog()`, backlog notice); worker thread `p2-landing` as `p2_elt`; `customer_key` (HMAC, `PSEUDONYM_KEY`) on `order.placed`; `GET /api/v1/pipelines/p2/backlog` CA only; overview panel. First start lands every older event (3,472 locally) |
| 2026-11-12 | 12B / #23 | DDR-116 | dbt 1.12.7 + dbt-postgres 1.11.0 (worker group); `analytics/dbt` (staging, 11 core, 6 marts, 45 tests); P2 stages land → dbt → tests → publish freshness; migration 0015 (reference grants by column, `ops.dataset_freshness`, `ops.pipeline_schedules`, `ops.queue_due_schedules()`); `order.placed` carries `items`; P2 page; real marts empty (all TEST); framework tests now use `p3_synthetic` as the unimplemented pipeline |
| 2026-11-12 | 13 / #24 | DDR-117 | `modules/reports` + `features/reports` (13 ETL §9 KPIs labelled pending DDR-44; Real/Simulated tabs; audited CSV); `management.reports.view`; migration 0016 (schema usage, `ops.operational_totals()`); dbt `grants` to app_api on marts and dims; P2 reconciles operational totals (6 critical checks); payment/delivery marts gain `kitchen_id` |
| 2026-11-12 | tooling / branch `tooling-handover-refresh` | — | Handover refresh: this guide (status, Task 14 brief, gotchas, memory), `CLAUDE.md`, `.claude/` commands |

**Update this file** when a task closes: §2 status table, §5 next-task brief, and a §10 changelog line. The next session starts here.
