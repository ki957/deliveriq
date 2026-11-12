"""SQL for menu items. Parameterised; callers own the transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, Row, text

_COLUMNS = """
    m.id, m.name, m.description, m.price_paise, m.is_veg, m.spice_level, m.tax_classification,
    m.prep_time_minutes, m.image_url, m.image_is_placeholder, c.name AS category, m.publication_status,
    m.is_test_fixture, m.kitchen_id, k.region_id, m.recipe_id,
    EXISTS (SELECT 1 FROM app.recipe_versions v WHERE v.recipe_id = m.recipe_id AND v.status = 'ACTIVE')
        AS has_active_recipe,
    m.updated_at
"""
_FROM = (
    "FROM app.menu_items m JOIN app.kitchens k ON k.id = m.kitchen_id "
    "LEFT JOIN app.menu_categories c ON c.id = m.category_id"
)


@dataclass(frozen=True)
class MenuItemRow:
    id: uuid.UUID
    name: str
    description: str | None
    price_paise: int | None
    is_veg: bool | None
    spice_level: str | None
    tax_classification: str | None
    prep_time_minutes: int | None
    image_url: str | None
    image_is_placeholder: bool
    category: str | None
    publication_status: str
    is_test_fixture: bool
    kitchen_id: uuid.UUID
    region_id: uuid.UUID
    recipe_id: uuid.UUID
    has_active_recipe: bool
    updated_at: datetime


def _item(row: Row[Any]) -> MenuItemRow:
    return MenuItemRow(**row._mapping)


def published(conn: Connection, *, include_fixtures: bool) -> list[MenuItemRow]:
    """Customer view: PUBLISHED only; fixtures excluded in production (plan §5.2 control 4)."""
    rows = conn.execute(
        text(
            f"SELECT {_COLUMNS} {_FROM} WHERE m.publication_status = 'PUBLISHED' "
            "AND (CAST(:fixtures AS boolean) OR NOT m.is_test_fixture) ORDER BY c.display_order, m.name"
        ),
        {"fixtures": include_fixtures},
    ).all()
    return [_item(r) for r in rows]


def list_items(conn: Connection, regions: frozenset[uuid.UUID] | None) -> list[MenuItemRow]:
    rows = conn.execute(
        text(
            f"SELECT {_COLUMNS} {_FROM} "
            "WHERE (CAST(:all_regions AS boolean) OR k.region_id = ANY(:regions)) ORDER BY m.name"
        ),
        {"all_regions": regions is None, "regions": list(regions or ())},
    ).all()
    return [_item(r) for r in rows]


def find_item(conn: Connection, item_id: uuid.UUID, *, lock: bool = False) -> MenuItemRow | None:
    sql = f"SELECT {_COLUMNS} {_FROM} WHERE m.id = :id"
    row = conn.execute(text(sql + (" FOR UPDATE OF m" if lock else "")), {"id": item_id}).first()
    return _item(row) if row else None


def set_status(conn: Connection, item_id: uuid.UUID, status: str) -> None:
    conn.execute(
        text("UPDATE app.menu_items SET publication_status = :s WHERE id = :id"), {"s": status, "id": item_id}
    )
