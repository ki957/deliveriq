from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.identity.otp_delivery import MOCK_OTP_CODE, DisabledOtpSender, OtpUnavailable, sender_for

pytestmark = pytest.mark.unit


def test_production_uses_disabled_sender_which_fails_closed(
    test_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OTP_ADAPTER", "disabled")
    sender = sender_for(Settings())  # type: ignore[call-arg]
    assert isinstance(sender, DisabledOtpSender)
    with pytest.raises(OtpUnavailable):
        sender.send("+919876543210", sender.new_code())


def test_mock_sender_uses_fixed_test_code(test_env: dict[str, str]) -> None:
    sender = sender_for(Settings())  # type: ignore[call-arg]
    assert sender.new_code() == MOCK_OTP_CODE
