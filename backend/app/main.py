"""App factory: settings validation, logging, middleware and router registration only.

Run with: uvicorn app.main:create_app --factory
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware
from app.modules.health.api import router as health_router
from app.modules.identity.api import auth_router, me_router
from app.modules.identity.dependencies import CSRF_HEADER

API_TITLE = "DeliverIQ API"
API_VERSION = "0.1.0"


def _build(app: FastAPI) -> FastAPI:
    """Routers and error handlers shared by the runtime app and the OpenAPI export."""
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    return app


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast on missing/invalid configuration
    configure_logging(settings.log_level)
    app = FastAPI(title=API_TITLE, version=API_VERSION)
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=[CSRF_HEADER, "Content-Type", "X-Request-ID"],
        )
    app.add_middleware(RequestContextMiddleware)
    _build(app)
    if settings.is_local_or_test:
        # Never mounted in production; excluded from the committed OpenAPI contract.
        from app.modules.identity.testing_api import router as testing_router

        app.include_router(testing_router)
    return app


def openapi_app() -> FastAPI:
    """Same public routes as create_app, without environment configuration; used to export OpenAPI."""
    return _build(FastAPI(title=API_TITLE, version=API_VERSION))
