"""Readiness checks. Each check returns True/False and never leaks error details to callers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import text

from app.core.db import get_engine
from app.core.redis_client import get_redis

_log = logging.getLogger("app.health")

Check = Callable[[], bool]


def check_database() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        _log.warning("readiness: database check failed", exc_info=True)
        return False


def check_redis() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        _log.warning("readiness: redis check failed", exc_info=True)
        return False


@dataclass(frozen=True)
class Readiness:
    ready: bool
    checks: dict[str, str]


def readiness(checks: dict[str, Check]) -> Readiness:
    results = {name: ("ok" if check() else "unavailable") for name, check in checks.items()}
    return Readiness(ready=all(value == "ok" for value in results.values()), checks=results)


def default_checks() -> dict[str, Check]:
    return {"database": check_database, "redis": check_redis}
