---
description: Run every verification gate for the current task and summarise the evidence
---
Run the DeliverIQ gates in this order, from the repo root. Stop at the first failure, find the root cause, and fix it before continuing. If an approach has failed twice, stop and propose a different one.

1. `free -h`: stop and report if less than 2 GB is available.
2. `make up && make worker && make fixtures && make reset-fixtures` (migrations run inside `make up`; it rebuilds the image, which the migrate container needs after any migration edit).
3. `make check`: lint, format, mypy strict, import-linter, unit tests, verify-sources 21/21, openapi-check.
   - After any API change, first run `make openapi` and then `cd frontend && npm run api:generate`. Never run prettier on the generated client.
4. `make frontend-check`
5. `timeout 900 make test-integration`
6. `make e2e`. For new or changed screens, run `make e2e-update` and look at **every** new or changed baseline image, then `make e2e` twice.
7. Undefined-DDR check: every `DDR-nn` used in `docs/`, `backend/`, `frontend/src`, `tests/e2e/specs` exists in `docs/DESIGN_DECISION_REGISTER.md`.
8. `make reset-fixtures`, then `docker stats --no-stream` and `free -h` (record them for the report).
9. `make worker-down && make down`. Delete any temporary files you made.

Finish with a short table: gate, result, and the evidence (test counts or output lines).
