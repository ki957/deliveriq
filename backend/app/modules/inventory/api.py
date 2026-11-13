"""Kitchen inventory routes: /api/v1/kitchen/inventory (KI-21–KI-23; DDR-111 (9))."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.inventory import domain as d
from app.modules.inventory import service
from app.modules.inventory.schemas import AdjustIn, StockOut, ThresholdIn

router = APIRouter(prefix="/api/v1/kitchen/inventory", tags=["kitchen"], dependencies=[Depends(csrf_protect)])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except service.Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _out(row: service.StockRow) -> StockOut:
    free = d.available(row.on_hand, row.reserved)
    return StockOut(
        ingredient_id=row.ingredient_id,
        name=row.name,
        unit=row.unit,
        on_hand=row.on_hand,
        reserved=row.reserved,
        available=free,
        low_stock_threshold=row.low_stock_threshold,
        is_low=d.is_low(free, row.low_stock_threshold),
        is_test_fixture=row.is_test_fixture,
        used_in=list(row.used_in),
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[StockOut])
def stock(principal: CurrentPrincipal, kitchen_id: uuid.UUID | None = None) -> list[StockOut]:
    """Full stock (Kitchen Manager)."""
    return [_out(r) for r in _call(lambda: service.stock(principal, kitchen_id))]


@router.get("/low-stock", response_model=list[StockOut])
def low_stock(principal: CurrentPrincipal, kitchen_id: uuid.UUID | None = None) -> list[StockOut]:
    """Low-stock alerts (Kitchen Staff and Manager)."""
    return [_out(r) for r in _call(lambda: service.low_stock(principal, kitchen_id))]


@router.post("/{ingredient_id}/adjust", response_model=StockOut)
def adjust(
    ingredient_id: uuid.UUID, body: AdjustIn, principal: CurrentPrincipal, kitchen_id: uuid.UUID | None = None
) -> StockOut:
    """Signed stock adjustment with a reason (Kitchen Manager); ledger and audit record."""
    return _out(
        _call(
            lambda: service.adjust(principal, kitchen_id, ingredient_id, delta=body.delta, reason=body.reason)
        )
    )


@router.put("/{ingredient_id}/threshold", response_model=StockOut)
def set_threshold(
    ingredient_id: uuid.UUID,
    body: ThresholdIn,
    principal: CurrentPrincipal,
    kitchen_id: uuid.UUID | None = None,
) -> StockOut:
    """Set or clear the low-stock threshold with a reason (Kitchen Manager); audited."""
    return _out(
        _call(
            lambda: service.set_threshold(
                principal, kitchen_id, ingredient_id, threshold=body.low_stock_threshold, reason=body.reason
            )
        )
    )
