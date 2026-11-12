"""Shared pytest fixtures. Unit tests never need a database or Redis."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.redis_client import get_redis

TEST_ENV = {
    "APP_ENV": "test",
    "DB_HOST": "db.invalid",
    "DB_PORT": "5432",
    "POSTGRES_DB": "deliveriq_test",
    "DB_USER": "app_api",
    "DB_PASSWORD": "unit-test-only",
    "REDIS_URL": "redis://redis.invalid:6379/0",
    "OTP_ADAPTER": "mock",
    "OTP_PEPPER": "unit-test-pepper-not-secret",
}


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_redis.cache_clear()


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, str]]:
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    _clear_caches()
    yield dict(TEST_ENV)
    _clear_caches()
