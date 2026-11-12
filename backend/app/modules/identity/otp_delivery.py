"""OTP delivery adapters (DDR-40: no SMS provider in the POC; #15 §4.2 MOCK_OTP).

The mock adapter uses the fixed test code and sends nothing. It never logs the code. Config
validation already refuses `mock` outside local/test; this module checks again (defence in depth).
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import Settings
from app.core.security import new_otp_code
from app.modules.identity import domain as d

MOCK_OTP_CODE = "123456"


class OtpUnavailable(Exception):
    """No delivery channel is configured; login cannot proceed (fail closed)."""


class OtpSender(Protocol):
    def new_code(self) -> str: ...
    def send(self, mobile: str, code: str) -> None: ...


class MockOtpSender:
    def new_code(self) -> str:
        return MOCK_OTP_CODE

    def send(self, mobile: str, code: str) -> None:
        # Nothing is sent and nothing is logged (#15 §4.2: "Log OTP: false").
        return None


class DisabledOtpSender:
    def new_code(self) -> str:
        return new_otp_code(d.OTP_LENGTH)

    def send(self, mobile: str, code: str) -> None:
        raise OtpUnavailable


def sender_for(settings: Settings) -> OtpSender:
    if settings.otp_adapter == "mock":
        if not settings.is_local_or_test:
            raise RuntimeError("MOCK_OTP refused outside local/test")
        return MockOtpSender()
    return DisabledOtpSender()
