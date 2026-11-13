"""Customer addresses and serviceability (CU-01–CU-04; #1 §6; DDR-55, DDR-110).

Visitors check serviceability for a point without an account (CU-01); saved addresses need a
customer session and are private (another customer's address reads as not found).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Connection

from app.core.db import get_engine
from app.core.permissions import Permission, Principal, can
from app.modules.customers import domain as d
from app.modules.customers import repository as repo
from app.shared import config_values, geo

AddressRow = repo.AddressRow
KitchenRow = repo.KitchenRow
Serviceability = d.Serviceability


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


@dataclass(frozen=True)
class AddressView:
    address: repo.AddressRow
    kitchen: repo.KitchenRow
    serviceability: d.Serviceability


def _view(conn: Connection, address: repo.AddressRow) -> AddressView:
    k, result = check(conn, address.lat, address.lng)
    return AddressView(address, k, result)


def _require(principal: Principal) -> None:
    if not can(principal, Permission.CUSTOMER_ADDRESSES_MANAGE, customer_id=principal.user_id):
        raise Forbidden


def kitchen(conn: Connection) -> repo.KitchenRow:
    return repo.ordering_kitchen(conn)


def check(conn: Connection, lat: float, lng: float) -> tuple[repo.KitchenRow, d.Serviceability]:
    """Both rules, straight-line by PostGIS and road through the adapter (labelled when estimated)."""
    k = repo.ordering_kitchen(conn)
    straight = geo.km(repo.straight_line_km(conn, k.id, lat, lng))
    road = geo.road_adapter().road_distance(geo.Point(k.lat, k.lng), geo.Point(lat, lng), straight)
    return k, d.evaluate(
        straight,
        road.km,
        road_estimated=road.estimated,
        straight_line_max_km=config_values.value(conn, "SERVICEABILITY_STRAIGHT_LINE_MAX", kitchen_id=k.id),
        road_max_km=config_values.value(conn, "SERVICEABILITY_ROAD_DISTANCE_MAX", kitchen_id=k.id),
    )


def check_point(lat: float, lng: float) -> tuple[repo.KitchenRow, d.Serviceability]:
    with get_engine().connect() as conn:
        return check(conn, lat, lng)


def owned_address(conn: Connection, principal: Principal, address_id: uuid.UUID) -> repo.AddressRow:
    """For checkout: the customer's own, live address (revalidated before placement, CU-03)."""
    address = repo.find(conn, principal.user_id, address_id)
    if address is None:
        raise NotFound
    return address


def list_addresses(principal: Principal) -> list[AddressView]:
    _require(principal)
    with get_engine().connect() as conn:
        return [_view(conn, a) for a in repo.list_for(conn, principal.user_id)]


def add_address(
    principal: Principal, *, label: str, address_line: str, lat: float, lng: float, make_default: bool
) -> AddressView:
    _require(principal)
    with get_engine().begin() as conn:
        first = not repo.list_for(conn, principal.user_id)
        if make_default or first:
            repo.clear_default(conn, principal.user_id)
        address_id = repo.insert(
            conn, principal.user_id, label, address_line, lat, lng, make_default or first
        )
        address = repo.find(conn, principal.user_id, address_id)
        if address is None:  # pragma: no cover - inserted in this transaction
            raise NotFound
        return _view(conn, address)


def make_default(principal: Principal, address_id: uuid.UUID) -> AddressView:
    _require(principal)
    with get_engine().begin() as conn:
        address = repo.find(conn, principal.user_id, address_id, lock=True)
        if address is None:
            raise NotFound
        repo.clear_default(conn, principal.user_id)
        repo.set_default(conn, address_id)
        updated = repo.find(conn, principal.user_id, address_id)
        if updated is None:  # pragma: no cover
            raise NotFound
        return _view(conn, updated)


def delete_address(principal: Principal, address_id: uuid.UUID) -> None:
    _require(principal)
    with get_engine().begin() as conn:
        if repo.find(conn, principal.user_id, address_id, lock=True) is None:
            raise NotFound
        repo.soft_delete(conn, address_id)
