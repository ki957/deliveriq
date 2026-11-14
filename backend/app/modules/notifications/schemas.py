"""Notifications API contract (DDR-115 (10)). Ids and kinds only; the UI words each kind."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NotificationKind = Literal[
    "order.accepted",
    "order.preparing",
    "order.ready_for_pickup",
    "order.out_for_delivery",
    "order.delivered",
    "order.cancelled",
    "order.rejected",
    "order.delivery_failed",
    "order.agent_assigned",
    "delivery.offered",
    "delivery.withdrawn",
    "delivery.failure_returned",
    "delivery.failure_approved",
    "stock.low",
]


class NotificationOut(BaseModel):
    id: uuid.UUID
    kind: NotificationKind
    order_id: uuid.UUID | None
    ingredient_name: str | None
    is_test_fixture: bool
    created_at: datetime
    read_at: datetime | None


class InboxOut(BaseModel):
    rows: list[NotificationOut]
    unread: int
    history_days: int
    # DDR-40: no SMS provider in the POC; in-app only, stated on screen. No browser push (DDR-115 (10)).
    sms: Literal["Not configured (DDR-40)"] = "Not configured (DDR-40)"


class MarkReadIn(BaseModel):
    # None = mark every unread notification read.
    ids: list[uuid.UUID] | None = Field(default=None, max_length=100)
