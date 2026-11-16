#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
MODE="${1:-shell}"
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

git clone --quiet --no-hardlinks --local . "$TMP_DIR/repo"
find "$TMP_DIR/repo" -maxdepth 1 -type f \( -name '.env' -o -name '.env.*' \) ! -name '.env.example' -delete
git diff --binary HEAD -- . ':(exclude).env' ':(exclude).env.*' ':(exclude)data/source/**' > "$TMP_DIR/task.patch"
git -C "$TMP_DIR/repo" apply "$TMP_DIR/task.patch"
while IFS= read -r source_file; do
  case "$source_file" in
    .env|.env.*|*/.env|*/.env.*|data/source/*) continue ;;
  esac
  mkdir -p "$TMP_DIR/repo/$(dirname "$source_file")"
  cp -a -- "$source_file" "$TMP_DIR/repo/$source_file"
done < <(git ls-files --others --exclude-standard)
python3 infra/agent/compose_override.py backend/config/ai_models.yaml "$TMP_DIR/override.json" "$TMP_DIR/repo"
"${COMPOSE[@]}" up -d --build egress-proxy >/dev/null
CONTAINER_ID="$("${COMPOSE[@]}" run --detach --rm agent sleep infinity)"

if [[ "$MODE" == "check" ]]; then
  python3 infra/agent/check_container.py "$CONTAINER_ID"
  docker exec "$CONTAINER_ID" pytest -m "not integration" -q
  docker exec "$CONTAINER_ID" pytest tests/agent/test_proxy.py -q
  docker exec "$CONTAINER_ID" curl --silent --show-error --output /dev/null --fail --location --connect-timeout 8 --max-time 20 https://github.com/
  if docker exec "$CONTAINER_ID" curl --silent --show-error --output /dev/null --fail --connect-timeout 5 --max-time 10 -x http://egress-proxy:3128 https://example.com/; then
    echo "FAIL: non-allowlisted egress succeeded"
    exit 1
  fi
  docker exec "$CONTAINER_ID" python -c 'import socket; targets=(("postgres",5432),("redis",6379));
for host,port in targets:
 try: socket.create_connection((host,port),timeout=2)
 except OSError: continue
 raise SystemExit(f"FAIL: sandbox reached {host}:{port}")'
  echo "PASS: agent isolation, resource and egress checks"
elif [[ "$MODE" == "shell" ]]; then
  docker exec -it "$CONTAINER_ID" bash
else
  echo "Usage: make agent [MODE=shell|check]" >&2
  exit 2
fi
