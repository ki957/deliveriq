"""Orders API contract (Matrix §7; DDR-07, DDR-38, DDR-109). Money is integer paise."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.orders.domain import SPECIAL_INSTRUCTIONS_MAX, Fulfilment
from app.modules.payments.domain import PaymentMethod, PaymentStatus, SimOutcome

# Input-size guards against oversized requests; not business limits (none are defined in the sources).
MAX_LINES = 50
MAX_QUANTITY = 99


class OrderLineIn(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(ge=1, le=MAX_QUANTITY)


class OrderCreateIn(BaseModel):
    lines: list[OrderLineIn] = Field(min_length=1, max_length=MAX_LINES)
    payment_method: PaymentMethod
    special_instructions: str | None = Field(default=None, max_length=SPECIAL_INSTRUCTIONS_MAX)

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
    payable_paise: int | None
    placed_at: datetime
    items: list[OrderItemOut]
    payment: PaymentOut | None
