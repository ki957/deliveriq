"""Orders API contract (Matrix §7; DDR-07, DDR-38, DDR-109). Money is integer paise."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.customers.schemas import ServiceabilityOut
from app.modules.orders.domain import REJECT_REASON_MAX, SPECIAL_INSTRUCTIONS_MAX, Fulfilment, ItemPrep
from app.modules.payments.domain import PaymentMethod, PaymentStatus, SimOutcome

# Input-size guards against oversized requests; not business limits (none are defined in the sources).
MAX_LINES = 50
MAX_QUANTITY = 99


class OrderLineIn(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(ge=1, le=MAX_QUANTITY)
    # The unit price the customer saw and accepted; a different charge is refused with 409 (DDR-110).
    unit_price_paise: int = Field(gt=0)


class OrderCreateIn(BaseModel):
    lines: list[OrderLineIn] = Field(min_length=1, max_length=MAX_LINES)
    payment_method: PaymentMethod
    special_instructions: str | None = Field(default=None, max_length=SPECIAL_INSTRUCTIONS_MAX)
    # A saved address of the customer; serviceability is revalidated before placement (CU-03).
    address_id: uuid.UUID
    coupon_code: str | None = Field(default=None, max_length=20)

    @field_validator("lines")
    @classmethod
    def _one_line_per_dish(cls, lines: list[OrderLineIn]) -> list[OrderLineIn]:
        if len({line.menu_item_id for line in lines}) != len(lines):
            raise ValueError("each dish may appear once; use quantity")
        return lines

    @field_validator("special_instructions")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class SimulateIn(BaseModel):
    # Simulator scenarios (#15 §9). No real payment is made (DDR-109).
    outcome: SimOutcome


class CancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class OrderItemOut(BaseModel):
    menu_item_id: uuid.UUID
    item_name: str | None
    unit_price_paise: int | None
    quantity: int
    prep_status: str


class PaymentOut(BaseModel):
    method: PaymentMethod
    status: PaymentStatus
    amount_paise: int | None
    sim_reference: str | None
    # Always true: the POC never calls a real gateway (Phase 4 §13).
    simulated: Literal[True] = True


class LiveLocationOut(BaseModel):
    lat: float
    lng: float
    recorded_at: datetime
    # Simulated GPS is labelled in every UI (DL-G2).
    simulated: bool


class OrderOut(BaseModel):
    id: uuid.UUID
    fulfilment_status: Fulfilment
    # Customer label from the canonical display mapping (Matrix §7.3) and the DDR-16 indicator.
    status_label: str
    agent_assigned: bool
    is_test_fixture: bool
    special_instructions: str | None
    food_subtotal_paise: int | None
    delivery_fee_paise: int | None
    discount_paise: int
    payable_paise: int | None
    delivery_address: str | None
    road_km_estimated: bool | None
    placed_at: datetime
    items: list[OrderItemOut]
    payment: PaymentOut | None
    # Customer's own order, while Out for delivery only (DDR-113 (6), (8)).
    delivery_code: str | None = None
    live_location: LiveLocationOut | None = None


# ---------------------------------------------------------------- cart and quote (DDR-110)
class CartQuantityIn(BaseModel):
    quantity: int = Field(ge=1, le=MAX_QUANTITY)


class CartLineOut(BaseModel):
    menu_item_id: uuid.UUID
    name: str
    quantity: int
    is_test_fixture: bool
    available: bool
    # Price recorded when the line was added; protected until `protected_until` (CU-13).
    cart_price_paise: int
    protected_until: datetime
    # What checkout charges now (None while unavailable).
    charge_price_paise: int | None
    price_changed: bool


class BillOut(BaseModel):
    food_subtotal_paise: int
    minimum_food_subtotal_paise: int
    minimum_met: bool
    delivery_fee_paise: int
    discount_paise: int
    payable_paise: int
    tax_note: str


class CartOut(BaseModel):
    lines: list[CartLineOut]
    bill: BillOut
    coupon_code: str | None
    coupon_error: str | None
    serviceability: ServiceabilityOut | None
    address_error: str | None
    # Reasons checkout is not possible yet; empty when the order can be placed.
    blockers: list[str]


# ---------------------------------------------------------------- kitchen (Task 8; KI-01–KI-07, DDR-111)
class KitchenItemOut(BaseModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID
    item_name: str | None
    quantity: int
    prep_status: ItemPrep
    # Pinned at acceptance (KI-18); a later recipe version never changes it.
    recipe_version_id: uuid.UUID | None
    recipe_version: int | None


class KitchenAssignmentOut(BaseModel):
    # OFFERED until the agent responds (Task 9); ACCEPTED shows the agent on the card (Matrix §7.3).
    status: str
    agent_name: str


class KitchenOrderOut(BaseModel):
    """What the line needs (KI-07). No customer name, phone or address is exposed to the kitchen."""

    id: uuid.UUID
    fulfilment_status: Fulfilment
    status_label: str
    is_test_fixture: bool
    special_instructions: str | None
    payment_method: PaymentMethod | None
    placed_at: datetime
    queued_at: datetime | None
    accepted_at: datetime | None
    overdue: bool
    items: list[KitchenItemOut]
    assignment: KitchenAssignmentOut | None


class KitchenIntakeOut(BaseModel):
    mode: str
    capacity: int | None
    active_orders: int
    accepting: bool
    refusal: str | None


class KitchenQueueOut(BaseModel):
    kitchen_id: uuid.UUID
    kitchen_name: str
    intake: KitchenIntakeOut
    # DDR-42 test default until approved; drives the "Overdue" warning only.
    acceptance_timeout_minutes: int | None
    incoming: list[KitchenOrderOut]
    # FIFO by acceptance time (KI-03).
    held: list[KitchenOrderOut]
    can_process: bool
    can_reject_accepted: bool


class KitchenRejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=REJECT_REASON_MAX)


class KitchenItemStatusIn(BaseModel):
    status: Literal[ItemPrep.PREPARING, ItemPrep.PREPARED]
