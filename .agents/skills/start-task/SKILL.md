---
name: start-task
description: Use when the owner says to start or plan a DeliverIQ task (e.g. "start task 14"). Inspects the task and presents the plan and decision sheet; writes no code.
---
Start the DeliverIQ task number the owner gave (e.g. 14 or 15A); call it `<n>` below. If no number was given, ask. Do not write code in this step.

1. Confirm `main` is clean and current: `git status --short`, `git checkout main && git pull --ff-only`, and that the last PR's CI is green (see `passon.md` §7 "CI failures").
2. Read `passon.md` §2, §5 (the brief for this task) and the §7 gotchas, and the task's section in `docs/DELIVERIQ_EXECUTION_PLAN.md` (find it with `grep -n "### Task <n>" docs/DELIVERIQ_EXECUTION_PLAN.md`; read only that section plus §5.2 and §6).
3. Grep, don't read whole files: every DDR the task cites (`grep -n "DDR-NN" docs/DESIGN_DECISION_REGISTER.md`), its Matrix IDs in `docs/PORTAL_REQUIREMENTS_MATRIX.md`, and the README cards of the modules and features it touches.
4. Inspect the existing code it will change. For broad investigation, grep and read narrow line ranges so the context stays small.
5. Present:
   - **Plan:** scope, files and modules, how each acceptance criterion will be proved (named tests), and any split into A (backend) / B (UI).
   - **Decision sheet:** every value or behaviour the sources leave undefined, in the template from `passon.md` §9. Mark each recommendation with ✔. Never invent values.
6. Stop and wait for the owner ("go + approve all", or changes per D-number).
