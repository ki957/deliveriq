# passon.md: DeliverIQ handover guide for Claude Code

**Written:** 2026-11-12, at the end of Task 8A, by Kiro. **For:** Claude Code, continuing the build.
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

`main` CI is green at PR #15 (8B merged, commit `00dab8f`). **Task 9 is planned and approved (DDR-113).** 9A is merged (PR #16, `main` at `e3cf478`). **9B (Delivery PWA UI) is built and verified on `task-09b-delivery-pwa`, waiting for approval/merge.** After it merges, **M2 is complete**; the next task is **10 (Unified management portal)**.

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
| **8A** | Kitchen operations and inventory **backend** (migration 0010, DDR-111) | ✅ merged (PR #13) |
| tooling | `CLAUDE.md`, `.claude/` commands + hook, `make reset-fixtures`, this guide | ✅ merged (PR #14) |
| 8B | Kitchen + Management UI for Task 8, tablet + KDS E2E (DDR-112) | ✅ merged (PR #15) |
| 9A | Delivery backend (migration 0011, DDR-113) | ✅ merged (PR #16) |
| **9B** | Delivery PWA UI | 🟡 **built and verified on `task-09b-delivery-pwa`; waiting for approval/merge** |
| **10** | Unified management portal | ⏭️ **next task** (needs `/start-task 10`: plan + decision sheet) |
| 9 – 22 | See §6 | ⬜ not started |

**Milestones** (plan §4.1):
- M1 Foundation (0–4): done.
- **M2 Core order flow (5–9): only Task 9 (9A, 9B) remains.**
- M3 Ops & data (10–14), M4 AI (15–17), M5 ML & polish (18–22): not started.

**First thing to do:** ask the owner whether the 9B PR is merged; then `/start-task 10`.

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
| `DESIGN_DECISION_REGISTER.md` | Every decision, DDR-01 → **DDR-111**. Part A Decided (owner tables 2026-11-11 and 2026-11-12; per-task rows DDR-101–111), Part B former proposals (all decided), **Part C open items** (DDR-06, 15, 41, 42, 43, 44, 45, 46), out-of-scope list | Before any design choice; add a new DDR row per task's decisions |
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
- `backend/app/modules/*/README.md`: identity, menu, recipes, pipelines, customers, pricing, orders, payments, kitchen_ops, inventory, delivery, health.
- `frontend/src/features/*/README.md`: auth, data-pipelines, recipes, approvals, ordering.
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
- `make reset-fixtures`: kitchen NORMAL, the three DDR-42 test defaults with their labels, TEST Dishes A–C PUBLISHED, TEST stock 10,000 g with no threshold (reserved stock is left alone and reported). Idempotent; ledger entries carry the reason "TEST fixture reset".

### Working loop (rules §2)
1. Inspect the task (plan §7), the DDRs and the code it touches.
2. Present a **plan + a decision sheet** in the §9 template: every value or behaviour the sources leave undefined, each with options and a ✔ recommendation. **Never invent** prices, thresholds, rules or formulas. Undefined values go on the sheet.
3. Wait for the owner. Typical replies are "go + approve all" or "will do as u recommend".
4. Record the approved sheet as a new **DDR row** (the next number after the last row; the last is **DDR-113**) in the register's Part A list. Update the Matrix or plan where a decision changes them, and show the change list first.
5. Build one task at a time on branch `task-NN-short-name`. Large tasks split into **A (backend)** and **B (UI)**.
6. Verify (below), self-review against `CODE_STRUCTURE_DESIGN.md` §13 plus security, scope and leak controls, and grade findings Blocker/High/Medium/Low. Blocker and High must be fixed; Medium and Low are fixed or logged.
7. Commit (stage **files by name**, never `git add .`; check no `.env` is staged) and report.
8. After the owner says "approve": push, then give the PR compare link plus a title and description. **`gh` is NOT installed**, so use the link `https://github.com/ki957/deliveriq/compare/main...<branch>?expand=1`. The owner squash-merges. **Never merge, never push to main, never force-push.**
9. After "merged": `git checkout main && git pull --ff-only`, check CI, delete the local branch.

### Report format (rules §10), kept short
What changed (files) · evidence per acceptance criterion (test names or command output) · review findings with grades · not verified and why · memory (`docker stats`, `free -h`) · open items · next task.

### Owner style
- Short replies.
- Approves recommendations quickly.
- Prefers squash merges.
- Is cost-sensitive: be efficient and don't repeat work.

---

## 5. Next task: 10 (Unified management portal)

Run `/start-task 10`. Read plan "### Task 10", Matrix §5 (MG-*, capability rows) and DDR-44 (YAML editor B: not built; exceptional-refund threshold A: disabled).

**APIs already built that Task 10 puts a UI on (do not rebuild):**
- Kitchen settings for RM/CA: `GET/PUT /api/v1/kitchen/settings?kitchen_id=` (mode, capacities, reason).
- Kitchen queue for RM/CA: `GET /api/v1/kitchen/orders?kitchen_id=`; "cannot fulfil": `POST /api/v1/kitchen/orders/{id}/reject` (KM/RM/CA).
- Delivery oversight: `GET /api/v1/delivery/manage/agents`, `POST …/orders/{id}/assign`, `POST …/agents/{id}/force-offline`, `POST …/orders/{id}/failure-decision`, `POST …/orders/{id}/code`.
- Dish availability decisions (already has a UI: `/management/dish-availability`); menu publication and recipe sign-off (UI exists); pipelines (UI exists, Task 10 completes it per DDR-63/64).
- Open from 9A: no automatic refund on an approved delivery failure (DDR-113 (7)); Task 10's refund workflow decides it (DDR-44 classes).

**Expect decision-sheet items for:** staff management fields and deactivation rules (MG-01), what "active work" blocks deactivation, refund workflow without thresholds, report/CSV scope (Task 13 builds marts), the audit log viewer filters.

**Known leftovers:** stale TEST orders from customer E2E (D16, Task 21); kitchen and delivery screens poll (Task 11 adds WebSockets).

---

## 6. Remaining tasks after 10 (full criteria in plan §7)

| Task | Summary | Key gates / notes |
|---|---|---|
| 11 Realtime | Authenticated WebSockets, server-side subscriptions; replaces 10 s polling | — |
| 12 ELT P2 | Outbox relay to `raw`, dbt staging→core→marts on demand | Events only from DATA_PIPELINE §6.3; leak control 6 |
| 13 Marts & analytics | Management analytics | DDR-44 KPIs labelled, not business truth |
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
- **Tests:** Vitest; Playwright (Chromium, pinned container).

### Repo map
- `backend/app/{core,shared,modules,pipelines,worker,cli}`
- `backend/migrations/versions/0001–0010` (**head = 0010**; `migrations/tests/test_schema_and_seeds.py` asserts the head; bump it with each migration)
- `frontend/src/{app,portals,features,shared}`
- `tests/e2e/{specs,__screenshots__}`
- `infra/compose.yaml`, `Makefile`, `.github/workflows/ci.yml` (jobs: source-integrity, backend, frontend, e2e)

### Make targets (from repo root)

| Command | Use |
|---|---|
| `make up` / `make down` | start / stop `core` (Postgres, Redis, API; runs migrations and `db-roles`) |
| `make worker` / `make worker-down` | pipeline worker (needed by the pipelines integration tests) |
| `make fixtures` | seed users, TEST menu, TEST50 coupon, seed address, **TEST opening stock** (idempotent) |
| `make reset-fixtures` | back to the shared TEST baseline (run before and after test runs) |
| `make check` | ruff, format, mypy strict, import-linter (5 contracts), unit tests, verify-sources (21/21), openapi-check |
| `make frontend-check` | typecheck, lint, Vitest, api:check, build |
| `timeout 900 make test-integration` | integration tests against the running stack (worker must be up) |
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
- Avoid broad `sed` across files; edit precisely.

### Git
- Remote: `git@github-kiro:ki957/deliveriq.git` (SSH host alias).
- Branch per task; never push to main.
- No force push, `reset --hard`, `clean -f` or `--no-verify`.
- Never change git config.

### Resources (16 GB laptop, rules §6)
- Run `free -h` before heavy jobs (e2e, dbt, embeddings). Stop if under 2 GB available.
- Never run heavy jobs together.
- Stop the stack after work (`make worker-down; make down`).
- Typical memory: API ~100 MiB, Postgres ~65–85 MiB, worker ~48 MiB, Redis ~6 MiB.
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
- [ ] `make check` ✔ · `make frontend-check` ✔ · `timeout 900 make test-integration` ✔ (stack + worker up) · `make e2e` ✔ (twice for new specs)
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
- After approval, add one register row `DDR-<next>` (the next number after the last row; the last is **DDR-113**) with numbered points (1), (2)…, matching D-numbers, in `docs/DESIGN_DECISION_REGISTER.md` after the last DDR row in Part A. Cite it in code comments as `DDR-nnn (3)`.

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
| 2026-11-12 | 9 plan | DDR-113 | Approved |
| 2026-11-12 | 9B / #17 | DDR-113 (19)–(20) | Delivery PWA; Leaflet pinned (lazy chunk); E2E agent fixture `load-e2e-agent`; full flow on phone-390, screens `@devices`. M2 complete |
| 2026-11-12 | 9A / #16 | DDR-113 | Migration 0011; delivery lifecycle, code, GPS, retention; worker uses 2 SECURITY DEFINER functions only |
| 2026-11-12 | 8B / #15 | DDR-112 | Kitchen screens + Management Dish Availability; `kds` 1920×1080 project (`@kitchen` on tablet + kds only); `e2e-setup` runs `reset-shared`; mask live counts in screenshots |

**Update this file** when a task closes: §2 status table, §5 next-task brief, and a §10 changelog line. The next session starts here.
