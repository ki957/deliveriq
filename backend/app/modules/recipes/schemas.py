"""Recipe workflow API contract (DDR-10, DDR-54, DDR-103, DDR-107)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.recipes.domain import RecipeStatus, SignoffType

Action = Literal["submit", "return", "validate", "reject", "activate"]


class RecipeVersionOut(BaseModel):
    id: uuid.UUID
    recipe_id: uuid.UUID
    name: str
    source_menu_id: str | None
    kitchen_id: uuid.UUID
    version: int
    status: RecipeStatus
    is_test_fixture: bool
    quarantine_reason: str | None
    open_review_items: int
    candidate_category: str | None
    updated_at: datetime


class IngredientLineOut(BaseModel):
    line_no: int
    ingredient_id: uuid.UUID
    name: str
    quantity: Decimal
    unit: str
    source_line: int | None
    original_text: str | None


class SignoffOut(BaseModel):
    signoff_type: SignoffType
    signed_by: uuid.UUID
    signed_at: datetime
    note: str | None


class ReviewItemOut(BaseModel):
    id: uuid.UUID
    recipe_version_id: uuid.UUID
    recipe_name: str
    source_card_id: str | None
    reason_code: str
    subject: str
    detail: str
    source_ref: str
    source_line: int | None
    status: Literal["OPEN", "ACKNOWLEDGED"]
    acknowledged_by: uuid.UUID | None
    acknowledged_at: datetime | None
    note: str | None


class LineageOut(BaseModel):
    source_path: str | None
    source_sha256: str | None
    source_card_id: str | None
    source_line_start: int | None
    source_line_end: int | None
    source_page_ref: int | None


class RecipeVersionDetailOut(RecipeVersionOut):
    prep_type: str | None
    portion: str | None
    method: str | None
    quality: str | None
    inventory_rule: str | None
    validation_text: str | None
    lineage: LineageOut
    ingredients: list[IngredientLineOut]
    signoffs: list[SignoffOut]
    missing_signoffs: list[SignoffType]
    review_items: list[ReviewItemOut]


class TransitionIn(BaseModel):
    action: Action
    # Every recipe transition records a reason (DDR-10; status_transitions.reason_required).
    reason: str = Field(min_length=3, max_length=500)


class SignoffIn(BaseModel):
    signoff_type: SignoffType
    note: str | None = Field(default=None, max_length=500)


class AcknowledgeIn(BaseModel):
    note: str = Field(min_length=3, max_length=1000)
