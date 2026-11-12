# DeliverIQ developer commands (DOCKER_DEPLOYMENT_DESIGN.md §9).
# Task 2: core profile (postgres, redis, migrate, api). Targets for worker, osrm, e2e, agent and demo
# are added with those services (Tasks 4, 5, 9, 15B).

.PHONY: help install lint format typecheck imports test test-integration verify-sources openapi \
        openapi-check check env-check build up down restart ps logs migrate stats

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

up: env-check
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

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
test-integration: env-check
	@set -a; . ./.env; set +a; \
	DELIVERIQ_INTEGRATION=1 \
	INTEGRATION_API_URL="http://127.0.0.1:$${API_HOST_PORT:-8000}" \
	INTEGRATION_DB_PORT="$${POSTGRES_HOST_PORT:-5433}" \
	$(UV) run pytest -m integration -v
