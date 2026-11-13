# DeliverIQ developer commands (DOCKER_DEPLOYMENT_DESIGN.md §9).
# Profiles: core (postgres, redis, migrate, api), e2e (Task 4B), worker (Task 5). Targets for osrm,
# agent and demo are added with those services (Tasks 9, 15B).

.PHONY: help install lint format typecheck imports test test-integration verify-sources openapi \
        openapi-check check env-check build up down restart ps logs migrate stats fixtures \
        e2e e2e-setup e2e-update frontend-check db-roles worker worker-down pipeline

UV := env -u VIRTUAL_ENV uv
PY_PATH := PYTHONPATH=backend
COMPOSE := docker compose --project-directory . -f infra/compose.yaml --profile core

help:
	@echo "Host checks"
	@echo "  install          Create .venv with the locked api + dev groups"
	@echo "  lint / format    Ruff lint + format check / apply formatting"
	@echo "  typecheck        mypy (strict)"
	@echo "  imports          import-linter dependency contracts"
	@echo "  test             Unit tests (integration tests skipped)"
	@echo "  verify-sources   Hash-check data/source against the inventory"
	@echo "  openapi          Regenerate backend/openapi.json"
	@echo "  openapi-check    Fail if backend/openapi.json is out of date"
	@echo "  check            All host checks"
	@echo "Docker (core profile)"
	@echo "  up / down        Start / stop core services (data volume preserved)"
	@echo "  ps / logs        Status / follow logs"
	@echo "  migrate          Run Alembic migrations once"
	@echo "  db-roles         Create any missing DB roles on an existing data volume (idempotent)"
	@echo "  worker           Start the worker profile (needs the core stack)"
	@echo "  worker-down      Stop the worker only"
	@echo "  pipeline         Queue a pipeline run and wait: make pipeline NAME=p1_sop [INPUT=fault:records]"
	@echo "  fixtures         Load local/test seed users and the TEST menu (refused outside local/test)"
	@echo "  e2e              Playwright suites in the pinned container (axe, screenshots, phones)"
	@echo "  e2e-update       Regenerate screenshot baselines (review before committing)"
	@echo "  frontend-check   Frontend typecheck, lint, unit tests, API client check, build"
	@echo "  stats            docker stats snapshot"
	@echo "  test-integration Integration tests against the running core stack"

install:
	$(UV) sync --locked

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy

imports:
	$(PY_PATH) $(UV) run lint-imports

test:
	$(UV) run pytest -m "not integration"

verify-sources:
	$(PY_PATH) $(UV) run python -m app.cli.source_registry --root data/source --inventory docs/SOURCE_DOCUMENT_INVENTORY.md

openapi:
	$(PY_PATH) $(UV) run python -m app.cli.export_openapi --write

openapi-check:
	$(PY_PATH) $(UV) run python -m app.cli.export_openapi --check

check: lint typecheck imports test verify-sources openapi-check

env-check:
	@test -f .env || { echo "Missing .env: copy .env.example to .env and set the passwords"; exit 1; }

build: env-check
	$(COMPOSE) build

# Postgres first, then any roles added since the volume was created (e.g. `worker`), then the rest,
# so migrations that need a new role find it.
up: env-check
	$(COMPOSE) up -d --build --wait postgres
	$(MAKE) --no-print-directory db-roles
	$(COMPOSE) up -d --build --wait
db-roles: env-check
	$(COMPOSE) exec -T postgres bash /docker-entrypoint-initdb.d/10-roles-and-extensions.sh
worker: env-check
	$(COMPOSE) --profile worker up -d --build --wait worker
worker-down:
	$(COMPOSE) --profile worker stop worker
# Runs as app_api (insert-only on run records), the same path as the UI trigger.
pipeline: env-check
	@test -n "$(NAME)" || { echo "Usage: make pipeline NAME=p1_sop [INPUT=fault:records]"; exit 1; }
	$(COMPOSE) exec -T api python -m app.cli.pipelines run "$(NAME)" $(if $(INPUT),--input "$(INPUT)") --wait

down:
	$(COMPOSE) --profile worker down

restart: down up

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

migrate: env-check
	$(COMPOSE) run --rm migrate

stats:
	docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}"

# Reads .env in a subshell; values are exported to the test process only, never printed.
fixtures: env-check
	$(COMPOSE) run --rm migrate python -m app.cli.fixtures load-all

# Back to the fixture baseline: kitchen NORMAL, test defaults, TEST dishes published, TEST stock 10,000 g.
reset-fixtures: env-check
	$(COMPOSE) run --rm migrate python -m app.cli.fixtures reset-shared

# Playwright in the pinned container against the running core stack (needs `make up` + `make fixtures`).
# Needs the core stack, the worker and fixtures (`make up worker fixtures`). Setup makes the data
# independent of earlier runs: the real SOP import (idempotent, through the worker) and one fresh
# `TEST – E2E <n>` DRAFT recipe for the workflow spec (DDR-108).
e2e-setup: env-check
	$(COMPOSE) exec -T api python -m app.cli.pipelines run p1_sop --wait
	$(COMPOSE) run --rm migrate python -m app.cli.fixtures load-e2e-recipe
e2e: e2e-setup
	$(COMPOSE) --profile e2e run --rm e2e

# Regenerate screenshot baselines after an intended UI change; review the diff before committing.
e2e-update: e2e-setup
	PLAYWRIGHT_ARGS="--update-snapshots" $(COMPOSE) --profile e2e run --rm e2e

frontend-check:
	cd frontend && npm run typecheck && npm run lint && npm test && npm run api:check && npm run build

test-integration: env-check
	@set -a; . ./.env; set +a; \
	DELIVERIQ_INTEGRATION=1 \
	INTEGRATION_API_URL="http://127.0.0.1:$${API_HOST_PORT:-8000}" \
	INTEGRATION_DB_PORT="$${POSTGRES_HOST_PORT:-5433}" \
	$(UV) run pytest -m integration -v
