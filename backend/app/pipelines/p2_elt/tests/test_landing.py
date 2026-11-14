"""The P2 envelope check (DATA_PIPELINE §6.2, §10; DDR-116 (6))."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

from app.pipelines.p2_elt.landing import OutboxRow, problem

ORDER = uuid.uuid4()
GOOD = OutboxRow(
    id=1,
    event_id=uuid.uuid4(),
    event_type="order.placed",
    event_version=1,
    occurred_at=datetime.now(UTC),
    aggregate_type="order",
    aggregate_id=ORDER,
    region_id=None,
    kitchen_id=None,
    correlation_id=None,
    idempotency_key=f"order.placed:{ORDER}",
    data={"order_id": str(ORDER), "customer_key": "ab" * 32},
    is_test_fixture=True,
)


def test_a_valid_event_is_accepted() -> None:
    assert problem(GOOD) is None
    assert problem(replace(GOOD, data={})) is None  # order_id is optional; the aggregate carries it


def test_malformed_events_are_rejected_with_a_reason() -> None:
    cases = {
        "unknown event type 'delivery.location'": replace(GOOD, event_type="delivery.location"),
        "unsupported event version 2": replace(GOOD, event_version=2),
        "aggregate type must be 'order'": replace(GOOD, aggregate_type="customer"),
        "data must be a JSON object": replace(GOOD, data=[1, 2]),
        "data.order_id differs from the aggregate": replace(GOOD, data={"order_id": str(uuid.uuid4())}),
    }
    for reason, row in cases.items():
        assert problem(row) == reason
