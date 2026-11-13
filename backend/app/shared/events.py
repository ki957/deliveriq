"""Transactional outbox writer (ADR-004; DATA_PIPELINE_DESIGN §6.2–6.3; Phase 2 §10.5).

`emit` writes the event in the caller's transaction, so the business change and its event commit
together or not at all. The worker relays outbox rows to `raw.events` (Task 12); delivery is
at-least-once, so consumers deduplicate by `event_id`. Payloads never contain PII, OTPs or secrets.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import Connection, text

EVENT_VERSION = 1

# DATA_PIPELINE_DESIGN §6.3. Types outside this list need an approved addition first (DDR-109).
EVENT_TYPES = frozenset(
    {
        "order.placed",
        "order.accepted",
        "order.rejected",
        "order.cancelled",
        "order.preparing",
        "order.ready_for_pickup",
        "payment.succeeded",
        "payment.failed",
        "inventory.reserved",
        "inventory.released",
        "inventory.consumed",
        "delivery.assigned",
        "delivery.picked_up",
        "delivery.completed",
        "delivery.failed",
    }
)


class UnknownEventType(ValueError):
    pass


def emit(
    conn: Connection,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    is_test_fixture: bool,
    data: dict[str, Any],
    region_id: uuid.UUID | None = None,
    kitchen_id: uuid.UUID | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> uuid.UUID:
    """Write one event in the caller's transaction. One event per type and aggregate by default."""
    if event_type not in EVENT_TYPES:
        raise UnknownEventType(event_type)
    event_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO app.outbox (event_id, event_type, event_version, occurred_at, aggregate_type, "
            "aggregate_id, region_id, kitchen_id, correlation_id, idempotency_key, data, is_test_fixture) "
            "VALUES (:id, :type, :ver, now(), :atype, :aid, :reg, :kit, :cid, :key, "
            "CAST(:data AS jsonb), :fx)"
        ),
        {
            "id": event_id,
            "type": event_type,
            "ver": EVENT_VERSION,
            "atype": aggregate_type,
            "aid": aggregate_id,
            "reg": region_id,
            "kit": kitchen_id,
            "cid": correlation_id,
            "key": idempotency_key or f"{event_type}:{aggregate_id}",
            "data": json.dumps(data, default=str, sort_keys=True),
            "fx": is_test_fixture,
        },
    )
    return event_id
