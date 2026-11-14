#!/usr/bin/env bash
# Codex PreToolUse hook (rules §5, §7). Runs for Bash and apply_patch (see .codex/hooks.json).
# Bash: blocks unsafe git actions and reads of .env. apply_patch: blocks edits of protected paths.
# Exit 2 blocks the tool call; the message on stderr is shown to Codex.
set -euo pipefail

input="$(cat)"
read_field() { printf '%s' "$input" | python3 -c "import json,sys; d=json.load(sys.stdin); v=$1; print(v if isinstance(v,str) else '')"; }
tool="$(read_field 'd.get("tool_name","")')"
command="$(read_field 'd.get("tool_input",{}).get("command","")')"

block() {
  echo "Blocked by .codex/hooks/guard-git.sh: $1" >&2
  exit 2
}

# apply_patch sends the patch text as tool_input.command; file targets are on "*** Add/Update/Delete File:" and "*** Move to:" lines.
if [[ "$tool" == "apply_patch" ]]; then
  targets="$(printf '%s\n' "$command" | sed -nE 's/^\*\*\* (Add File|Update File|Delete File|Move to): (.*)$/\2/p')"
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    [[ "$path" == /home/k/Downloads/task1/* ]] && block "never modify /home/k/Downloads/task1/ (rules §1.3): $path"
    [[ "$path" =~ (^|/)data/source/ ]] && block "data/source/ is read-only and hash-checked (rules §1.3): $path"
    [[ "$path" =~ (^|/)frontend/src/shared/api/generated/ ]] && block "the generated client is never hand-edited; run make openapi + npm run api:generate: $path"
    [[ "$path" =~ (^|/)\.env(\.[^/]*)?$ && ! "$path" =~ \.env\.example$ ]] && block ".env files are edited by the owner only (rules §5): $path"
  done <<< "$targets"
  exit 0
fi

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
# Reading .env prints secret values (rules §5). .env.example is fine; make targets source .env themselves.
[[ "$command" =~ (cat|less|more|head|tail|bat|grep|rg|sed|awk|strings|xxd|od|cut|sort|nl|base64)[^\;\&\|]*(^|[[:space:]/\"\'])\.env([[:space:]\"\'\;\&\|]|$) ]] && block "never read or print .env values; refer to secrets by key name (rules §5)"

if [[ "$command" == *"git commit"* ]]; then
  staged="$(git diff --cached --name-only 2>/dev/null || true)"
  if printf '%s\n' "$staged" | grep -Eiq '(^|/)\.env($|\.)|\.pem$|\.key$|credential|secret'; then
    block "a secret-looking file is staged: $(printf '%s\n' "$staged" | grep -Ei '(^|/)\.env($|\.)|\.pem$|\.key$|credential|secret' | tr '\n' ' ')"
  fi
  branch="$(git branch --show-current 2>/dev/null || true)"
  [[ "$branch" == "main" ]] && block "do not commit on main; create task-NN-short-name first (rules §7)"
fi
exit 0
