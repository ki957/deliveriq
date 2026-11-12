"""Redis client. Used for pub/sub, rate limits and cache only; never as a durable queue (ADR-004)."""

from __future__ import annotations

from functools import lru_cache

from redis import Redis

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    url = get_settings().redis_url.get_secret_value()
    return Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
