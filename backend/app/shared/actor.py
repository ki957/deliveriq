"""Transaction-local actor context for the database status-transition engine (migration 0001).

Every status change must carry `app.actor_role`, `app.actor_user_id` (except SYSTEM) and, where the
transition requires one, `app.reason`. The settings are local to the caller's transaction.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Connection, text


def set_actor(
    conn: Connection,
    *,
    role: str,
    user_id: uuid.UUID | None,
    reason: str | None,
    correlation_id: str | None,
) -> None:
    conn.execute(
        text(
            "SELECT set_config('app.actor_role', :role, true), set_config('app.actor_user_id', :uid, true), "
            "set_config('app.reason', :reason, true), set_config('app.correlation_id', :cid, true)"
        ),
        {
            "role": role,
            "uid": str(user_id) if user_id else "",
            "reason": reason or "",
            "cid": correlation_id or "",
        },
    )
