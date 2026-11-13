"""Customer address and serviceability contract (CU-02–CU-04; DDR-110)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

# India bounds keep obviously wrong coordinates out; the serviceability rule decides the rest.
LAT = Field(ge=6.0, le=37.5)
LNG = Field(ge=68.0, le=97.5)


class ServiceabilityOut(BaseModel):
    serviceable: bool
    straight_line_km: Decimal
    straight_line_max_km: Decimal
    straight_line_ok: bool
    road_km: Decimal
    road_max_km: Decimal
    road_ok: bool
    # True while the road distance is the labelled stub (DDR-55): show "road distance: estimated".
    road_km_estimated: bool
    kitchen_name: str
    kitchen_location_is_synthetic: bool


class AddressIn(BaseModel):
    label: str = Field(min_length=1, max_length=40, examples=["Home"])
    address_line: str = Field(min_length=3, max_length=300)
    lat: float = LAT
    lng: float = LNG
    make_default: bool = False


class AddressOut(BaseModel):
    id: uuid.UUID
    label: str
    address_line: str
    lat: float
    lng: float
    is_default: bool
    created_at: datetime
    serviceability: ServiceabilityOut


def serviceability_out(kitchen: Any, result: Any) -> ServiceabilityOut:
    """From the customers service's kitchen row and Serviceability result."""
    return ServiceabilityOut(
        **result.__dict__,
        kitchen_name=kitchen.name,
        kitchen_location_is_synthetic=kitchen.location_is_synthetic,
    )
