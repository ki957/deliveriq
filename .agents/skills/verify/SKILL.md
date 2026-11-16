---
name: verify
description: Use when a DeliverIQ task is built and needs its verification gates run (make check, frontend-check, integration, e2e, DDR and hash checks) with evidence.
---
Run the DeliverIQ gates in this order, from the repo root. Stop at the first failure, find the root cause, and fix it before continuing. If an approach has failed twice, stop and propose a different one. Never run two heavy jobs at once (e2e, dbt, embeddings, agent, osrm-prep). Run each gate once against final code; rerun a passed gate only if code it covers changed afterward. After a clean rebase, run only `make check` and `make frontend-check` locally; CI covers the remaining gates.

Use the shared Docker lock only for integration, E2E and pipeline runs (including their required stack setup and fixture preparation). Do not queue for the lock solely to take a memory snapshot; use the last stack run's figures. The PR's CI is the second E2E run, so never run E2E twice locally. Run `make e2e-update` only when a screenshot assertion fails or a new screenshot is added, and inspect only the affected images.

1. `free -h`: stop and report if less than 2 GB is available. Use an immediately available snapshot; do not queue on the Docker lock for memory alone.
2. `make up && make worker && make fixtures && make reset-fixtures`.
   - `make up` rebuilds the image and runs migrations; the migrate container needs that after any migration edit.
   - `make worker` rebuilds the worker image, which carries dbt; needed after dependency or dbt-runtime changes.
3. If the task touches P2, dbt models or reports: `make pipeline NAME=p2_elt` so dbt rebuilds the models and applies its `grants` (otherwise `app_api` cannot read the marts).
4. `make check`: lint, format, mypy strict, import-linter, unit tests, verify-sources 21/21, openapi-check.
   - After any API change, first run `make openapi` and then `cd frontend && npm run api:generate`. Never run prettier on the generated client.
5. `make frontend-check`, plus `cd frontend && npx prettier --check "src/**/*.md"` when a frontend README changed (CI checks them).
6. `timeout 1200 make test-integration`
7. `make e2e` once locally. Run `make e2e-update` only when a screenshot assertion fails or a new screenshot is added; inspect only those new or changed images. The PR's CI is the second E2E run. One spec: `PLAYWRIGHT_ARGS="<spec>" make e2e` (spec name first).
8. Undefined-DDR check: every `DDR-nn` used in the code and docs exists in the register:
   ```
   used=$(grep -rhoE --exclude-dir=__pycache__ --exclude-dir=generated --exclude-dir=node_modules 'DDR-[0-9]+' docs frontend/src backend/app backend/migrations tests/e2e/specs .kiro passon.md analytics | sort -u)
   defined=$(grep -oE 'DDR-[0-9]+' docs/DESIGN_DECISION_REGISTER.md | sort -u)
   comm -23 <(echo "$used") <(echo "$defined")
   ```
   The last command must print nothing. Don't write a future DDR number (the next one) anywhere before its register row exists.
9. `make reset-fixtures`, then `docker stats --no-stream` and `free -h` (record the most recent stack run's figures for the report; do not queue solely for this snapshot).
10. `make worker-down && make down`. Delete any temporary files you made.

Finish with a short table: gate, result, and the evidence (test counts or output lines).
