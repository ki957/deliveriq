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
    m.is_test_fixture, m.is_bestseller, m.kitchen_id, k.region_id, m.recipe_id,
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
    is_bestseller: bool
    kitchen_id: uuid.UUID
    region_id: uuid.UUID
    recipe_id: uuid.UUID
    has_active_recipe: bool
    updated_at: datetime


def _item(row: Row[Any]) -> MenuItemRow:
    return MenuItemRow(**row._mapping)


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


# ---------------------------------------------------------------- customer menu filters (CU-06, DDR-110)
def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def published_filtered(
    conn: Connection,
    *,
    include_fixtures: bool,
    q: str | None,
    category: str | None,
    veg: bool | None,
    spice: str | None,
    min_price_paise: int | None,
    max_price_paise: int | None,
    bestseller: bool | None,
) -> list[MenuItemRow]:
    rows = conn.execute(
        text(
            f"SELECT {_COLUMNS} {_FROM} WHERE m.publication_status = 'PUBLISHED' "
            "AND (CAST(:fixtures AS boolean) OR NOT m.is_test_fixture) "
            "AND (CAST(:q AS text) IS NULL OR m.name ILIKE :q OR m.description ILIKE :q) "
            "AND (CAST(:cat AS text) IS NULL OR c.name = :cat) "
            "AND (CAST(:veg AS boolean) IS NULL OR m.is_veg = :veg) "
            "AND (CAST(:spice AS text) IS NULL OR m.spice_level = :spice) "
            "AND (CAST(:minp AS integer) IS NULL OR m.price_paise >= :minp) "
            "AND (CAST(:maxp AS integer) IS NULL OR m.price_paise <= :maxp) "
            "AND (CAST(:best AS boolean) IS NULL OR m.is_bestseller = :best) "
            "ORDER BY c.display_order, m.name"
        ),
        {
            "fixtures": include_fixtures,
            "q": _like(q) if q else None,
            "cat": category,
            "veg": veg,
            "spice": spice,
            "minp": min_price_paise,
            "maxp": max_price_paise,
            "best": bestseller,
        },
    ).all()
    return [_item(r) for r in rows]


def filter_options(conn: Connection, *, include_fixtures: bool) -> dict[str, object]:
    """Options from the published dishes themselves: nothing is invented (DDR-110 (2))."""
    row = conn.execute(
        text(
            "SELECT array_remove(array_agg(DISTINCT c.name), NULL), "
            "array_remove(array_agg(DISTINCT m.spice_level), NULL), "
            "min(m.price_paise), max(m.price_paise), bool_or(m.is_bestseller), bool_or(m.is_veg), "
            "bool_or(NOT m.is_veg) "
            f"{_FROM} WHERE m.publication_status = 'PUBLISHED' "
            "AND (CAST(:fixtures AS boolean) OR NOT m.is_test_fixture)"
        ),
        {"fixtures": include_fixtures},
    ).one()
    return {
        "categories": sorted(row[0] or []),
        "spice_levels": sorted(row[1] or []),
        "min_price_paise": row[2],
        "max_price_paise": row[3],
        "has_bestsellers": bool(row[4]),
        "has_veg": bool(row[5]),
        "has_non_veg": bool(row[6]),
    }


def published_item(conn: Connection, item_id: uuid.UUID, *, include_fixtures: bool) -> MenuItemRow | None:
    row = conn.execute(
        text(
            f"SELECT {_COLUMNS} {_FROM} WHERE m.id = :id AND m.publication_status = 'PUBLISHED' "
            "AND (CAST(:fixtures AS boolean) OR NOT m.is_test_fixture)"
        ),
        {"id": item_id, "fixtures": include_fixtures},
    ).first()
    return _item(row) if row else None


def active_ingredient_names(conn: Connection, recipe_id: uuid.UUID) -> list[str]:
    """Ingredient names of the dish's ACTIVE recipe version (CU-08 "ingredients"); no quantities."""
    rows = conn.execute(
        text(
            "SELECT i.name FROM app.recipe_versions v JOIN app.recipe_ingredients ri ON "
            "ri.recipe_version_id = v.id "
            "JOIN app.ingredients i ON i.id = ri.ingredient_id WHERE v.recipe_id = :r AND "
            "v.status = 'ACTIVE' "
            "ORDER BY ri.line_no"
        ),
        {"r": recipe_id},
    ).all()
    return [r[0] for r in rows]
