---
name: report
description: Use when a DeliverIQ task is verified and the owner needs the task report (rules §10), plus the passon.md update.
---
Write the report for the current task. Keep it short; no filler; no new markdown files.

## What changed
Files and modules, grouped (migrations, backend modules, frontend features, tests, docs).

## Evidence per acceptance criterion
One line per criterion from the plan, each with the test name or command output that proves it. "It exited 0" is not proof.

## Review findings
Run the `docs/CODE_STRUCTURE_DESIGN.md` §13 checklist plus security, RBAC and scope (404 outside scope, 403 wrong role), leak controls (plan §5.2), RAM and docs traceability. Grade each finding Blocker / High / Medium / Low and say whether it was fixed or logged with a reason. No Blocker or High may remain open. For large or security-sensitive diffs, run Codex `/review` on the branch diff first and include its findings.

## Not verified
What could not be checked and why.

## Memory
`docker stats --no-stream` and `free -h` figures.

## Next
Open items, and the next task proposed.

Then update `passon.md`: §2 status table, §3.5 README card list (new modules or features), §4/§9 "last DDR", §5 next-task brief, §7 (migration head, new gotchas, memory figures) and a §10 changelog line (newest last). If the workflow changed, update the matching `.agents/skills/` file and `AGENTS.md` too.
