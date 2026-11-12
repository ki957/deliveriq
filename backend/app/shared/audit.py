"""Append-only audit events (PL-12; `audit.events`). Parameterised; the caller owns the transaction."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import Connection, text


def write_event(
    conn: Connection,
    *,
    action: str,
    actor_user_id: uuid.UUID | None,
    actor_role: str,
    target_type: str,
    target_id: str,
    outcome: str = "SUCCESS",
    region_id: uuid.UUID | None = None,
    kitchen_id: uuid.UUID | None = None,
    reason: str | None = None,
    correlation_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO audit.events (actor_user_id, actor_role, action, target_type, target_id, region_id, "
            "kitchen_id, outcome, reason, correlation_id, before_summary, after_summary) "
            "VALUES (:actor, :role, "
            ":action, :ttype, :tid, :reg, :kit, :outcome, :reason, :cid, CAST(:before AS jsonb), "
            "CAST(:after AS jsonb))"
        ),
        {
            "actor": actor_user_id,
            "role": actor_role,
            "action": action,
            "ttype": target_type,
            "tid": target_id,
            "reg": region_id,
            "kit": kitchen_id,
            "outcome": outcome,
            "reason": reason,
            "cid": correlation_id,
            "before": None if before is None else json.dumps(before, default=str),
            "after": None if after is None else json.dumps(after, default=str),
        },
    )
