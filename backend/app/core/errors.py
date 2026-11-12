"""One error envelope for every API error: code, message, request_id (CODE_STRUCTURE §7)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import current_request_id


def error_body(code: str, message: str) -> dict[str, str | None]:
    return {"code": code, "message": message, "request_id": current_request_id()}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else f"http_{exc.status_code}"
        # Keep the exception's headers (e.g. Retry-After on 429).
        return JSONResponse(
            error_body(code, str(exc.detail)), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(error_body("validation_error", "Request validation failed"), status_code=422)

    # Unhandled exceptions are turned into the envelope by RequestContextMiddleware,
    # so the response keeps its request ID.
