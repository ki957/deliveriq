"""Health routes: /health/live (process up) and /health/ready (DB + Redis reachable)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.modules.health.schemas import LiveResponse, ReadyResponse
from app.modules.health.service import Check, default_checks, readiness

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=LiveResponse)
def live() -> LiveResponse:
    return LiveResponse(status="alive")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse, "description": "A dependency is unavailable"}},
)
def ready(checks: Annotated[dict[str, Check], Depends(default_checks)]) -> JSONResponse:
    result = readiness(checks)
    body = ReadyResponse(status="ready" if result.ready else "not_ready", checks=result.checks)  # type: ignore[arg-type]
    return JSONResponse(body.model_dump(), status_code=200 if result.ready else 503)
