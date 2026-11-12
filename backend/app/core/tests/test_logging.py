from __future__ import annotations

import json
import logging

import pytest

from app.core.logging import JsonFormatter, redact
from app.core.request_context import request_id_var

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "secret"),
    [
        ("otp=482913 sent", "482913"),
        ('{"token": "abc.def.ghi"}', "abc.def.ghi"),
        ("password: hunter2", "hunter2"),
        ("Authorization: Bearer eyJhbGciOi.payload.sig", "eyJhbGciOi.payload.sig"),
        ("call +91 9876543210 now", "9876543210"),
        ("agent 9123456789", "9123456789"),
        ("api_key=gsk_example_value", "gsk_example_value"),
    ],
)
def test_sensitive_values_are_redacted(raw: str, secret: str) -> None:
    assert secret not in redact(raw)


def test_ordinary_numbers_are_kept() -> None:
    assert redact("order 12345 total 50000 paise") == "order 12345 total 50000 paise"


def test_json_line_carries_request_id_and_redacts_extras() -> None:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "login otp=123456", None, None)
    record.phone = "9876543210"
    token = request_id_var.set("req-abc12345")
    try:
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["request_id"] == "req-abc12345"
    assert "123456" not in line["message"]
    assert line["phone"] == "[REDACTED_PHONE]"
    assert line["level"] == "INFO"
