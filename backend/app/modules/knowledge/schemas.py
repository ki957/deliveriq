"""Knowledge approval API contracts (DDR-122)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeVersionOut(BaseModel):
    id: uuid.UUID
    doc_id: str
    display_name: str
    doc_version: int
    content_sha256: str
    status: Literal["DRAFT", "APPROVED", "REJECTED"]
    kitchen_id: uuid.UUID | None = None
    submitted_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    decision_reason: str | None


class KnowledgeDecisionIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class GoldenSetOut(BaseModel):
    id: uuid.UUID
    suite: Literal["DDR-90"]
    portal: Literal["KITCHEN", "CUSTOMER"]
    name: str
    approval_label: str
    case_count: int
    leak_count: int
    status: Literal["DRAFT", "APPROVED", "BLOCKED"]
    dataset_hash: str | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    decision_reason: str | None
