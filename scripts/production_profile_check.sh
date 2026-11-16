#!/usr/bin/env bash
set -euo pipefail

set -a
# shellcheck disable=SC1091
. ./.env
set +a

export APP_ENV=production
export OTP_ADAPTER=disabled
export COMPOSE_PROJECT_NAME=deliveriq-production-check
export API_HOST_PORT=18080
export POSTGRES_HOST_PORT=15433
export INTEGRATION_API_URL=http://127.0.0.1:18080
export INTEGRATION_DB_PORT=15433
export DELIVERIQ_INTEGRATION=1
export DELIVERIQ_PRODUCTION_PROFILE=1

compose=(docker compose --project-directory . -f infra/compose.yaml --profile core)
cleanup() {
  docker compose --project-directory . -f infra/compose.yaml --profile worker down -v
}
trap cleanup EXIT

"${compose[@]}" up -d --build --wait

if refusal=$("${compose[@]}" run --rm migrate python -m app.cli.fixtures load-all 2>&1); then
  echo "production fixture loader unexpectedly succeeded" >&2
  exit 1
fi
grep -Fq 'refused: fixtures load only when APP_ENV is local or test' <<<"$refusal"
echo "production fixture loader refused as expected"

env PYTHONPATH=backend uv run pytest backend/app/modules/ai/tests/test_production_profile_integration.py -m integration -q
