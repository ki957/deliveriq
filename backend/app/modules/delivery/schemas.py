"""Delivery API contract (#7 §3–§9; DL-01–DL-17; DDR-113). No model carries the full customer number
except the audited reveal."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.delivery.domain import GPS_BATCH_MAX, REASON_MAX


class Place(BaseModel):
    lat: float
    lng: float


class WorkItemOut(BaseModel):
    name: str
    quantity: int


class WorkOrderOut(BaseModel):
    order_id: uuid.UUID
    items: list[WorkItemOut]
    fulfilment_status: str
    status_label: str
    is_test_fixture: bool
    special_instructions: str | None
    # Shown after the agent accepts (DL-08); an open offer shows the kitchen only.
    delivery_address: str | None
    destination: Place | None
    kitchen_name: str
    kitchen: Place
    kitchen_location_is_synthetic: bool
    customer_phone_masked: str
    payment_method: str | None
    payment_status: str | None
    payable_paise: int | None
    customer_unavailable_since: datetime | None
    delivery_exception_open: bool
    code_attempts_left: int | None


class AssignmentOut(BaseModel):
    id: uuid.UUID
    status: str
    offered_at: datetime
    offer_seconds_left: int | None


class MyWorkOut(BaseModel):
    availability: Literal["ONLINE", "OFFLINE"]
    availability_changed_at: datetime | None
    assignment: AssignmentOut | None
    order: WorkOrderOut | None
    customer_unavailable_wait_minutes: int
    gps_interval_seconds: tuple[int, int]
    gps_stale_seconds: int
    # Until real road routing (DDR-55 optional OSRM), the route is a labelled straight line.
    route_is_estimated: Literal[True] = True


class AvailabilityIn(BaseModel):
    online: bool


class RespondIn(BaseModel):
    accept: bool
    reason: str | None = Field(default=None, max_length=REASON_MAX)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=REASON_MAX)


class OptionalReasonIn(BaseModel):
    reason: str | None = Field(default=None, max_length=REASON_MAX)


class CodeIn(BaseModel):
    code: str = Field(pattern=r"^\s*\d{6}\s*$")


class FailureIn(BaseModel):
    refused: bool
    reason: str = Field(min_length=1, max_length=REASON_MAX)


class CodIn(BaseModel):
    collected: bool
    reason: str | None = Field(default=None, max_length=REASON_MAX)


class PointIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: Decimal | None = Field(default=None, ge=0, le=100000, max_digits=8, decimal_places=2)
    recorded_at: datetime
    source: Literal["REAL", "SIMULATED"]


class PointsIn(BaseModel):
    points: list[PointIn] = Field(min_length=1, max_length=GPS_BATCH_MAX)


class IngestOut(BaseModel):
    accepted: int
    refused: dict[str, int]


class PhoneOut(BaseModel):
    phone: str


class UnavailableOut(BaseModel):
    since: datetime
    wait_minutes: int


class HistoryOut(BaseModel):
    order_id: uuid.UUID
    assignment_status: str
    fulfilment_status: str
    is_test_fixture: bool
    offered_at: datetime
    picked_up_at: datetime | None
    delivered_at: datetime | None
    duration_minutes: int | None


class NameIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


class NameOut(BaseModel):
    display_name: str


class AgentOut(BaseModel):
    id: uuid.UUID
    name: str
    availability: Literal["ONLINE", "OFFLINE"]
    availability_changed_at: datetime | None
    live_status: str | None
    live_order_id: uuid.UUID | None


class AssignIn(BaseModel):
    agent_user_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=REASON_MAX)


class DecisionIn(BaseModel):
    approve: bool
    reason: str = Field(min_length=1, max_length=REASON_MAX)


class LiveAssignmentOut(BaseModel):
    order_id: uuid.UUID
    assignment_id: uuid.UUID
    status: str
    agent_name: str
