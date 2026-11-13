# DeliverIQ: instructions for Claude Code

Before any work, read and follow these two files. They are binding:

@.kiro/steering/rules.md
@passon.md

Hard limits that are never relaxed:
- Never modify anything in `/home/k/Downloads/task1/`.
- Never read aloud, print, log or commit values from `.env`; refer to secrets by key name.
- Stage files by name (never `git add .` or `-A`); never push to `main`, force-push, `reset --hard`, `clean -f` or use `--no-verify`. The owner merges.
- One task at a time, on its own branch. Plan and decision sheet first; never invent values.

Project commands: `/start-task`, `/verify`, `/report`, `/ship` (see `.claude/commands/`).
