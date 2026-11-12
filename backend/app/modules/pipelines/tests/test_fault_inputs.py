"""Fault-injection inputs: refused in production, always flagged as test (DDR-65, DDR-104)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.pipelines import repository, service

pytestmark = pytest.mark.unit
REPO = Path(__file__).resolve().parents[5]


def _stub(monkeypatch: pytest.MonkeyPatch, app_env: str) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        service, "get_settings", lambda: SimpleNamespace(is_local_or_test=app_env != "production")
    )
    monkeypatch.setattr(repository, "find_pipeline", lambda conn, name: object())
    monkeypatch.setattr(repository, "kitchen_region", lambda conn, code: None)

    def insert_run(conn: Any, **kwargs: Any) -> str:
        captured.update(kwargs)
        return "run"

    monkeypatch.setattr(repository, "insert_run", insert_run)
    return captured


class _Nested:
    def __enter__(self) -> _Nested:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _Conn:
    """Only the savepoint the queue opens around its insert; every repository call is stubbed."""

    def begin_nested(self) -> _Nested:
        return _Nested()


@pytest.mark.parametrize("ref", sorted(service.FAULT_INPUTS))
def test_fault_inputs_are_refused_in_production(monkeypatch: pytest.MonkeyPatch, ref: str) -> None:
    _stub(monkeypatch, "production")
    with pytest.raises(service.FaultInputRefused):
        service._queue(None, pipeline="p1_sop", input_ref=ref, trigger="ui", actor_user_id=None)  # type: ignore[arg-type]


def test_fault_runs_are_always_test_runs_and_sop_is_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _stub(monkeypatch, "local")
    conn = _Conn()
    service._queue(conn, pipeline="p1_sop", input_ref="fault:records", trigger="ui", actor_user_id=None)  # type: ignore[arg-type]
    assert (captured["is_test"], captured["input_ref"]) == (True, "fault:records")
    service._queue(conn, pipeline="p1_sop", input_ref=None, trigger="ui", actor_user_id=None)  # type: ignore[arg-type]
    assert (captured["is_test"], captured["input_ref"]) == (False, "sop")


def test_fault_files_are_never_copied_into_images() -> None:
    dockerfile = (REPO / "infra" / "backend" / "Dockerfile").read_text(encoding="utf-8")
    copies = [line for line in dockerfile.splitlines() if line.strip().startswith("COPY")]
    assert copies and not any("test_inputs" in line for line in copies)
    assert all(
        "backend/app" in line
        or "migrations" in line
        or "alembic.ini" in line
        or "--from=" in line
        or "pyproject" in line
        for line in copies
    )


@pytest.mark.parametrize(
    ("app_env", "expected"),
    [("local", ["sop", "fault:records", "fault:structural"]), ("production", ["sop"])],
)
def test_listed_inputs_follow_the_environment(
    monkeypatch: pytest.MonkeyPatch, app_env: str, expected: list[str]
) -> None:
    monkeypatch.setattr(
        service, "get_settings", lambda: SimpleNamespace(is_local_or_test=app_env != "production")
    )
    assert service.available_inputs("p1_sop") == expected
    assert service.available_inputs("p2_elt") == []
