"""In-app notifications (CU-25, DL-16, KI-23; DDR-115 (10), (11)). Own rows only, for any signed-in user."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.db import get_engine
from app.core.permissions import Principal
from app.modules.notifications import repository as repo

HISTORY_DAYS = 30  # DL-16 "30-day history"; the worker purges older rows (DDR-115 (11))
LIST_MAX = 100
MARK_MAX = 100


@dataclass(frozen=True)
class Inbox:
    rows: list[repo.NotificationRow]
    unread: int


def inbox(principal: Principal) -> Inbox:
    with get_engine().connect() as conn:
        return Inbox(
            repo.recent(conn, principal.user_id, days=HISTORY_DAYS, limit=LIST_MAX),
            repo.unread_count(conn, principal.user_id, days=HISTORY_DAYS),
        )


def mark_read(principal: Principal, ids: list[uuid.UUID] | None) -> int:
    with get_engine().begin() as conn:
        return repo.mark_read(conn, principal.user_id, ids[:MARK_MAX] if ids is not None else None)
