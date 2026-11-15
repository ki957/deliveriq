"""Kitchen knowledge approval routes (DDR-46, DDR-122)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.knowledge import service
from app.modules.knowledge.schemas import GoldenSetOut, KnowledgeDecisionIn, KnowledgeVersionOut

router = APIRouter(
    prefix="/api/v1/knowledge/kitchen", tags=["kitchen-knowledge"], dependencies=[Depends(csrf_protect)]
)


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except service.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.get("/versions", response_model=list[KnowledgeVersionOut])
def list_versions(principal: CurrentPrincipal) -> list[KnowledgeVersionOut]:
    rows = _call(lambda: service.list_versions(principal))
    return [KnowledgeVersionOut.model_validate(row) for row in rows]


@router.post("/versions/{version_id}/approve", response_model=KnowledgeVersionOut)
def approve(
    version_id: uuid.UUID, body: KnowledgeDecisionIn, principal: CurrentPrincipal
) -> KnowledgeVersionOut:
    row = _call(lambda: service.decide(principal, version_id, approve=True, reason=body.reason))
    return KnowledgeVersionOut.model_validate(row)


@router.post("/versions/{version_id}/reject", response_model=KnowledgeVersionOut)
def reject(
    version_id: uuid.UUID, body: KnowledgeDecisionIn, principal: CurrentPrincipal
) -> KnowledgeVersionOut:
    row = _call(lambda: service.decide(principal, version_id, approve=False, reason=body.reason))
    return KnowledgeVersionOut.model_validate(row)


@router.get("/golden-set", response_model=GoldenSetOut)
def golden_set(principal: CurrentPrincipal) -> GoldenSetOut:
    return GoldenSetOut.model_validate(_call(lambda: service.golden_set(principal)))


@router.post("/golden-set/{set_id}/approve", response_model=GoldenSetOut)
def approve_golden_set(
    set_id: uuid.UUID, body: KnowledgeDecisionIn, principal: CurrentPrincipal
) -> GoldenSetOut:
    row = _call(lambda: service.approve_golden_set(principal, set_id, body.reason))
    return GoldenSetOut.model_validate(row)
