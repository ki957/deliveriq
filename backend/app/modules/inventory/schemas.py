"""Inventory API contract (#4 §7; KI-21–KI-23; DDR-37, DDR-111 (8), (9))."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.inventory.domain import QUANTITY_MAX, REASON_MAX


class StockOut(BaseModel):
    ingredient_id: uuid.UUID
    name: str
    unit: str
    on_hand: Decimal
    reserved: Decimal
    available: Decimal
    low_stock_threshold: Decimal | None
    is_low: bool
    # Opening stock is test-only (DDR-37): the UI labels it "Test stock".
    is_test_fixture: bool
    used_in: list[str]
    updated_at: datetime


class AdjustIn(BaseModel):
    # Signed, in the ingredient's own unit; never below the reserved quantity.
    delta: Decimal = Field(ge=-QUANTITY_MAX, le=QUANTITY_MAX, max_digits=14, decimal_places=3)
    reason: str = Field(min_length=1, max_length=REASON_MAX)


class ThresholdIn(BaseModel):
    # null clears the threshold (no alert).
    low_stock_threshold: Decimal | None = Field(ge=0, le=QUANTITY_MAX, max_digits=14, decimal_places=3)
    reason: str = Field(min_length=1, max_length=REASON_MAX)
