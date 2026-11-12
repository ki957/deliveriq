"""App factory: settings validation, logging, middleware and router registration only.

Run with: uvicorn app.main:create_app --factory
"""

from __future__ import annotations

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware
from app.modules.health.api import router as health_router

API_TITLE = "DeliverIQ API"
API_VERSION = "0.1.0"


def _build(app: FastAPI) -> FastAPI:
    """Routers and error handlers shared by the runtime app and the OpenAPI export."""
    register_error_handlers(app)
    app.include_router(health_router)
    return app


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast on missing/invalid configuration
    configure_logging(settings.log_level)
    app = FastAPI(title=API_TITLE, version=API_VERSION)
    app.add_middleware(RequestContextMiddleware)
    return _build(app)


def openapi_app() -> FastAPI:
    """Same routes as create_app, without environment configuration; used only to export OpenAPI."""
    return _build(FastAPI(title=API_TITLE, version=API_VERSION))
