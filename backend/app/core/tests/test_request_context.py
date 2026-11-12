from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.core.request_context import REQUEST_ID_HEADER, RequestContextMiddleware, current_request_id

pytestmark = pytest.mark.unit


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    @app.get("/echo")
    def echo() -> dict[str, str | None]:
        return {"request_id": current_request_id()}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("internal detail password=hunter2")

    return app


def test_generates_request_id_and_returns_it() -> None:
    response = TestClient(_app()).get("/echo")
    request_id = response.headers[REQUEST_ID_HEADER]
    assert len(request_id) == 32
    assert response.json()["request_id"] == request_id


def test_accepts_safe_caller_request_id() -> None:
    response = TestClient(_app()).get("/echo", headers={REQUEST_ID_HEADER: "trace-0001-abcd"})
    assert response.headers[REQUEST_ID_HEADER] == "trace-0001-abcd"


@pytest.mark.parametrize(
    "bad", ["short", "x" * 65, "has space here", "semi;colon=1234", "<script>xx</script>"]
)
def test_replaces_unsafe_caller_request_id(bad: str) -> None:
    response = TestClient(_app()).get("/echo", headers={REQUEST_ID_HEADER: bad})
    assert response.headers[REQUEST_ID_HEADER] != bad
    assert len(response.headers[REQUEST_ID_HEADER]) == 32


def test_unhandled_error_returns_envelope_with_request_id() -> None:
    response = TestClient(_app()).get("/boom", headers={REQUEST_ID_HEADER: "trace-boom-0001"})
    assert response.status_code == 500
    body = response.json()
    assert body == {
        "code": "internal_error",
        "message": "An unexpected error occurred",
        "request_id": "trace-boom-0001",
    }
    assert "hunter2" not in response.text


def test_not_found_uses_error_envelope() -> None:
    response = TestClient(_app()).get("/missing")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_access_log_line_has_correlation_id(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.access")
    TestClient(_app()).get("/echo", headers={REQUEST_ID_HEADER: "trace-log-00001"})
    records = [r for r in caplog.records if r.name == "app.access"]
    assert records, "expected an access log record"
    record = records[-1]
    assert record.__dict__["path"] == "/echo"
    assert record.__dict__["status"] == 200


def test_http_error_keeps_exception_headers() -> None:
    from fastapi import HTTPException

    app = _app()

    @app.get("/limited")
    def limited() -> None:
        raise HTTPException(status_code=429, detail="slow down", headers={"Retry-After": "30"})

    response = TestClient(app).get("/limited")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert response.json()["code"] == "http_429"
