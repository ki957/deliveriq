"""Pseudonymous customer keys (DDR-116 (5))."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.shared.pseudonym import customer_key


def test_keys_are_stable_distinct_and_never_the_id(test_env: dict[str, str]) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    assert customer_key(a) == customer_key(a)
    assert customer_key(a) != customer_key(b)
    assert str(a) not in customer_key(a) and len(customer_key(a)) == 64


def test_another_secret_gives_another_key(test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    a = uuid.uuid4()
    first = customer_key(a)
    monkeypatch.setenv("PSEUDONYM_KEY", "x" * 40)
    get_settings.cache_clear()
    assert customer_key(a) != first


def test_a_short_secret_is_refused(test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSEUDONYM_KEY", "short")
    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="PSEUDONYM_KEY"):
        get_settings()
