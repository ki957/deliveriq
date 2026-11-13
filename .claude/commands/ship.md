---
description: After the owner approves - commit check, push the branch, and print the PR link and text
---
Only run this after the owner has said "approve" for the current task.

1. Confirm the branch is not `main`: `git branch --show-current`.
2. Confirm nothing secret is staged or committed: `git diff --cached --name-only` and `git show --name-only HEAD` must contain no `.env`, `*.pem`, `*.key` or credential files.
3. `git push -u origin <branch>`. Never force-push and never push `main`.
4. `gh` is not installed. Print this link for the owner:
   `https://github.com/ki957/deliveriq/compare/main...<branch>?expand=1`
5. Print a PR title (under 70 characters) and a description with the sections **Summary**, **Tested** and **Not done / logged**, in code blocks ready to paste.
6. Wait for "merged". Then run `git checkout main && git pull --ff-only`, check CI (`passon.md` §7 "CI failures"), and delete the local branch with `git branch -d <branch>`.
