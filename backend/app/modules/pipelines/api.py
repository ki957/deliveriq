"""Data & Pipelines routes: /api/v1/pipelines/* (DATA_PIPELINE_DESIGN §12; DDR-64, DDR-105)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.pipelines import repository as repo
from app.modules.pipelines import service
from app.modules.pipelines.schemas import (
    BacklogOut,
    CancelOut,
    DqResultOut,
    IngestionErrorOut,
    PipelineOut,
    RunCreateIn,
    RunDetailOut,
    RunSummaryOut,
    StageOut,
)

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"], dependencies=[Depends(csrf_protect)])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except service.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except service.FaultInputRefused:
        raise HTTPException(
            status_code=403, detail="Fault-injection runs are allowed only in local/test"
        ) from None


def _summary(run: repo.RunRow) -> RunSummaryOut:
    return RunSummaryOut.model_validate(run, from_attributes=True)


@router.get("", response_model=list[PipelineOut])
def list_pipelines(principal: CurrentPrincipal) -> list[PipelineOut]:
    return [
        PipelineOut(
            name=s.pipeline.name,
            display_name=s.pipeline.display_name,
            pipeline_group=s.pipeline.pipeline_group,
            is_heavy=s.pipeline.is_heavy,
            implemented=s.implemented,
            inputs=s.inputs,
            last_run=_summary(s.last_run) if s.last_run else None,
        )
        for s in _call(lambda: service.list_pipelines(principal))
    ]


@router.get("/p2/backlog", response_model=BacklogOut)
def p2_backlog(principal: CurrentPrincipal) -> BacklogOut:
    """Unpublished outbox events and the oldest one's age; landed and rejected raw counts (CA only)."""
    b = _call(lambda: service.backlog(principal))
    return BacklogOut(
        waiting=b.waiting,
        oldest_waiting_at=b.oldest_waiting_at,
        oldest_age_seconds=b.oldest_age_seconds,
        landed=b.landed,
        rejected=b.rejected,
        warn_after_seconds=service.BACKLOG_WARN_SECONDS,
    )


@router.get("/runs", response_model=list[RunSummaryOut])
def list_runs(
    principal: CurrentPrincipal,
    pipeline: Annotated[str | None, Query(pattern=r"^[a-z][a-z0-9_]+$", max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RunSummaryOut]:
    return [_summary(r) for r in _call(lambda: service.list_runs(principal, pipeline, limit))]


@router.post("/runs", status_code=202, response_model=RunSummaryOut)
def trigger_run(body: RunCreateIn, principal: CurrentPrincipal) -> RunSummaryOut:
    return _summary(_call(lambda: service.trigger(principal, body.pipeline, body.input_ref)))


@router.get("/runs/{run_id}", response_model=RunDetailOut)
def run_detail(run_id: uuid.UUID, principal: CurrentPrincipal) -> RunDetailOut:
    detail = _call(lambda: service.run_detail(principal, run_id))
    return RunDetailOut(
        run=_summary(detail.run),
        stages=[StageOut.model_validate(s) for s in detail.stages],
        errors=[IngestionErrorOut.model_validate(e) for e in detail.errors],
        errors_total=detail.errors_total,
        dq_results=[DqResultOut.model_validate(d) for d in detail.dq_results],
    )


@router.post("/runs/{run_id}/cancel", response_model=CancelOut)
def cancel_run(run_id: uuid.UUID, principal: CurrentPrincipal) -> CancelOut:
    return CancelOut.model_validate({"outcome": _call(lambda: service.cancel(principal, run_id))})


@router.post("/runs/{run_id}/retry", status_code=202, response_model=RunSummaryOut)
def retry_run(run_id: uuid.UUID, principal: CurrentPrincipal) -> RunSummaryOut:
    return _summary(_call(lambda: service.retry(principal, run_id)))


@router.get(
    "/runs/{run_id}/report",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {"schema": {"type": "string"}}}}},
)
def run_report(run_id: uuid.UUID, principal: CurrentPrincipal) -> Response:
    markdown = _call(lambda: service.run_report(principal, run_id))
    return Response(
        markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="pipeline-run-{run_id}.md"'},
    )
