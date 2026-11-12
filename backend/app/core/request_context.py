"""Correlation ID per request, carried in a context variable and the X-Request-ID header."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_access_log = logging.getLogger("app.access")
_error_log = logging.getLogger("app.errors")


def current_request_id() -> str | None:
    return request_id_var.get()


def _internal_error_start() -> Message:
    return {
        "type": "http.response.start",
        "status": 500,
        "headers": [(b"content-type", b"application/json")],
    }


def _internal_error_body(request_id: str) -> Message:
    body = {"code": "internal_error", "message": "An unexpected error occurred", "request_id": request_id}
    return {"type": "http.response.body", "body": json.dumps(body).encode()}


def _resolve_request_id(raw: bytes | None) -> str:
    """Accept a caller's ID only if it is short and safe to log; otherwise generate one."""
    if raw is not None:
        candidate = raw.decode("latin-1")
        if _SAFE_REQUEST_ID.fullmatch(candidate):
            return candidate
    return uuid.uuid4().hex


class RequestContextMiddleware:
    """Pure ASGI middleware: sets the correlation ID and writes one access log line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        request_id = _resolve_request_id(headers.get(REQUEST_ID_HEADER.lower().encode()))
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500

        response_started = False

        async def send_with_header(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        except Exception:
            # Handled here (not by a Starlette Exception handler, which runs outside this
            # middleware) so the 500 envelope still carries the request ID. Details are logged only.
            _error_log.exception("unhandled error")
            if not response_started:
                await send_with_header(_internal_error_start())
                await send_with_header(_internal_error_body(request_id))
        finally:
            _access_log.info(
                "request completed",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)
