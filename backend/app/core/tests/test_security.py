from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import new_otp_code, new_token, otp_hash, token_hash

pytestmark = pytest.mark.unit


def test_tokens_are_random_and_hashed() -> None:
    a, b = new_token(), new_token()
    assert a != b and len(a) >= 43
    assert token_hash(a) != a and len(token_hash(a)) == 64


def test_otp_hash_is_keyed_and_bound_to_mobile() -> None:
    base = otp_hash("123456", mobile="+919876543210", pepper="p" * 20)
    assert base != otp_hash("123456", mobile="+919876543210", pepper="q" * 20)
    assert base != otp_hash("123456", mobile="+919876543211", pepper="p" * 20)
    assert "123456" not in base


def test_generated_codes_are_six_digits() -> None:
    assert all(len(c) == 6 and c.isdigit() for c in (new_otp_code(6) for _ in range(50)))


def test_mock_otp_refused_in_production(test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ValidationError, match="OTP_ADAPTER=mock"):
        Settings()  # type: ignore[call-arg]


def test_short_pepper_rejected(test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTP_PEPPER", "short")
    with pytest.raises(ValidationError, match="OTP_PEPPER"):
        Settings()  # type: ignore[call-arg]


def test_cookies_secure_only_in_production(test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    assert not Settings().secure_cookies  # type: ignore[call-arg]
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OTP_ADAPTER", "disabled")
    assert Settings().secure_cookies  # type: ignore[call-arg]
