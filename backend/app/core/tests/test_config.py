from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings

pytestmark = pytest.mark.unit


def test_valid_environment_loads(test_env: dict[str, str]) -> None:
    settings = get_settings()
    assert settings.app_env == "test"
    assert settings.is_local_or_test


@pytest.mark.parametrize("value", ["prod", "staging", "", "LOCAL"])
def test_app_env_must_be_local_test_or_production(
    test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("APP_ENV", value)
    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_production_is_not_local_or_test(test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OTP_ADAPTER", "disabled")  # mock is refused in production
    assert not Settings().is_local_or_test  # type: ignore[call-arg]


def test_missing_key_is_named_without_leaking_values(
    test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DB_PASSWORD")
    with pytest.raises(ValidationError) as caught:
        Settings()  # type: ignore[call-arg]
    message = str(caught.value)
    assert "DB_PASSWORD" in message
    assert test_env["REDIS_URL"] not in message


def test_password_is_escaped_in_database_url(
    test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DB_PASSWORD", "p@ss:w/rd#1")
    url = Settings().database_url  # type: ignore[call-arg]
    assert url.password == "p@ss:w/rd#1"
    assert "p@ss" not in str(url)  # rendered URL hides the password
    assert url.host == "db.invalid"


def test_secrets_are_hidden_in_repr(test_env: dict[str, str]) -> None:
    text = repr(get_settings())
    assert test_env["DB_PASSWORD"] not in text
    assert test_env["REDIS_URL"] not in text
