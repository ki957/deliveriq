---
description: Inspect a task and present the plan and decision sheet (no code yet)
argument-hint: <task number, e.g. 8B or 9>
---
Start DeliverIQ task **$ARGUMENTS**. Do not write code in this step.

1. Confirm `main` is clean and current: `git status --short`, `git checkout main && git pull --ff-only`, and that the last PR's CI is green (see `passon.md` §7 "CI failures").
2. Read `passon.md` §2 and §5, and the task's section in `docs/DELIVERIQ_EXECUTION_PLAN.md` (find it with `grep -n "### Task $ARGUMENTS" docs/DELIVERIQ_EXECUTION_PLAN.md`; read only that section plus §5.2 and §6).
3. Grep, don't read whole files: every DDR the task cites (`grep -n "DDR-NN" docs/DESIGN_DECISION_REGISTER.md`), its Matrix IDs in `docs/PORTAL_REQUIREMENTS_MATRIX.md`, and the README cards of the modules and features it touches.
4. Inspect the existing code it will change. For broad investigation, use a sub-agent so the main context stays small.
5. Present:
   - **Plan:** scope, files and modules, how each acceptance criterion will be proved (named tests), and any split into A (backend) / B (UI).
   - **Decision sheet:** every value or behaviour the sources leave undefined, in the template from `passon.md` §9. Mark each recommendation with ✔. Never invent values.
6. Stop and wait for the owner ("go + approve all", or changes per D-number).
