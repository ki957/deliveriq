"""Data & Pipelines API contract (DATA_PIPELINE_DESIGN §12; DDR-63, DDR-64, DDR-105)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "running", "succeeded", "completed_with_quarantine", "failed", "cancelled"]


class RunSummaryOut(BaseModel):
    id: uuid.UUID
    pipeline: str
    status: RunStatus
    trigger: str
    is_test: bool
    input_ref: str | None
    region_id: uuid.UUID | None
    retry_of: uuid.UUID | None
    failure_class: str | None
    error_summary: str | None
    cancel_requested: bool
    counts: dict[str, Any]
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    has_report: bool


class PipelineOut(BaseModel):
    name: str
    display_name: str
    pipeline_group: str
    is_heavy: bool
    # False until the task that builds the pipeline lands; the backend refuses to queue it.
    implemented: bool
    last_run: RunSummaryOut | None


class StageOut(BaseModel):
    seq: int
    stage: str
    status: str
    rows_in: int | None
    rows_out: int | None
    rows_rejected: int | None
    detail: dict[str, Any]
    started_at: datetime | None
    finished_at: datetime | None


class IngestionErrorOut(BaseModel):
    stage: str
    record_ref: str | None
    reason_code: str
    message: str


class DqResultOut(BaseModel):
    check_name: str
    severity: str
    status: str
    failures: int
    detail: dict[str, Any]


class RunDetailOut(BaseModel):
    run: RunSummaryOut
    stages: list[StageOut]
    errors: list[IngestionErrorOut]
    errors_total: int
    dq_results: list[DqResultOut]


class RunCreateIn(BaseModel):
    pipeline: str = Field(pattern=r"^[a-z][a-z0-9_]+$", max_length=40, examples=["p1_sop"])
    # P1 reads the committed SOP; fault-injection inputs are added in Task 5B (DDR-104).
    input_ref: Literal["sop"] | None = None


class CancelOut(BaseModel):
    # cancelled: was queued, stopped at once; cancel_requested: running, stops at the next stage.
    outcome: Literal["cancelled", "cancel_requested"]
