"""Menu routes: public customer menu and Management publication (DDR-11, DDR-31, DDR-107)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.menu import service
from app.modules.menu.schemas import CustomerMenuItemOut, ManagedMenuItemOut, MenuTransitionIn

# Public, read-only: PUBLISHED items only (Task 6 extends it with filters).
public_router = APIRouter(prefix="/api/v1/menu", tags=["menu"])
manage_router = APIRouter(prefix="/api/v1/menu/manage", tags=["menu"], dependencies=[Depends(csrf_protect)])


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except service.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@public_router.get("/items", response_model=list[CustomerMenuItemOut])
def customer_menu() -> list[CustomerMenuItemOut]:
    return [CustomerMenuItemOut.model_validate(i, from_attributes=True) for i in service.customer_menu()]


@manage_router.get("/items", response_model=list[ManagedMenuItemOut])
def list_items(principal: CurrentPrincipal) -> list[ManagedMenuItemOut]:
    items = _call(lambda: service.list_items(principal))
    return [ManagedMenuItemOut.model_validate(i, from_attributes=True) for i in items]


@manage_router.post("/items/{item_id}/transitions", response_model=ManagedMenuItemOut)
def transition(item_id: uuid.UUID, body: MenuTransitionIn, principal: CurrentPrincipal) -> ManagedMenuItemOut:
    item = _call(lambda: service.transition(principal, item_id, body.action, body.reason))
    return ManagedMenuItemOut.model_validate(item, from_attributes=True)
