#!/usr/bin/env bash
set -euo pipefail

COMPOSE=(docker compose --project-directory . -f infra/compose.yaml --profile agent)
CONTAINERS="$("${COMPOSE[@]}" ps --all -q agent)"
if [[ -n "$CONTAINERS" ]]; then
  while IFS= read -r container_id; do
    [[ -z "$container_id" ]] || docker stop "$container_id" >/dev/null
  done <<< "$CONTAINERS"
fi
"${COMPOSE[@]}" stop egress-proxy >/dev/null 2>&1 || true
"${COMPOSE[@]}" rm -f egress-proxy >/dev/null 2>&1 || true
echo "PASS: interrupted Builder Agent runs stopped for the current Compose project"
