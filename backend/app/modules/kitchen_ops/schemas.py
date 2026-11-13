"""Kitchen settings API contract (KI-12–KI-15; DDR-42, DDR-111)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.modules.kitchen_ops.domain import CAPACITY_MAX, CAPACITY_MIN, REASON_MAX, KitchenMode


class ConfiguredValueOut(BaseModel):
    value: int
    # True while the value is a labelled test default (DDR-42 open); the UI says so.
    is_test_default: bool


class IntakeOut(BaseModel):
    mode: KitchenMode
    capacity: int | None
    active_orders: int
    accepting: bool
    refusal: str | None


class KitchenSettingsOut(BaseModel):
    kitchen_id: uuid.UUID
    kitchen_name: str
    mode: KitchenMode
    normal_capacity: ConfiguredValueOut
    busy_capacity: ConfiguredValueOut
    acceptance_timeout_minutes: ConfiguredValueOut | None
    intake: IntakeOut
    can_change: bool


class KitchenSettingsIn(BaseModel):
    mode: KitchenMode
    normal_capacity: int = Field(ge=CAPACITY_MIN, le=CAPACITY_MAX)
    busy_capacity: int = Field(ge=CAPACITY_MIN, le=CAPACITY_MAX)
    reason: str = Field(min_length=1, max_length=REASON_MAX)
