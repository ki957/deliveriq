"""SQL for delivery assignments. Parameterised; callers own the transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Connection, text


@dataclass(frozen=True)
class LiveAssignment:
    order_id: uuid.UUID
    assignment_id: uuid.UUID
    status: str
    agent_user_id: uuid.UUID
    agent_name: str


_ELIGIBLE = """
    SELECT u.id FROM app.users u
     WHERE u.status = 'ACTIVE'
       AND EXISTS (SELECT 1 FROM app.role_assignments r
                    WHERE r.user_id = u.id AND r.role = 'DELIVERY_AGENT' AND r.region_id = :reg
                      AND r.revoked_at IS NULL)
       AND NOT EXISTS (SELECT 1 FROM app.delivery_assignments a
                        WHERE a.agent_user_id = u.id
                          AND a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED'))
     ORDER BY (SELECT max(a.offered_at) FROM app.delivery_assignments a WHERE a.agent_user_id = u.id)
              NULLS FIRST, u.id
     LIMIT 1 FOR UPDATE OF u SKIP LOCKED
"""
_LIVE = """
    SELECT a.order_id, a.id, a.status, a.agent_user_id, u.display_name
      FROM app.delivery_assignments a JOIN app.users u ON u.id = a.agent_user_id
     WHERE a.order_id = ANY(:ids) AND a.status IN ('OFFERED', 'ACCEPTED', 'FAILURE_REQUESTED')
"""


def eligible_agent(conn: Connection, region_id: uuid.UUID) -> uuid.UUID | None:
    """An active agent in the region with no open offer or live delivery, least recently offered first.

    Every active agent counts as available until online/offline exists (Task 9; DDR-111 (6)).
    Rows another acceptance is offering right now are skipped, not waited for.
    """
    row = conn.execute(text(_ELIGIBLE), {"reg": region_id}).first()
    return row[0] if row else None


def insert_offer(conn: Connection, order_id: uuid.UUID, agent_user_id: uuid.UUID) -> uuid.UUID:
    assignment_id: uuid.UUID = conn.execute(
        text(
            "INSERT INTO app.delivery_assignments (order_id, agent_user_id, status) "
            "VALUES (:o, :a, 'OFFERED') RETURNING id"
        ),
        {"o": order_id, "a": agent_user_id},
    ).scalar_one()
    return assignment_id


def live(
    conn: Connection, order_ids: list[uuid.UUID], *, lock: bool = False
) -> dict[uuid.UUID, LiveAssignment]:
    sql = _LIVE + (" FOR UPDATE OF a" if lock else "")
    rows = conn.execute(text(sql), {"ids": order_ids}).all()
    return {r[0]: LiveAssignment(*r) for r in rows}


def set_status(conn: Connection, assignment_id: uuid.UUID, status: str) -> None:
    conn.execute(
        text(
            "UPDATE app.delivery_assignments SET status = :s, "
            "responded_at = coalesce(responded_at, now()) WHERE id = :id"
        ),
        {"s": status, "id": assignment_id},
    )
