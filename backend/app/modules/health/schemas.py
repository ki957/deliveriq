"""Health API response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LiveResponse(BaseModel):
    status: Literal["alive"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["ok", "unavailable"]]
