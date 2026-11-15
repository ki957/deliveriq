"""AI platform API contracts; never expose provider keys or prompt text in request metadata."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AiModelOut(BaseModel):
    logical_name: str
    capabilities: list[str]
    selected: bool


class AiStatusOut(BaseModel):
    enabled: bool
    knowledge_status: str
    models: list[AiModelOut]
    conversation_turn_limit: int
    request_metadata_retention_days: int


class AiSettingsOut(BaseModel):
    harness: str
    logical_model: str
    updated_at: datetime | None


class AiSettingsIn(BaseModel):
    logical_model: str = Field(min_length=1, max_length=40)
    reason: str = Field(min_length=1, max_length=500)


class CopilotIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None


class CopilotOut(BaseModel):
    answer: str
    conversation_id: uuid.UUID
    logical_model: str
    simulated: bool
    knowledge_status: str
    read_only: bool = True
