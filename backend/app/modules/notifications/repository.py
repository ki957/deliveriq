"""Notification reads and read marks, always for one owner (rows are written by triggers, migration 0013)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Connection, bindparam, text


@dataclass(frozen=True)
class NotificationRow:
    id: uuid.UUID
    kind: str
    order_id: uuid.UUID | None
    ingredient_name: str | None
    is_test_fixture: bool
    created_at: datetime
    read_at: datetime | None


def recent(conn: Connection, user_id: uuid.UUID, *, days: int, limit: int) -> list[NotificationRow]:
    rows = conn.execute(
        text(
            "SELECT n.id, n.kind, n.order_id, i.name, n.is_test_fixture, n.created_at, n.read_at "
            "FROM app.notifications n LEFT JOIN app.ingredients i ON i.id = n.ingredient_id "
            "WHERE n.user_id = :u AND n.created_at > now() - make_interval(days => :d) "
            "ORDER BY n.created_at DESC, n.id LIMIT :l"
        ),
        {"u": user_id, "d": days, "l": limit},
    ).all()
    return [NotificationRow(*r) for r in rows]


def unread_count(conn: Connection, user_id: uuid.UUID, *, days: int) -> int:
    count: int = conn.execute(
        text(
            "SELECT count(*) FROM app.notifications WHERE user_id = :u AND read_at IS NULL "
            "AND created_at > now() - make_interval(days => :d)"
        ),
        {"u": user_id, "d": days},
    ).scalar_one()
    return count


def mark_read(conn: Connection, user_id: uuid.UUID, ids: list[uuid.UUID] | None) -> int:
    """Only the owner's unread rows; another person's ids are ignored (existence is not revealed)."""
    if ids is None:
        sql = text("UPDATE app.notifications SET read_at = now() WHERE user_id = :u AND read_at IS NULL")
        return conn.execute(sql, {"u": user_id}).rowcount
    sql = text(
        "UPDATE app.notifications SET read_at = now() WHERE user_id = :u AND read_at IS NULL AND id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    return conn.execute(sql, {"u": user_id, "ids": ids}).rowcount
