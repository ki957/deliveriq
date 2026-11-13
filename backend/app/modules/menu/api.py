"""Menu routes: public customer menu and Management publication (DDR-11, DDR-31, DDR-107)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.menu import service
from app.modules.menu.schemas import (
    AvailabilityDecisionIn,
    AvailabilityRequestIn,
    AvailabilityRequestOut,
    CustomerMenuItemOut,
    DishDetailOut,
    KitchenDishOut,
    ManagedMenuItemOut,
    MenuFiltersOut,
    MenuTransitionIn,
)

# Public, read-only: PUBLISHED items only (Task 6 extends it with filters).
public_router = APIRouter(prefix="/api/v1/menu", tags=["menu"])
manage_router = APIRouter(prefix="/api/v1/menu/manage", tags=["menu"], dependencies=[Depends(csrf_protect)])
availability_router = APIRouter(
    prefix="/api/v1/menu/availability", tags=["menu"], dependencies=[Depends(csrf_protect)]
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
    except service.Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


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


# ---------------------------------------------------------------- dish availability (KI-24; DDR-111 (7))
@availability_router.get("/dishes", response_model=list[KitchenDishOut])
def kitchen_dishes(kitchen_id: uuid.UUID, principal: CurrentPrincipal) -> list[KitchenDishOut]:
    """The kitchen's dishes that are on the menu or temporarily unavailable."""
    items = _call(lambda: service.kitchen_dishes(principal, kitchen_id))
    return [KitchenDishOut.model_validate(i, from_attributes=True) for i in items]


@availability_router.get("/requests", response_model=list[AvailabilityRequestOut])
def availability_requests(
    principal: CurrentPrincipal, pending_only: bool = False
) -> list[AvailabilityRequestOut]:
    """Kitchen roles: their kitchen's requests. RM: assigned regions. CA: all regions."""
    rows = _call(lambda: service.availability_requests(principal, pending_only=pending_only))
    return [AvailabilityRequestOut.model_validate(r, from_attributes=True) for r in rows]


@availability_router.post("/requests", status_code=201, response_model=AvailabilityRequestOut)
def request_availability(body: AvailabilityRequestIn, principal: CurrentPrincipal) -> AvailabilityRequestOut:
    """Kitchen Staff or Manager ask to take a dish off the menu, or to bring it back, with a reason."""
    row = _call(lambda: service.request_availability(principal, body.menu_item_id, body.kind, body.reason))
    return AvailabilityRequestOut.model_validate(row, from_attributes=True)


@availability_router.post("/requests/{request_id}/decision", response_model=AvailabilityRequestOut)
def decide_availability(
    request_id: uuid.UUID, body: AvailabilityDecisionIn, principal: CurrentPrincipal
) -> AvailabilityRequestOut:
    """RM (own region) or CA approves (the menu changes) or rejects with a reason. Audited."""
    row = _call(
        lambda: service.decide_availability(principal, request_id, approve=body.approve, reason=body.reason)
    )
    return AvailabilityRequestOut.model_validate(row, from_attributes=True)
