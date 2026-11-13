"""Outbox writer guards (DATA_PIPELINE_DESIGN §6.3; DDR-109)."""

from __future__ import annotations

import uuid

import pytest

from app.shared import events

pytestmark = pytest.mark.unit


def test_event_types_are_exactly_the_approved_list() -> None:
    assert len(events.EVENT_TYPES) == 15
    assert {"order.placed", "payment.succeeded", "payment.failed", "delivery.picked_up"} <= events.EVENT_TYPES
    assert not any(t.startswith("refund") or "cod" in t for t in events.EVENT_TYPES)


def test_unknown_event_types_are_refused_before_any_write() -> None:
    with pytest.raises(events.UnknownEventType):
        events.emit(
            None,  # type: ignore[arg-type]  # refused before the connection is used
            event_type="payment.refunded",
            aggregate_type="order",
            aggregate_id=uuid.uuid4(),
            is_test_fixture=True,
            data={},
        )
