#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
MODE="${1:-shell}"
python3 infra/agent/snapshot.py check-clean "$ROOT"
if ! git ls-files --cached -z | python3 -c '
import sys

paths = sys.stdin.buffer.read().split(b"\0")
names = (path.rsplit(b"/", 1)[-1] for path in paths if path)
sys.exit(1 if any(name.startswith(b".env") and name != b".env.example" for name in names) else 0)
'; then
  echo "Refusing to seed tracked .env files into the agent sandbox" >&2
  exit 1
fi
TMP_DIR="$(mktemp -d /dev/shm/deliveriq-agent.XXXXXX)"
CONTAINER_ID=""
COMPOSE=(docker compose --project-directory . -f infra/compose.yaml -f "$TMP_DIR/override.json" --profile agent)

cleanup() {
  if [[ -n "$CONTAINER_ID" ]]; then
    docker stop "$CONTAINER_ID" >/dev/null 2>&1 || true
  fi
  bash infra/agent/stop.sh >/dev/null 2>&1 || true
  rm -rf -- "$TMP_DIR"
}
trap cleanup EXIT INT TERM

python3 infra/agent/snapshot.py clone-head "$ROOT" "$TMP_DIR/repo"
python3 infra/agent/compose_override.py backend/config/ai_models.yaml "$TMP_DIR/override.json" "$TMP_DIR/repo"
"${COMPOSE[@]}" up -d --build egress-proxy >/dev/null
CONTAINER_ID="$("${COMPOSE[@]}" run --detach --rm agent sleep infinity)"

if [[ "$MODE" == "check" ]]; then
  python3 infra/agent/check_container.py "$CONTAINER_ID"
  docker exec "$CONTAINER_ID" pytest -m "not integration" -q
  docker exec "$CONTAINER_ID" pytest tests/agent/test_proxy.py -q
  docker exec "$CONTAINER_ID" curl --silent --show-error --output /dev/null --fail --location --connect-timeout 8 --max-time 20 https://github.com/
  if docker exec "$CONTAINER_ID" curl --noproxy '*' --silent --output /dev/null --fail --connect-timeout 5 --max-time 10 https://example.com/; then
    echo "FAIL: direct non-allowlisted egress succeeded"
    exit 1
  fi
  for service_port in postgres:5432 redis:6379; do
    service="${service_port%:*}"
    port="${service_port#*:}"
    core_container="$(docker compose --project-directory . -f infra/compose.yaml --profile core ps -q "$service")"
    if [[ -z "$core_container" ]]; then
      echo "FAIL: core service $service is not running for the direct-IP isolation probe" >&2
      exit 1
    fi
    service_ips="$(docker inspect "$core_container" | python3 -c 'import json,sys; item=json.load(sys.stdin)[0]; ips=sorted({network.get("IPAddress", "") for network in item["NetworkSettings"]["Networks"].values() if network.get("IPAddress")}); print("\n".join(ips))')"
    if [[ -z "$service_ips" ]]; then
      echo "FAIL: core service $service has no container IP for the direct-IP isolation probe" >&2
      exit 1
    fi
    while IFS= read -r service_ip; do
      [[ -z "$service_ip" ]] && continue
      probe_result="$(docker exec "$CONTAINER_ID" python -c 'import socket,sys;
try: connection=socket.create_connection((sys.argv[1],int(sys.argv[2])),timeout=2)
except OSError: print("BLOCKED")
else: connection.close(); print("REACHED")' "$service_ip" "$port")"
      if [[ "$probe_result" != "BLOCKED" ]]; then
        echo "FAIL: sandbox reached core service $service by container IP" >&2
        exit 1
      fi
    done <<< "$service_ips"
  done
  echo "PASS: direct egress and Postgres/Redis container-IP connections are denied"
  echo "PASS: agent isolation, resource and egress checks"
elif [[ "$MODE" == "shell" ]]; then
  docker exec -it "$CONTAINER_ID" bash
else
  echo "Usage: make agent [MODE=shell|check]" >&2
  exit 2
fi
