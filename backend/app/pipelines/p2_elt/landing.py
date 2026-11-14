"""P2 landing: `app.outbox` → `raw.events`, continuously (DATA_PIPELINE §2.2, §10, §13; ADR-004; DDR-116 (6)).

Runs as the `p2_elt` role in its own worker thread, so a dbt run never blocks it. Each batch is one
transaction: claim unpublished rows (oldest first, `SKIP LOCKED`), insert them into `raw.events` with
`ON CONFLICT (event_id) DO NOTHING`, mark them published. A crash rolls the whole batch back, so nothing is
lost and nothing lands twice. Rows that fail the envelope check land with `parse_status = rejected` and the
reason; raw is append-only, so they are kept and shown, never deleted.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, text

from app.shared.events import EVENT_TYPES, EVENT_VERSION

BATCH_MAX = 500
POLL_SECONDS = 2.0  # DDR-105 poll interval; DDR-116 (6)
# Every §6.3 event is about an order (DATA_PIPELINE §6.3). GPS points are never events (DDR-78).
AGGREGATE_TYPE = "order"

COLUMNS = (
    "event_id, event_type, event_version, occurred_at, aggregate_type, aggregate_id, region_id, "
    "kitchen_id, correlation_id, idempotency_key, data, is_test_fixture"
)


@dataclass(frozen=True)
class OutboxRow:
    id: int
    event_id: uuid.UUID
    event_type: str
    event_version: int
    occurred_at: datetime
    aggregate_type: str
    aggregate_id: uuid.UUID
    region_id: uuid.UUID | None
    kitchen_id: uuid.UUID | None
    correlation_id: str | None
    idempotency_key: str
    data: Any
    is_test_fixture: bool


@dataclass(frozen=True)
class Landed:
    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0


def problem(row: OutboxRow) -> str | None:
    """Why an event is rejected, or None. Pure: unit-tested without a database."""
    if row.event_type not in EVENT_TYPES:
        return f"unknown event type {row.event_type!r}"
    if row.event_version != EVENT_VERSION:
        return f"unsupported event version {row.event_version}"
    if row.aggregate_type != AGGREGATE_TYPE:
        return f"aggregate type must be {AGGREGATE_TYPE!r}"
    if not isinstance(row.data, dict):
        return "data must be a JSON object"
    if row.data.get("order_id") not in (None, str(row.aggregate_id)):
        return "data.order_id differs from the aggregate"
    return None


def land_batch(conn: Connection, limit: int = BATCH_MAX) -> Landed:
    """One batch in the caller's transaction (the caller commits; an exception rolls everything back)."""
    rows = [
        OutboxRow(*r)
        for r in conn.execute(
            text(
                f"SELECT id, {COLUMNS} FROM app.outbox WHERE published_at IS NULL "  # noqa: S608 - fixed SQL
                "ORDER BY id LIMIT :n FOR UPDATE SKIP LOCKED"
            ),
            {"n": limit},
        )
    ]
    if not rows:
        return Landed()
    accepted = rejected = inserted = 0
    for r in rows:
        reason = problem(r)
        inserted += conn.execute(
            text(
                f"INSERT INTO raw.events ({COLUMNS}, parse_status, parse_error) VALUES "  # noqa: S608 - fixed SQL
                "(:event_id, :event_type, :event_version, :occurred_at, :aggregate_type, :aggregate_id, "
                ":region_id, :kitchen_id, :correlation_id, :idempotency_key, CAST(:data AS jsonb), "
                ":is_test_fixture, :status, :error) ON CONFLICT (event_id) DO NOTHING"
            ),
            {
                **{k: getattr(r, k) for k in COLUMNS.replace(" ", "").split(",") if k != "data"},
                "data": json.dumps(r.data, default=str),
                "status": "rejected" if reason else "accepted",
                "error": reason,
            },
        ).rowcount
        if reason:
            rejected += 1
        else:
            accepted += 1
    conn.execute(
        text(
            "UPDATE app.outbox SET published_at = now(), attempts = attempts + 1, last_error = NULL "
            "WHERE id = ANY(:ids)"
        ),
        {"ids": [r.id for r in rows]},
    )
    return Landed(accepted, rejected, duplicates=len(rows) - inserted)
