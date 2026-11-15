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


class ActionRequestIn(BaseModel):
    request: str = Field(min_length=1, max_length=2000)


class ActionProposalOut(BaseModel):
    status: str
    message: str
    proposal_id: uuid.UUID | None
    action: str | None
    exact_change: dict[str, object] | None
    simulated: bool


class ActionConfirmIn(BaseModel):
    idempotency_key: uuid.UUID


class ActionResultOut(BaseModel):
    result: dict[str, object]


class KitchenCopilotIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    recipe_version_id: uuid.UUID | None = None


class KitchenCopilotOut(BaseModel):
    answer: str
    citations: list[str]
    grounded: bool
    retrieval_mode: str = "reduced retrieval"
    simulated: bool = True
