"""Menu routes: public customer menu and Management publication (DDR-11, DDR-31, DDR-107)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.menu import service
from app.modules.menu.schemas import (
    CustomerMenuItemOut,
    DishDetailOut,
    ManagedMenuItemOut,
    MenuFiltersOut,
    MenuTransitionIn,
)

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
def customer_menu(
    q: Annotated[str | None, Query(max_length=80)] = None,
    category: Annotated[str | None, Query(max_length=80)] = None,
    veg: bool | None = None,
    spice: Annotated[str | None, Query(max_length=40)] = None,
    min_price_paise: Annotated[int | None, Query(ge=0)] = None,
    max_price_paise: Annotated[int | None, Query(ge=0)] = None,
    bestseller: bool | None = None,
) -> list[CustomerMenuItemOut]:
    """PUBLISHED dishes only (DDR-11); fixtures excluded in production (leak control 4); CU-06 filters."""
    items = service.customer_menu(
        q=q.strip() if q and q.strip() else None,
        category=category,
        veg=veg,
        spice=spice,
        min_price_paise=min_price_paise,
        max_price_paise=max_price_paise,
        bestseller=bestseller,
    )
    return [CustomerMenuItemOut.model_validate(i, from_attributes=True) for i in items]


@public_router.get("/filters", response_model=MenuFiltersOut)
def menu_filters() -> MenuFiltersOut:
    return MenuFiltersOut.model_validate(service.menu_filters())


@public_router.get("/items/{item_id}", response_model=DishDetailOut)
def dish_detail(item_id: uuid.UUID) -> DishDetailOut:
    item, ingredients = _call(lambda: service.dish(item_id))
    base = CustomerMenuItemOut.model_validate(item, from_attributes=True)
    return DishDetailOut(**base.model_dump(), ingredients=ingredients, customizations=[])


@manage_router.get("/items", response_model=list[ManagedMenuItemOut])
def list_items(principal: CurrentPrincipal) -> list[ManagedMenuItemOut]:
    items = _call(lambda: service.list_items(principal))
    return [ManagedMenuItemOut.model_validate(i, from_attributes=True) for i in items]


@manage_router.post("/items/{item_id}/transitions", response_model=ManagedMenuItemOut)
def transition(item_id: uuid.UUID, body: MenuTransitionIn, principal: CurrentPrincipal) -> ManagedMenuItemOut:
    item = _call(lambda: service.transition(principal, item_id, body.action, body.reason))
    return ManagedMenuItemOut.model_validate(item, from_attributes=True)
