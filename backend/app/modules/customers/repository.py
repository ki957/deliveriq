"""SQL for customer addresses and kitchen distances. Parameterised; callers own the transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Connection, text

_COLUMNS = (
    "id, customer_user_id, label, address_line, ST_Y(location::geometry) AS lat, "
    "ST_X(location::geometry) AS lng, "
    "is_default, created_at"
)


@dataclass(frozen=True)
class AddressRow:
    id: uuid.UUID
    customer_user_id: uuid.UUID
    label: str
    address_line: str
    lat: float
    lng: float
    is_default: bool
    created_at: datetime


@dataclass(frozen=True)
class KitchenRow:
    id: uuid.UUID
    region_id: uuid.UUID
    name: str
    lat: float
    lng: float
    location_is_synthetic: bool


def list_for(conn: Connection, customer: uuid.UUID) -> list[AddressRow]:
    rows = conn.execute(
        text(
            f"SELECT {_COLUMNS} FROM app.customer_addresses WHERE customer_user_id = :c AND "  # noqa: S608
            "deleted_at IS NULL "
            "ORDER BY is_default DESC, created_at"
        ),
        {"c": customer},
    ).all()
    return [AddressRow(*r) for r in rows]


def find(
    conn: Connection, customer: uuid.UUID, address_id: uuid.UUID, *, lock: bool = False
) -> AddressRow | None:
    sql = (
        f"SELECT {_COLUMNS} FROM app.customer_addresses WHERE id = :id AND customer_user_id "  # noqa: S608
        "= :c "
        "AND deleted_at IS NULL"
    )
    row = conn.execute(text(sql + (" FOR UPDATE" if lock else "")), {"id": address_id, "c": customer}).first()
    return AddressRow(*row) if row else None


def clear_default(conn: Connection, customer: uuid.UUID) -> None:
    conn.execute(
        text(
            "UPDATE app.customer_addresses SET is_default = false WHERE customer_user_id = :c AND is_default"
        ),
        {"c": customer},
    )


def insert(
    conn: Connection,
    customer: uuid.UUID,
    label: str,
    address_line: str,
    lat: float,
    lng: float,
    is_default: bool,
) -> uuid.UUID:
    address_id: uuid.UUID = conn.execute(
        text(
            "INSERT INTO app.customer_addresses (customer_user_id, label, address_line, "
            "location, is_default) "
            "VALUES (:c, :l, :a, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :d) RETURNING id"
        ),
        {"c": customer, "l": label, "a": address_line, "lat": lat, "lng": lng, "d": is_default},
    ).scalar_one()
    return address_id


def set_default(conn: Connection, address_id: uuid.UUID) -> None:
    conn.execute(
        text("UPDATE app.customer_addresses SET is_default = true WHERE id = :id"), {"id": address_id}
    )


def soft_delete(conn: Connection, address_id: uuid.UUID) -> None:
    conn.execute(
        text("UPDATE app.customer_addresses SET deleted_at = now(), is_default = false WHERE id = :id"),
        {"id": address_id},
    )


def ordering_kitchen(conn: Connection) -> KitchenRow:
    """The single POC kitchen (one cloud kitchen in Chennai); its location is a labelled synthetic fixture."""
    row = conn.execute(
        text(
            "SELECT id, region_id, name, ST_Y(location::geometry), "
            "ST_X(location::geometry), location_is_synthetic "
            "FROM app.kitchens WHERE status = 'ACTIVE' ORDER BY code LIMIT 1"
        )
    ).one()
    return KitchenRow(*row)


def straight_line_km(conn: Connection, kitchen_id: uuid.UUID, lat: float, lng: float) -> Decimal:
    value = conn.execute(
        text(
            "SELECT ST_Distance(k.location, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) / 1000.0 "
            "FROM app.kitchens k WHERE k.id = :k"
        ),
        {"k": kitchen_id, "lat": lat, "lng": lng},
    ).scalar_one()
    return Decimal(str(value))
