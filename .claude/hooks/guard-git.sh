#!/usr/bin/env bash
# Claude Code PreToolUse hook for Bash (rules §5, §7). Blocks unsafe git actions before they run.
# Exit 2 blocks the command; the message on stderr is shown to Claude Code.
set -euo pipefail

input="$(cat)"
command="$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')"

block() {
  echo "Blocked by .claude/hooks/guard-git.sh: $1" >&2
  exit 2
}

# Each pattern stays inside one shell command (no ; & | between the parts).
end='([[:space:];&|]|$)'
[[ "$command" =~ --no-verify ]] && block "--no-verify is not allowed (rules §7)"
[[ "$command" =~ git[[:space:]]+push[^\;\&\|]*(--force|[[:space:]]-f$end) ]] && block "force push is not allowed (rules §7)"
[[ "$command" =~ git[[:space:]]+reset[[:space:]]+--hard ]] && block "reset --hard needs the owner's explicit permission (rules §7)"
[[ "$command" =~ git[[:space:]]+clean[[:space:]]+-[a-zA-Z]*f ]] && block "git clean -f needs the owner's explicit permission (rules §7)"
[[ "$command" =~ git[[:space:]]+branch[[:space:]]+-D ]] && block "branch -D needs the owner's explicit permission (rules §7)"
[[ "$command" =~ git[[:space:]]+config[[:space:]] ]] && block "git config must not be changed (rules §7)"
[[ "$command" =~ git[[:space:]]+add[[:space:]]+(\.|-A|--all)$end ]] && block "stage files by name, not git add . / -A (rules §7)"
[[ "$command" =~ git[[:space:]]+push[^\;\&\|]*[[:space:]:]main$end ]] && block "never push to main (rules §7)"

if [[ "$command" == *"git commit"* ]]; then
  staged="$(git diff --cached --name-only 2>/dev/null || true)"
  if printf '%s\n' "$staged" | grep -Eiq '(^|/)\.env($|\.)|\.pem$|\.key$|credential|secret'; then
    block "a secret-looking file is staged: $(printf '%s\n' "$staged" | grep -Ei '(^|/)\.env($|\.)|\.pem$|\.key$|credential|secret' | tr '\n' ' ')"
  fi
  branch="$(git branch --show-current 2>/dev/null || true)"
  [[ "$branch" == "main" ]] && block "do not commit on main; create task-NN-short-name first (rules §7)"
fi
exit 0
