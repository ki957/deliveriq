"""Customer routes: public serviceability check and saved addresses (CU-01–CU-04; DDR-110)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.modules.customers import service
from app.modules.customers.schemas import AddressIn, AddressOut, ServiceabilityOut, serviceability_out
from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect

public_router = APIRouter(prefix="/api/v1/serviceability", tags=["customers"])
addresses_router = APIRouter(
    prefix="/api/v1/me/addresses", tags=["customers"], dependencies=[Depends(csrf_protect)]
)


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Address not found") from None


def _address_out(view: service.AddressView) -> AddressOut:
    a = view.address
    return AddressOut(
        id=a.id,
        label=a.label,
        address_line=a.address_line,
        lat=a.lat,
        lng=a.lng,
        is_default=a.is_default,
        created_at=a.created_at,
        serviceability=serviceability_out(view.kitchen, view.serviceability),
    )


@public_router.get("", response_model=ServiceabilityOut)
def check(
    lat: Annotated[float, Query(ge=6.0, le=37.5)], lng: Annotated[float, Query(ge=68.0, le=97.5)]
) -> ServiceabilityOut:
    """For visitors too (CU-01): no location is stored on the server (DDR-110)."""
    kitchen, result = service.check_point(lat, lng)
    return serviceability_out(kitchen, result)


@addresses_router.get("", response_model=list[AddressOut])
def list_addresses(principal: CurrentPrincipal) -> list[AddressOut]:
    return [_address_out(v) for v in _call(lambda: service.list_addresses(principal))]


@addresses_router.post("", status_code=201, response_model=AddressOut)
def add_address(body: AddressIn, principal: CurrentPrincipal) -> AddressOut:
    view = _call(
        lambda: service.add_address(
            principal,
            label=body.label.strip(),
            address_line=body.address_line.strip(),
            lat=body.lat,
            lng=body.lng,
            make_default=body.make_default,
        )
    )
    return _address_out(view)


@addresses_router.post("/{address_id}/default", response_model=AddressOut)
def make_default(address_id: uuid.UUID, principal: CurrentPrincipal) -> AddressOut:
    return _address_out(_call(lambda: service.make_default(principal, address_id)))


@addresses_router.delete("/{address_id}", status_code=204)
def delete_address(address_id: uuid.UUID, principal: CurrentPrincipal) -> Response:
    _call(lambda: service.delete_address(principal, address_id))
    return Response(status_code=204)
