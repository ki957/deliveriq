"""Management API contract (#10; DDR-114). Money is integer paise; no secrets or OTPs ever appear here."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

StaffRole = Literal["KITCHEN_STAFF", "KITCHEN_MANAGER", "DELIVERY_AGENT", "REGIONAL_MANAGER"]


class ManagedIntakeOut(BaseModel):
    mode: str
    capacity: int | None
    active_orders: int
    accepting: bool
    refusal: str | None


class KitchenStatusOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    region_id: uuid.UUID
    region_name: str
    mode: str
    # None when a capacity value is not configured for this kitchen (never guessed).
    intake: ManagedIntakeOut | None


class OverviewOut(BaseModel):
    orders_by_status: dict[str, int]
    overdue_incoming: int
    availability_requests: int
    failure_requests: int
    delivery_exceptions: int
    online_agents: int
    active_deliveries: int
    kitchens: list[KitchenStatusOut]
    # KPI formulas are not defined (DDR-44); revenue and trends come with Task 13.
    kpis_available: Literal[False] = False


class RegionOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class OrderRowOut(BaseModel):
    id: uuid.UUID
    placed_at: datetime
    fulfilment_status: str
    status_label: str
    is_test_fixture: bool
    kitchen_name: str
    payable_paise: int | None
    payment_method: str | None
    payment_status: str | None
    agent_name: str | None
    assignment_status: str | None
    delivery_exception_open: bool


class OrderPageOut(BaseModel):
    rows: list[OrderRowOut]
    total: int
    page: int
    page_size: int


class TimelineOut(BaseModel):
    machine: str
    from_status: str | None
    to_status: str
    actor_role: str
    actor_name: str | None
    reason: str | None
    changed_at: datetime


class ManagedItemOut(BaseModel):
    name: str
    quantity: int


class OrderDetailOut(BaseModel):
    order: OrderRowOut
    items: list[ManagedItemOut]
    timeline: list[TimelineOut]


class DeliveryOut(BaseModel):
    order_id: uuid.UUID
    assignment_id: uuid.UUID
    assignment_status: str
    fulfilment_status: str
    is_test_fixture: bool
    agent_id: uuid.UUID
    agent_name: str
    delivery_address: str | None
    delivery_exception_open: bool
    lat: float | None
    lng: float | None
    recorded_at: datetime | None
    simulated: bool | None


class RefundOut(BaseModel):
    order_id: uuid.UUID
    is_test_fixture: bool
    amount_paise: int | None
    method: str
    status: str
    reason: str | None
    actor_role: str | None
    actor_name: str | None
    changed_at: datetime | None
    pending_decision: bool


class RefundsOut(BaseModel):
    rows: list[RefundOut]
    # DDR-44 open: no threshold is configured, so exceptional refunds and overrides are disabled.
    exceptional_refunds_enabled: Literal[False] = False
    disabled_reason: str = "Disabled: no threshold configured (DDR-44)"


class ManagedStockOut(BaseModel):
    ingredient_id: uuid.UUID
    name: str
    unit: str
    on_hand: Decimal
    reserved: Decimal
    available: Decimal
    low_stock_threshold: Decimal | None
    is_test_fixture: bool


class MovementOut(BaseModel):
    created_at: datetime
    ingredient_name: str
    unit: str
    delta: Decimal
    kind: str
    reason: str | None
    actor_role: str
    order_id: uuid.UUID | None
    is_test_fixture: bool


class InventoryOut(BaseModel):
    kitchen_id: uuid.UUID
    stock: list[ManagedStockOut]
    movements: list[MovementOut]


class AuditOut(BaseModel):
    occurred_at: datetime
    actor_role: str
    actor_name: str | None
    action: str
    target_type: str
    target_id: str | None
    region_id: uuid.UUID | None
    outcome: str
    reason: str | None
    correlation_id: str | None
    before_summary: Any
    after_summary: Any


class AuditPageOut(BaseModel):
    rows: list[AuditOut]
    total: int
    page: int
    page_size: int


class StaffOut(BaseModel):
    assignment_id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    mobile_masked: str
    user_status: str
    role: str
    region_id: uuid.UUID | None
    kitchen_id: uuid.UUID | None
    granted_at: datetime


class StaffIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    mobile: str = Field(min_length=10, max_length=20)
    role: StaffRole
    region_id: uuid.UUID
    kitchen_id: uuid.UUID | None = None
    reason: str = Field(min_length=1, max_length=500)


class StaffReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class StatusIn(BaseModel):
    active: bool
    reason: str = Field(min_length=1, max_length=500)
