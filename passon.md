# passon.md: DeliverIQ handover guide for Codex

**Written:** 2026-11-12 by Kiro; **last updated:** 2026-11-16 after Task 19A fallback-range verification. **For:** OpenAI Codex (CLI or IDE extension), continuing the build.
**Read this file first.** It tells you where the project stands, what to read, how to work, and what to build next. `AGENTS.md` points Codex to it and to `.kiro/steering/rules.md` (the binding rules) at every start.

> ## ⛔ Do not (each of these has broken something, or would)
> 1. **Never edit** `/home/k/Downloads/task1/` or `data/source/**`. `make verify-sources` must stay 21/21.
> 2. **Never print or commit `.env` values**; name secrets by key only. The guard hook blocks `.env` reads and staged secret-looking files.
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

All work through Task 21 is merged on `main` at `852a36a` (PR #41; Task 21 UI/E2E is PR #40). Merged task PRs: 0–4B #1–#6; 5A–5C #7–#9; 7 #10; 6A–6B #11–#12; 8A #13; tooling #14; 8B #15; 9A/9B #16–#17; 10A/10B #18–#19; 11A/11B #20–#21; 12A/12B #22–#23; 13 #24; 14 #26; 15/15A #27–#28; 16A–16C #29 (CI fix #30); 17A #31; 18 #32; 17B #33; 19A #34 (main CI fix #35); 20 #36; 15B #37; 19B #38; 15C #39; 21 #40/#41. Task 17B's measured 60-case evaluation remains DRAFT pending CA approval. Task 18 is under DDR-124. Task 19A is under DDR-125. Task 20 is under DDR-126. Current migration head is **0032**; Task 20 migration 0031 was not needed, and Task 15C added 0031–0032. Task 22 is being completed on `task-22-handover` under DDR-130. The Customer Assistant UI remains gated by CD-18.

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
| tooling | Claude Code setup (now replaced by the Codex setup), `make reset-fixtures`, this guide | ✅ merged (PR #14) |
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
| 14 | Labelled synthetic P3 data (DDR-118) | ✅ merged (PR #26) |
| 15 | AI gateway and Management Copilot (DDR-119) | ✅ merged (PR #27) |
| 15A | Management Operational Actions (DDR-120) | ✅ merged (PR #28) |
| 15B | Builder Agent sandbox (DDR-70) | ✅ merged (PR #37) |
| 15C | Builder Agent harness (DDR-71, DDR-80, Task 21 dependency) | ✅ merged (PR #39) |
| 16A / 16B / 16C | Kitchen RAG, embedding winner, hybrid retrieval, KM approval and golden-set gate | ✅ merged on `main` (`778a863`); CI fix merged in PR #30 (`9dc6871`) |
| 17A | Customer RAG/K1, Customer Assistant guard/tools, CA approval UI and golden-set draft | ✅ merged in PR #31 at `7c8e807`; all four CI jobs passed |
| 17B | Customer Assistant acceptance verification and persisted golden-set evaluation | ✅ merged in PR #33 at `e0e2bb7`; all four CI jobs passed; evaluation remains DRAFT pending CA approval |
| 18 | Demand Forecasting (DDR-124) | ✅ merged in PR #32 at `b317bee`; all four CI jobs passed |
| tooling | Handover refresh and switch to Codex: this guide, `AGENTS.md`, `.agents/skills/`, `.codex/` | ✅ merged |
| 17–22 | See plan | 17A–17B #31/#33, 18 #32, 19A #34 + CI fix #35, 20 #36, 15B #37, 19B #38, 15C #39, and 21 #40/#41 are merged; Task 22 is locally verified on `task-22-handover`, PR pending |

**Milestones** (plan §4.1):
- M1 Foundation (0–4): done.
- M2 Core order flow (5–9): done.
- M3 Ops & data (10–14): done; Task 14 is merged.
- M4 AI (15–17): Tasks 15, 15A, 16, 17A and 17B are merged.
- M5 ML & polish (18–22): Tasks 18, 19, and 20 are merged; Tasks 21 and its dependencies are merged in PRs #37–#41. Task 22 is locally verified on `task-22-handover`, PR pending.

**Current:** Task 21 is merged in PRs #40/#41 at `852a36a`. Its backend gates passed: `make check` (421 unit tests), integration (278 passed), `make agent-check` (421 unit + 10 proxy tests), backup/restore at head 0032 (9 regions, 9 kitchens, 57 menu items, 68 pipeline runs, 808 raw events), reduced retrieval without the worker, and P2 (45 dbt tests, 6 reconciliation checks). Resource sample: idle API 101.1 MiB, Postgres 32.56 MiB, Redis 4.754 MiB, worker 43.35 MiB; during P2 API 142.5 MiB, Postgres 42.79 MiB, Redis 4.668 MiB, worker 87.5 MiB; host 15 GiB total, 7.6 GiB idle / 7.5 GiB during P2 available. E2E/UI merged in #40; manual keyboard/screen-reader pass remains owner-pending. Task 22 is implemented and locally verified on `task-22-handover`; review its report and open the PR from the compare link. After it merges and CI is green, update this handover and continue with any owner-open items. Current migration head: 0032. Open items are all of register Part C plus the owner-pending knowledge/golden approvals, CD-18 Customer Assistant UI gate, and Task 21 manual accessibility pass.

---

## 3. Documents to read, in this order

### 3.1 Binding rules (read every session)
1. **`.kiro/steering/rules.md`**: the build rules (v1.2, tool-neutral). `AGENTS.md` sends you to it every session. "Kiro" in it means you.
2. **This file.**

### 3.1a Read cheaply (saves tokens)
- **Grep, don't read whole files.** The plan (50 KB) and the register (52 KB) are large. Use `grep -n "### Task 9" docs/DELIVERIQ_EXECUTION_PLAN.md`, `grep -n "DDR-111" docs/DESIGN_DECISION_REGISTER.md` and `grep -n "KI-2[0-4]" docs/PORTAL_REQUIREMENTS_MATRIX.md`, then read only those line ranges.
- **Read in full only:** `rules.md`, this file, the task's plan section, plan §5.2 and §6, and the README cards of modules you touch.
- **Read only when the task needs them:** `RAG_AI_DESIGN.md` (Tasks 15–17), `DATA_PIPELINE_DESIGN.md` (12–14, or any new event), `DOCKER_DEPLOYMENT_DESIGN.md` (infra), `KITCHEN_SOURCE_VALIDATION.md` (recipes), `adr/*` (platform choices), source files in `data/source/` (to settle an undefined value).
- **Keep context small:** for broad investigation, grep and read narrow line ranges; don't load whole directories.
- **Don't re-investigate:** §5 holds the brief for the next task; write the following task's brief into §5 when you close a task.

### 3.2 Precedence when documents disagree (rules §1)
Owner's instruction in this session → `docs/DESIGN_DECISION_REGISTER.md` (Decided) → the four design docs → `docs/DELIVERIQ_EXECUTION_PLAN.md` → `docs/PORTAL_REQUIREMENTS_MATRIX.md` → source files. **If two documents conflict, stop, show both and ask.** Never pick silently.

### 3.3 The docs in `docs/` and when to use each

| File | What it is | Read when |
|---|---|---|
| `DELIVERIQ_EXECUTION_PLAN.md` | **The task list.** §5 decision classes (B/A/P/G) and §5.1 matrix; §5.2 TEST fixtures + the **8 leak controls**; §6 cross-cutting acceptance criteria for every UI task; §7 every task with Depends on / Gated features / Acceptance criteria / Status line; §8 dependency map | Start of every task |
| `DESIGN_DECISION_REGISTER.md` | Every decision, DDR-01 → **DDR-130**. Part A Decided (owner tables and per-task rows through DDR-130), Part B former proposals (all decided), **Part C open items** (DDR-06, 15, 41, 42, 43, 44), out-of-scope list | Before any design choice; add a new DDR row per task's decisions |
| `PORTAL_REQUIREMENTS_MATRIX.md` | Requirement IDs per portal: CU-*, KI-*, DL-*, MG-*, SH-*, PL-*; role-permission tables (§3.1 Kitchen, §5 Management); **§7 canonical status machines + display labels per portal**; §10 AI guardrails | Writing any feature or label |
| `CODE_STRUCTURE_DESIGN.md` | Repo layout, module template (api/schemas/service/domain/repository), dependency rules, frontend feature layout, testing layers, **§13 review checklist** | Writing code; end-of-task review |
| `DOCKER_DEPLOYMENT_DESIGN.md` | Compose profiles (`core`, `worker`, `e2e`, `osrm`, `agent`), RAM budget, which profiles may run together, §17 approved deviations | Touching infra or starting profiles |
| `DATA_PIPELINE_DESIGN.md` | Pipelines P1/P2/P3 and K1–K3, run framework, **§6.3 the only approved event types**, dbt layers | Tasks 12–14, any event emission |
| `RAG_AI_DESIGN.md` | Model gateway, harnesses, RAG schemas, embedding benchmark, **§13 system prompts**, Builder Agent sandbox | Tasks 15–17 |
| `KITCHEN_SOURCE_VALIDATION.md` | Validation of the Kitchen SOP source (why SOP dishes are not publishable) | Recipe or SOP work |
| `SOURCE_DOCUMENT_INVENTORY.md` | The 21 source files, their numbers (#1–#21) and SHA-256 hashes | Citing a source; the hash check |
| `adr/` (25 ADRs) | Architecture decisions: monolith, Postgres-only, outbox, status machines, RBAC, model gateway, import-linter, OpenAPI client, sync DB access, Tailwind/shadcn, themes | When a platform choice comes up |
| `docs/runbooks/` | Fresh-machine demo, daily operations, and known limitations (Task 22) | Task 22 |

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
- `backend/app/modules/*/README.md`: identity, menu, recipes, pipelines, knowledge, customers, pricing, orders, payments, kitchen_ops, inventory, delivery (Task 19 held-out-calibrated ETA fallback range and read-only assignment suggestions), management, realtime, notifications, reports, health.
- AI harness cards: `backend/app/modules/ai/kitchen_copilot/README.md` (read-only Kitchen Copilot, hybrid retrieval with reduced-retrieval fallback, KM-approved knowledge only) and `backend/app/modules/ai/customer_assistant/README.md` (Customer-only, read-only Assistant with Prompt Guard).
- `backend/app/pipelines/README.md` (framework, K1 Customer and K2 Kitchen staging; documents remain DRAFT pending CA/KM approval), `backend/app/pipelines/p2_elt/README.md`; `analytics/dbt/README.md` (models, tests, grants, the `dataset` var); Reports cards describe the Task 18 seasonal demand forecast.
- `frontend/src/features/*/README.md`: auth, ordering (post-pickup ETA range), recipes, approvals, data-pipelines, kitchen (including Kitchen Copilot), customer-assistant (gated approval card), delivery, management (advisory assignment suggestions), notifications, reports.
- `docs/runbooks/`: Task 22 fresh-machine demo, daily operations, and known limitations.
- These are the fastest way to learn what a module already does.

---

## 4. How to work (owner's expectations)

### Tooling (Codex)
- `AGENTS.md` (repo root) is read by Codex at every start. Codex has no file imports, so it tells you to read `.kiro/steering/rules.md` and this file in full first.
- Skills in `.agents/skills/<name>/SKILL.md` (run with `$name`, or `/skills`; Codex may also pick one by its description):
  - `$start-task` + the task number: inspect, then present the plan and decision sheet; stops for approval.
  - `$verify`: every gate in order, with evidence.
  - `$report`: the owner's report format, plus the update to this file.
  - `$ship`: after "approve", push and print the PR link and text; after "merged", sync and check CI.
- `.codex/hooks.json` runs `.codex/hooks/guard-git.sh` before every Bash and `apply_patch` call. It blocks unsafe git commands, commits of secret-looking files, commands that read `.env`, and patches to `/home/k/Downloads/task1/`, `data/source/`, the generated client and `.env`. **Project hooks run only after the owner trusts them** (`/hooks` in Codex; re-trust after any change to the hook files).
- Codex runs in a sandbox. Docker, `git push` and `curl` need the socket or the network; if a command is refused by the sandbox, ask the owner to approve it rather than working around it.
- For an independent review of a large or security-sensitive diff, use Codex `/review`.
- `AGENTS.md` and the skills are tool-neutral copies of the Kiro workflow; when the workflow changes, update this file and the matching skill.
- `make reset-fixtures`: kitchen NORMAL, the three DDR-42 test defaults with their labels, TEST Dishes A–C PUBLISHED, TEST stock 10,000 g with no threshold (reserved stock is left alone and reported). Idempotent; ledger entries carry the reason "TEST fixture reset".

### Working loop (rules §2)
1. Inspect the task (plan §7), the DDRs and the code it touches.
2. Present a **plan + a decision sheet** in the §9 template: every value or behaviour the sources leave undefined, each with options and a ✔ recommendation. **Never invent** prices, thresholds, rules or formulas. Undefined values go on the sheet.
3. Wait for the owner. Typical replies are "go + approve all" or "will do as u recommend".
4. Record the approved sheet as a new **DDR row** (the next number after the last row; Task 22 records its chosen documentation and test-harness defaults in DDR-130) in the register's Part A list. Update the Matrix or plan where a decision changes them, and show the change list first.
5. Build one task at a time on branch `task-NN-short-name`. Large tasks split into **A (backend)** and **B (UI)**.
6. Verify (below), self-review against `CODE_STRUCTURE_DESIGN.md` §13 plus security, scope and leak controls, and grade findings Blocker/High/Medium/Low. Blocker and High must be fixed; Medium and Low are fixed or logged.
7. Commit (stage **files by name**, never `git add .`; check no `.env` is staged) and report.
8. After the owner says "approve": push, then give the PR compare link plus a title and description. **`gh` is NOT installed**, so use the link `https://github.com/ki957/deliveriq/compare/main...<branch>?expand=1`. The owner squash-merges. **Never merge, never push to main, never force-push.**
9. After "merged": `git checkout main && git pull --ff-only`, check CI, delete the local branch with `git branch -d` (the hook blocks `-D`; a squash-merged branch may need the owner's OK to force-delete).
10. Tooling or handover-only changes (this file, `AGENTS.md`, `.agents/skills/`, `.codex/`) go on the open task branch as their own commit, or on a `tooling-<name>` branch from `main` when no task branch is open. Run `git fetch` first: a branch whose PR is already merged no longer reaches `main`.

### Report format (rules §10), kept short
What changed (files) · evidence per acceptance criterion (test names or command output) · review findings with grades · not verified and why · memory (`docker stats`, `free -h`) · open items · next task.

### Owner style
- Short replies.
- Approves recommendations quickly.
- Prefers squash merges.
- Is cost-sensitive: be efficient and don't repeat work.

---

## 5. Current task: Task 22 handover

Task 22 is implemented on `task-22-handover` from main `852a36a`. It adds three command-first runbooks, a production-profile Make target and integration test, and a final status update. Local gates passed: `make check` (421 unit tests), full integration (279 passed), production profile (one integration test plus fixture-loader refusal), source hashes (21/21), undefined-DDR check, and `git diff --check`. The fresh clone/runbook passed with generated local credentials, unique Compose ports and project name, and Vite proxying to the chosen API port; the public menu API returned HTTP 200 through the frontend. The throwaway project's containers and volume were removed. No frontend files changed, so frontend-check was not required. CI runs after the owner opens the PR from the compare link. Once merged and CI is green, update §2 and §10 with its PR number and merge SHA.

## 6. Task status and remaining work (full criteria in plan §7)

| Task | Summary | Key gates / notes |
|---|---|---|
| 14 Synthetic P3 | Labelled deterministic synthetic data and separate marts | ✅ merged (#26), DDR-74 separation |
| 15 / 15A / 15B / 15C | ✅ merged in PR #27–#28 and #37/#39 | DDR-46 content approval; DDR-68–71, 85–87 |
| 16 | ✅ merged PR #29; CI fix PR #30 | DDR-121, DDR-122; no live knowledge before KM approval |
| 17B Customer Assistant verification | ✅ merged PR #33 at `e0e2bb7`; evaluation stays DRAFT until CA approval | DDR-90, DDR-92, DDR-123 |
| 19 ETA + assignment optimisation | ✅ merged PRs #34, #35, #38 | DDR-19, DDR-55, DDR-56, DDR-74, DDR-78, DDR-113, DDR-118, DDR-124, DDR-125 |
| 20 Monitoring & reconciliation | ✅ merged in PR #36 at `190210a` | DDR-126; no schema gap; migration 0031 was later used by Task 15C |
| 21 | ✅ merged PRs #40/#41 at `852a36a`; manual accessibility pass still owner-pending | DDR-129; Task 21 results and memory are in §2/§7 |
| 22 | Locally verified on `task-22-handover`; PR pending | DDR-48–50, DDR-130; runbooks and production-profile gate |

**Remaining-work order:** Task 22 PR/CI, then merge. No later task is scheduled in the current plan.

**Still-open decisions:** every item in register Part C (DDR-06, DDR-15, DDR-41–44); Task 22 known limitations are listed in `docs/runbooks/known-limitations.md`. Owner-pending: DRAFT knowledge and golden sets await CA/KM approval, CD-18 gates the Customer Assistant UI, and the Task 21 manual keyboard/screen-reader pass remains. DDR-45/46 are resolved by DDR-121/122.

---

## 7. Technical cheat-sheet

Current migration head is **0032**: Task 17B added 0029, Task 19A added 0030, and Task 15C added 0031–0032. Task 20 reused existing scheduling and reconciliation structures; it needed no migration 0031. K1 runs as `rag_customer`; Customer and Kitchen source documents remain DRAFT pending CA/KM approval. Customer retrieval uses `app.retrieve_customer_chunks_hybrid`; live menu/order facts come from read tools, including current `TEMPORARILY_UNAVAILABLE` availability. Prompt Guard is controlled by `AI_PROMPT_GUARD_ENABLED`; the Customer Assistant UI remains gated by CD-18. Task 18 reads `analytics_synthetic` only after its immutable profile is ready; Task 19 ETA training is separate, synthetic-only and generator-evaluated. Task 21 backend/E2E status and measured memory are in §2. Branch protection on `main` is on, and Task 15C's fine-grained token is in place.

### Stack
- Migration head is 0032. Task 17B owns 0028–0029, Task 19A owns 0030, Task 15C owns 0031–0032. Task 22 adds no migration.
- Task 21 resource figures above are the final captured snapshots; Task 22 does not need a new memory snapshot. Its `make production-profile-check` uses an isolated project/volume, production environment, loader refusal assertion, public menu assertion and Kitchen RAG canary integration test.
- **Backend:** FastAPI modular monolith; **sync** SQLAlchemy 2 + psycopg 3 (async only for WS/Redis/HTTP); PostgreSQL + PostGIS + pgvector (Kitchen vector index migration 0027); Redis; Python with `uv`.
- **Frontend:** React + TypeScript strict + Vite + Tailwind + TanStack Query + react-router; **API client generated from OpenAPI, never hand-written**.
- **Realtime:** WebSocket `/api/v1/realtime` sends hints `{topic, kind, id}` (Postgres triggers → listener → Redis → hub); pages refetch REST and poll only while the socket is down (DDR-115).
- **Data:** dbt-core 1.12.7 + dbt-postgres 1.11.0 (worker dependency group only), run by P2 as `p2_elt` (DDR-116); reports read marts and dims only (DDR-117).
- **Tests:** Vitest; Playwright (Chromium, pinned container).

### Repo map
- `backend/app/{core,shared,modules,pipelines,worker,cli}`
- `backend/migrations/versions/0001–0032` (**head = 0032**; 0026–0032 add AI evaluation, Kitchen/Customer RAG, ETA profile, and Builder Agent harness/queue data)
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
| `timeout 1200 make test-integration` | integration tests against the running stack (worker must be up) |
| `make production-profile-check` | isolated production startup, fixture-loader refusal, menu fixture exclusion, Kitchen RAG canary exclusion |
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
- Framework tests use `p3_synthetic` as the unimplemented pipeline stand-in; Task 14 now implements P3, so update this stand-in when convenient.
- `PSEUDONYM_KEY` in `.env` (HMAC for `customer_key`, DDR-116; at least 32 characters) is required by every backend container, so Compose refuses to start without it. Name it, never print it.

### Git
- Remote: `git@github-kiro:ki957/deliveriq.git` (SSH host alias).
- Branch per task; never push to main.
- Branch protection on `main` is on. Task 15C still needs a GitHub fine-grained token scoped to repository contents and pull requests (plan §5.3).
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
- After approval, add one register row `DDR-<next>` (Task 22 recorded defaults in DDR-130; future work takes the next unused number) with numbered points (1), (2)…, matching D-numbers, in `docs/DESIGN_DECISION_REGISTER.md` after the last DDR row in Part A. Cite it in code comments as `DDR-nnn (3)`.

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
| 2026-11-12 | 12B / #23 | DDR-116 | dbt 1.12.7 + dbt-postgres 1.11.0 (worker group); `analytics/dbt` (staging, 11 core, 6 marts, 45 tests); P2 stages land → dbt → tests → publish freshness; migration 0015 (reference grants by column, `ops.dataset_freshness`, `ops.pipeline_schedules`, `ops.queue_due_schedules()`); `order.placed` carries `items`; P2 page; real marts empty (all TEST); framework integration tests used `p3_synthetic` as the not-yet-built pipeline stand-in |
| 2026-11-12 | 13 / #24 | DDR-117 | `modules/reports` + `features/reports` (13 ETL §9 KPIs labelled pending DDR-44; Real/Simulated tabs; audited CSV); `management.reports.view`; migration 0016 (schema usage, `ops.operational_totals()`); dbt `grants` to app_api on marts and dims; P2 reconciles operational totals (6 critical checks); payment/delivery marts gain `kitchen_id` |
| 2026-11-12 | tooling / branch `tooling-handover-refresh` | rules v1.2 | Handover refresh (status, Task 14 brief, gotchas, memory); builder switched from Claude Code to Codex: `CLAUDE.md` → `AGENTS.md`, `.claude/commands` → `.agents/skills`, guard hook → `.codex/hooks.json` (now also guards `apply_patch` and `.env` reads) |
| 2026-11-15 | 16A / 16B / 16C / #29 + CI fix / #30 | DDR-45, DDR-46, DDR-57, DDR-77, DDR-80, DDR-88–90, DDR-121–122 | Merged on main `778a863`; migration 0026 persists benchmark evidence; migration 0027 adds MiniLM 384 vector metadata/HNSW hybrid retrieval, SHA-keyed KM approval and the in-app DDR-90 gate; CI fix adds the pinned worker dependency group to uv defaults; all four CI jobs green on `9dc6871`; owner confirmed MiniLM L6 v2; draft benchmark set remains non-golden |
| 2026-11-15 | 17 Customer Assistant / #31 | DDR-123 | Merged at `7c8e807`; all four CI jobs green. Migration 0028 adds Customer RAG/K1 and CA approval; chat UI remains gated by CD-18 |
| 2026-11-15 | 18 Demand Forecasting / #32 | DDR-124 | Read-only seven-day ingredient forecast in Management Reports; ready ML profile only, seasonal-mean model passed the two-window MAE backtest, CA/RM kitchen scope enforced; merged at `b317bee`, all four CI jobs passed; no migration or screenshot baseline changes |
| 2026-11-16 | 17B Customer Assistant verification / PR #33 | DDR-90, DDR-92, DDR-123 | Cherry-picked stranded `da19f7f`; fixed guard classifier capability selection and live availability reads; named acceptance tests, persisted measured 60-case evaluation remains DRAFT; migration 0029; merged at `e0e2bb7`, all four CI jobs passed |
| 2026-11-16 | Task 19A ETA fallback verification | DDR-125 | Rule fallback now uses the 80% chronological held-out residual interval (measured 80.00% coverage; model interval 80.48%); without a ready profile the point says “rough estimate, no range available”; DDR-111 (6) clarified to retain migration 0011's least-recently-offered order. `make check`, frontend-check, full integration (270 passed), and E2E (68 passed, 2 skipped) pass; 19B awaits owner approval |
| 2026-11-16 | Task 19A merged / CI fix / PR #34 | DDR-125 | CI's `test_cod_goes_straight_to_the_kitchen_with_snapshots_and_flags` caught the P2 landing worker publishing a valid outbox event before a transient unpublished-state assertion. Updated orders integration checks for durable fixture/event semantics and atomic pending-or-landed state; no application or migration change. `make check` (381), frontend-check (213), integration (270), and E2E (68 passed, 2 skipped) pass; hashes 21/21, DDR references clean. Fix is on `fix-main-ci`; 19B waits for merge and green CI. |
| 2026-11-16 | Main CI fix / PR #35 | DDR-125 | Merged at `1f3fdf7`; source-integrity, backend, frontend, and E2E all passed. Fixed the P2 outbox relay timing assumption in integration tests; no application or migration changes. Branch protection on `main` enabled. Task 19B resumed from the fixed main on `task-19b-eta-ui`. |
| 2026-11-16 | Task 19B ETA and assignment UI | DDR-125 | Customer order view gates remaining-travel ETA until pickup and displays range/no-range/synthetic labels; Management Delivery Operations adds read-only least-recently-offered suggestions. `make check` (381), `make frontend-check` (217), integration (270), E2E (68 passed, 2 skipped), DDR references clean; PR CI is the second E2E run. Awaiting owner approval before ship. |
| 2026-11-16 | Task 20 Monitoring and reconciliation / PR #36 | DDR-126 | Merged at `190210a`; reuses persisted pipeline run, stage and DQ results plus existing schedules and reconciliation checks. No schema gap is identified; migration 0031 remains conditional. |
| 2026-11-16 | Task 15B Builder Agent sandbox / PR #37 | DDR-127 | Merged; one-shot isolated task runner, HTTPS proxy allowlist, no socket or `.env` mount |
| 2026-11-16 | Task 19B ETA and assignment UI / PR #38 | DDR-125 | Merged; post-pickup ETA ranges and read-only suggestions; manual assignment preserved |
| 2026-11-16 | Task 15C Builder Agent harness / PR #39 | DDR-128 | Merged; CA-reviewed mock PR workflow, migrations 0031–0032 |
| 2026-11-16 | Task 21 E2E hardening / PRs #40–#41 | DDR-129 | Merged at `852a36a`; backend results and resource figures are recorded in §2; manual keyboard/screen-reader pass remains owner-pending |
| 2026-11-17 | Task 22 demo handover / PR pending | DDR-48–50, DDR-130 | Local gates and fresh-machine runbook passed; production-profile test rejects the loader and hides a Kitchen TEST canary; DRAFT approvals, CD-18 and manual accessibility remain open |

**Update this file** when a task closes: §2 status table, §5 next-task brief, and a §10 changelog line. The next session starts here.
