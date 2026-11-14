# DeliverIQ: instructions for Codex

Before any work, read these two files in full. They are binding:

1. `.kiro/steering/rules.md`: the build rules. "Kiro" in them means you (Codex).
2. `passon.md`: the handover guide (status, what to read, how to work, the next task's brief, gotchas).

Hard limits that are never relaxed:
- Never modify anything in `/home/k/Downloads/task1/` or `data/source/**` (`make verify-sources` stays 21/21).
- Never read, print, log or commit values from `.env` (for example `OTP_PEPPER`, `PSEUDONYM_KEY`); refer to secrets by key name.
- Never hand-edit `frontend/src/shared/api/generated/`; regenerate it with `make openapi` and `cd frontend && npm run api:generate`.
- Stage files by name (never `git add .` or `-A`); never push to `main`, force-push, `reset --hard`, `clean -f`, `branch -D` or use `--no-verify`; never change git config. The owner merges.
- One task at a time, on its own branch. Plan and decision sheet first; never invent values.
- No SOP recipe is ever activated (DDR-50); real and synthetic data never share a table (DDR-74).

Project skills (`.agents/skills/`): `$start-task`, `$verify`, `$report`, `$ship`.
Guard hooks (`.codex/hooks.json`) block unsafe git commands, `.env` reads and edits of protected paths; trust them with `/hooks` on first start.

`make up` rebuilds the API and migrate images; `make worker` rebuilds the worker image, which carries dbt.
