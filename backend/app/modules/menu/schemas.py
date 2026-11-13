"""Menu API contract (DDR-11, DDR-31, DDR-48, DDR-107)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.menu.domain import Publication


class CustomerMenuItemOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price_paise: int | None
    is_veg: bool | None
    spice_level: str | None
    prep_time_minutes: int | None
    image_url: str | None
    image_is_placeholder: bool
    category: str | None
    # Test items are labelled "Test" in every UI (plan §5.2).
    is_test_fixture: bool
    # Set only with owner approval (DDR-110 (1)); none are flagged in the POC.
    is_bestseller: bool


class ManagedMenuItemOut(CustomerMenuItemOut):
    tax_classification: str | None
    publication_status: Publication
    kitchen_id: uuid.UUID
    region_id: uuid.UUID
    recipe_id: uuid.UUID
    has_active_recipe: bool
    updated_at: datetime


class MenuTransitionIn(BaseModel):
    action: Literal["mark_ready", "publish"]
    reason: str | None = Field(default=None, max_length=500)


class DishDetailOut(CustomerMenuItemOut):
    # Ingredient names of the ACTIVE recipe version (CU-08); quantities stay internal.
    ingredients: list[str]
    # No customization model exists yet (DDR-110 (10)); the UI states that none is configured.
    customizations: list[str]


class MenuFiltersOut(BaseModel):
    # Taken from published dishes; no option is invented (DDR-110 (2)).
    categories: list[str]
    spice_levels: list[str]
    min_price_paise: int | None
    max_price_paise: int | None
    has_bestsellers: bool
    has_veg: bool
    has_non_veg: bool
