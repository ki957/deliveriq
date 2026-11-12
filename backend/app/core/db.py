"""Sync SQLAlchemy engine (DDR-82). Small pool: Postgres max_connections is 20 (DDR-62)."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=2,
        pool_pre_ping=True,
        pool_timeout=5,
        connect_args={"connect_timeout": 3},
    )
