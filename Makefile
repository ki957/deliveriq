# DeliverIQ developer commands.
# Task 1 provides host-side Python checks. Docker targets (up, down, worker, osrm, e2e, agent,
# demo, ...) are added in Task 2 per DOCKER_DEPLOYMENT_DESIGN.md §9; `test`/`lint` then move into
# the backend container.

.PHONY: help install lint format typecheck imports test verify-sources check

UV := env -u VIRTUAL_ENV uv
PY_PATH := PYTHONPATH=backend

help:
	@echo "install         Create .venv and install locked dev tools"
	@echo "lint            Ruff lint + format check"
	@echo "format          Apply Ruff formatting to Python files"
	@echo "typecheck       mypy (strict)"
	@echo "imports         import-linter dependency contracts"
	@echo "test            pytest"
	@echo "verify-sources  Hash-check data/source against the inventory"
	@echo "check           All of the above (except format)"

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
	$(UV) run pytest

verify-sources:
	$(PY_PATH) $(UV) run python -m app.cli.source_registry --root data/source --inventory docs/SOURCE_DOCUMENT_INVENTORY.md

check: lint typecheck imports test verify-sources
