"""Recipe workflow routes: /api/v1/recipes/* (DDR-10, DDR-54, DDR-103, DDR-105–DDR-107)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.recipes import repository as repo
from app.modules.recipes import service
from app.modules.recipes.domain import RecipeStatus
from app.modules.recipes.schemas import (
    AcknowledgeIn,
    IngredientLineOut,
    LineageOut,
    RecipeVersionDetailOut,
    RecipeVersionOut,
    ReviewItemOut,
    SignoffIn,
    SignoffOut,
    TransitionIn,
)

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"], dependencies=[Depends(csrf_protect)])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except service.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


def _summary(v: repo.VersionRow) -> RecipeVersionOut:
    return RecipeVersionOut.model_validate(v, from_attributes=True)


def _review(i: repo.ReviewItemRow) -> ReviewItemOut:
    return ReviewItemOut.model_validate(i, from_attributes=True)


@router.get("/versions", response_model=list[RecipeVersionOut])
def list_versions(principal: CurrentPrincipal, status: RecipeStatus | None = None) -> list[RecipeVersionOut]:
    return [_summary(v) for v in _call(lambda: service.list_versions(principal, status))]


@router.get("/versions/{version_id}", response_model=RecipeVersionDetailOut)
def version_detail(version_id: uuid.UUID, principal: CurrentPrincipal) -> RecipeVersionDetailOut:
    detail = _call(lambda: service.version_detail(principal, version_id))
    v = detail.version
    return RecipeVersionDetailOut(
        **_summary(v).model_dump(),
        prep_type=v.prep_type,
        portion=v.portion,
        method=v.method,
        quality=v.quality,
        inventory_rule=v.inventory_rule,
        validation_text=v.validation_text,
        lineage=LineageOut.model_validate(v, from_attributes=True),
        ingredients=[IngredientLineOut.model_validate(i, from_attributes=True) for i in detail.ingredients],
        signoffs=[SignoffOut.model_validate(s, from_attributes=True) for s in detail.signoffs],
        missing_signoffs=detail.missing_signoffs,
        review_items=[_review(i) for i in detail.review_items],
    )


@router.post("/versions/{version_id}/transitions", response_model=RecipeVersionOut)
def transition(version_id: uuid.UUID, body: TransitionIn, principal: CurrentPrincipal) -> RecipeVersionOut:
    return _summary(_call(lambda: service.transition(principal, version_id, body.action, body.reason)))


@router.post("/versions/{version_id}/signoffs", status_code=204)
def record_signoff(version_id: uuid.UUID, body: SignoffIn, principal: CurrentPrincipal) -> Response:
    _call(lambda: service.record_signoff(principal, version_id, body.signoff_type, body.note))
    return Response(status_code=204)


@router.get("/review-items", response_model=list[ReviewItemOut])
def review_items(
    principal: CurrentPrincipal,
    status: Literal["OPEN", "ACKNOWLEDGED"] | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[ReviewItemOut]:
    return [_review(i) for i in _call(lambda: service.review_items(principal, status, limit))]


@router.post("/review-items/{item_id}/acknowledge", response_model=ReviewItemOut)
def acknowledge(item_id: uuid.UUID, body: AcknowledgeIn, principal: CurrentPrincipal) -> ReviewItemOut:
    return _review(_call(lambda: service.acknowledge(principal, item_id, body.note)))
