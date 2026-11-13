"""App factory: settings validation, logging, middleware and router registration only.

Run with: uvicorn app.main:create_app --factory
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware
from app.modules.customers.api import addresses_router
from app.modules.customers.api import public_router as serviceability_router
from app.modules.delivery.api import manage_router as delivery_manage_router
from app.modules.delivery.api import router as delivery_router
from app.modules.health.api import router as health_router
from app.modules.identity.api import auth_router, me_router
from app.modules.identity.dependencies import CSRF_HEADER
from app.modules.inventory.api import router as inventory_router
from app.modules.kitchen_ops.api import router as kitchen_settings_router
from app.modules.management.api import router as management_router
from app.modules.menu.api import availability_router as menu_availability_router
from app.modules.menu.api import manage_router as menu_manage_router
from app.modules.menu.api import public_router as menu_public_router
from app.modules.orders.api import cart_router
from app.modules.orders.api import kitchen_router as kitchen_orders_router
from app.modules.orders.api import router as orders_router
from app.modules.pipelines.api import router as pipelines_router
from app.modules.recipes.api import router as recipes_router
from app.shared.fixture_guard import assert_no_fixtures

API_TITLE = "DeliverIQ API"
API_VERSION = "0.1.0"


def _build(app: FastAPI) -> FastAPI:
    """Routers and error handlers shared by the runtime app and the OpenAPI export."""
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(pipelines_router)
    app.include_router(recipes_router)
    app.include_router(menu_public_router)
    app.include_router(menu_manage_router)
    app.include_router(orders_router)
    app.include_router(cart_router)
    app.include_router(serviceability_router)
    app.include_router(addresses_router)
    app.include_router(kitchen_orders_router)
    app.include_router(kitchen_settings_router)
    app.include_router(inventory_router)
    app.include_router(menu_availability_router)
    app.include_router(delivery_router)
    app.include_router(delivery_manage_router)
    app.include_router(management_router)
    return app


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast on missing/invalid configuration
    configure_logging(settings.log_level)
    if settings.app_env == "production":
        # Leak control 3 (plan §5.2): never serve production with TEST fixture rows present.
        with get_engine().connect() as conn:
            assert_no_fixtures(conn)
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
