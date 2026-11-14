"""Management reports contract (DDR-117). Money is integer paise; durations are seconds; ratios 0–1."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class KpiOut(BaseModel):
    key: str
    label: str
    unit: Literal["count", "paise", "seconds", "ratio"]
    # None when the denominator is 0 (no value is invented, MG-08).
    value: float | None
    previous: float | None
    formula: str
    source: str
    definition_status: str
    denominator_note: str | None


class DailyOut(BaseModel):
    day: date
    orders_placed: int
    orders_delivered: int
    payable_paise: int
    discount_paise: int


class IngredientOut(BaseModel):
    ingredient_id: uuid.UUID
    name: str
    unit: str
    consumed_quantity: Decimal


class KitchenRefOut(BaseModel):
    id: uuid.UUID
    name: str


class NotAvailableOut(BaseModel):
    area: str
    reason: str


class ReportOut(BaseModel):
    dataset: Literal["analytics", "analytics_synthetic"]
    dataset_label: str
    available: bool
    unavailable_reason: str | None
    fresh_as_of: datetime | None
    freshness_warn_hours: int
    # Freshness older than the warning threshold (labelled test default, DDR-117 (11)).
    stale: bool
    date_from: date
    date_to: date
    previous_from: date
    previous_to: date
    kitchens: list[KitchenRefOut]
    kitchen_id: uuid.UUID | None
    kpis: list[KpiOut]
    daily: list[DailyOut]
    ingredients: list[IngredientOut]
    not_available: list[NotAvailableOut]
    # DDR-117 (12), class A: always false; KPIs are labelled, never business truth.
    kpis_are_business_truth: Literal[False]
