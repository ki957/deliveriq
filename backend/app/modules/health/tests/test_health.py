from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.health.service import default_checks

pytestmark = pytest.mark.unit


def _client(checks: dict[str, bool]) -> TestClient:
    app = create_app()
    app.dependency_overrides[default_checks] = lambda: {
        name: (lambda ok=ok: ok) for name, ok in checks.items()
    }
    return TestClient(app)


def test_live_is_always_ok(test_env: dict[str, str]) -> None:
    response = TestClient(create_app()).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_ready_when_all_checks_pass(test_env: dict[str, str]) -> None:
    response = _client({"database": True, "redis": True}).get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


@pytest.mark.parametrize("failing", ["database", "redis"])
def test_not_ready_when_a_dependency_fails(test_env: dict[str, str], failing: str) -> None:
    checks = {"database": True, "redis": True, failing: False}
    response = _client(checks).get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"][failing] == "unavailable"


def test_real_checks_report_unavailable_without_leaking_details(test_env: dict[str, str]) -> None:
    # TEST_ENV points at .invalid hosts, so both real checks fail fast.
    response = TestClient(create_app()).get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "unavailable", "redis": "unavailable"},
    }
    assert "invalid" not in response.text


def test_app_refuses_to_start_with_bad_app_env(
    test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("APP_ENV", "staging")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="APP_ENV"):
        create_app()
