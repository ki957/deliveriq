from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.cli.export_openapi import DEFAULT_PATH, main, render

pytestmark = pytest.mark.unit


def test_committed_schema_is_current() -> None:
    assert DEFAULT_PATH.read_text(encoding="utf-8") == render(), "run `make openapi` and commit the result"


def test_schema_lists_health_routes() -> None:
    paths = json.loads(render())["paths"]
    assert {"/health/live", "/health/ready"} <= set(paths)


def test_check_fails_on_drift(tmp_path: Path) -> None:
    stale = tmp_path / "openapi.json"
    stale.write_text("{}\n", encoding="utf-8")
    assert main(["--check", "--path", str(stale)]) == 1
    assert main(["--write", "--path", str(stale)]) == 0
    assert main(["--check", "--path", str(stale)]) == 0
