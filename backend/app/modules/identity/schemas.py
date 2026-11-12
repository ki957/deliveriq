"""Identity API contract (request and response models)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.permissions import Portal, Role
from app.modules.identity import domain as d


class OtpRequestIn(BaseModel):
    mobile: str = Field(min_length=10, max_length=20, examples=["+91 98765 43210"])
    portal: Portal


class OtpRequestOut(BaseModel):
    # Same body for every accepted request, registered or not (DDR-97).
    status: Literal["sent_if_eligible"] = "sent_if_eligible"
    expires_in_seconds: int = d.OTP_TTL_SECONDS
    resend_after_seconds: int = d.OTP_RESEND_COOLDOWN_SECONDS


class OtpVerifyIn(BaseModel):
    mobile: str = Field(min_length=10, max_length=20)
    portal: Portal
    code: str = Field(pattern=rf"^\d{{{d.OTP_LENGTH}}}$")
    display_name: str | None = Field(default=None, max_length=d.NAME_MAX_CHARS)
    trust_device: bool = False
    device_label: str | None = Field(default=None, max_length=120)


class TrustedLoginIn(BaseModel):
    portal: Portal


class GrantOut(BaseModel):
    role: Role
    region_id: uuid.UUID | None
    kitchen_id: uuid.UUID | None


class MeOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    roles: list[GrantOut]
    permissions: list[str]
    portals: list[Portal]


class DeviceOut(BaseModel):
    id: uuid.UUID
    label: str | None
    created_at: datetime
    expires_at: datetime
