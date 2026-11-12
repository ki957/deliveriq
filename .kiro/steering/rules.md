---
inclusion: always
---
# DeliverIQ — Build Rules for Kiro

**Version:** 1.0 (approved 2026-11-12)

These rules bind Kiro (IDE and CLI) for every build step. If a rule conflicts with a request, stop and ask the owner.

## 1. Sources of truth

1. Precedence: owner's explicit instruction in this session → `docs/DESIGN_DECISION_REGISTER.md` (Decided) → design docs (`DOCKER_DEPLOYMENT_DESIGN.md`, `DATA_PIPELINE_DESIGN.md`, `CODE_STRUCTURE_DESIGN.md`, `RAG_AI_DESIGN.md`) → `DELIVERIQ_EXECUTION_PLAN.md` → `PORTAL_REQUIREMENTS_MATRIX.md` → source files.
2. If two documents conflict, stop, show both, and ask. Never pick silently.
3. Never modify anything in `/home/k/Downloads/task1/`. Work from the committed, hash-checked copies.
4. Never invent requirements, business rules, recipe data, prices, thresholds or KPI formulas. Missing information is written as "not defined" and raised as a question.
5. Open decisions follow the B/A/P/G classes in plan §5: don't build B items, keep A items behind a disabled flag, label P items, and don't start a task while its G gate is unapproved.

## 2. Working loop (every task)

1. **Inspect:** read the task in the plan, the design sections it cites, the register entries, and the existing code it touches.
2. **Plan:** state the scope, the files, the acceptance criteria to prove and the tests to add. Wait for the owner's go-ahead on the first task of each milestone.
3. **One task at a time.** No work from later tasks, and no unrequested features, abstractions or refactors.
4. **Questions:** one at a time, with options and a recommendation.
5. **Implement** following `CODE_STRUCTURE_DESIGN.md`.
6. **Verify** (§4), then **review** (§8), then **report** (§10).
7. If an approach fails twice, stop patching. Find the root cause and propose a different approach.

## 3. Code rules

- Layout, layers and dependency rules per `CODE_STRUCTURE_DESIGN.md`. import-linter, Ruff, mypy, ESLint and TypeScript strict must pass.
- Sync SQLAlchemy 2.x + psycopg 3. Async only for WebSockets, Redis and outbound HTTP.
- The TypeScript API client is generated from OpenAPI, never hand-written.
- New dependency: only if needed, pinned in `uv.lock` / `package-lock.json`, from a well-known package, recorded with a reason, and with an ADR if it's a platform choice. Flag any name that looks unusual.
- Every feature and AI harness gets its README card, kept up to date.
- No commented-out code, and no TODO without an issue reference.

## 4. Verification and evidence

- Run format, lint, types, unit, integration and the import-linter check before reporting. Run E2E where the task requires it.
- Each acceptance criterion is proved by a test or by command output shown in the report. "It exited 0" is not proof.
- No simulated success. UI states come from persisted data, and mocks are labelled.
- Add tests for every behaviour changed and every bug fixed.
- At each milestone gate, record memory with `free -h` and `docker stats`.
- If something can't be verified, say so explicitly, with the reason.
- Delete any temporary files made during verification.

## 5. Security and data

- Secrets live only in `.env` (git-ignored) or GitHub Actions secrets. Never print, log, commit or echo values; refer to them by key name.
- Deny by default. Authorization is enforced in the backend; UI hiding is never the security boundary.
- Never weaken auth, RBAC, region scope, audit, the per-pipeline/per-portal DB roles or the AI guardrails (`PORTAL_REQUIREMENTS_MATRIX.md` §10) without an approved DDR.
- TEST fixtures: all eight leak controls (plan §5.2) must hold. No SOP recipe is ever activated (DDR-50).
- Real and synthetic data never share a table (DDR-74).
- AI: harness code never holds provider or model IDs (DDR-85). Builder Agent protected paths stay protected (DDR-71, DDR-87). No Docker socket in any app container.
- Use parameterized queries only, validate input at the API boundary, and quote shell input correctly.

## 6. Resources (16 GB laptop)

- Start only the Compose profiles the task needs, and stop them afterwards.
- Never run heavy jobs at the same time (dbt, embedding, e2e, agent, osrm-prep).
- Before starting a heavy profile, check `free -h`. If headroom is under 2 GB, stop and report.

## 7. Host, git and destructive actions

- Kiro CLI does host setup. Any change to the owner's shell or user config (for example conda) needs the owner's confirmation at that moment (DDR-79).
- **Commit policy:** one branch per task (`task-NN-short-name`). Commit when the task's review is clean. After the owner approves the task report, push the branch and open a PR. The owner merges on GitHub. Kiro never merges.
- Never push to `main`. No force push, `reset --hard`, `clean -f`, `branch -D`, `--amend` on pushed commits, or `--no-verify`. Never change git config.
- Stage files by name, not `git add .`. Check that no `.env` or credential file is staged before every commit.
- Ask before any destructive or broad action: `docker compose down -v`, dropping data, mass deletes, or installs outside the project.

## 8. Review checklist (end of each task)

- Run the `CODE_STRUCTURE_DESIGN.md` §13 checklist, plus security, RBAC and scope, leak controls, RAM and docs traceability.
- Grade findings as Blocker, High, Medium or Low. A Blocker or High finding is fixed before the task closes. Medium and Low findings are fixed or logged with a reason.

## 9. Documentation updates

- Any change to a decision or design: show the change list, get the owner's explicit approval, then update the register and every affected doc and bump their versions.
- After any docs change, run the undefined-DDR check and the 21-file source hash check.
- Don't create new markdown files unless the plan or the owner asks for them.

## 10. Task report format

Each report gives: what changed (files), evidence per acceptance criterion, review findings with grades, anything not verified and why, memory figures where relevant, open items, and the next task proposed. A few short sections, no filler.

## 11. Location

This file is the single source of the build rules. It loads in every Kiro session (`inclusion: always`). `docs/` holds no copy; the plan and the code-structure design link here.
