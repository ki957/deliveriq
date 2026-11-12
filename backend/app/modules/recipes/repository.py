"""SQL for recipes, versions, sign-offs and the review queue. Parameterised; callers own the transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, Row, text

_VERSION_COLUMNS = """
    v.id, v.recipe_id, r.name, r.source_menu_id, r.kitchen_id, k.region_id, v.version, v.status,
    v.is_test_fixture, v.quarantine_reason, v.prep_type, v.portion, v.method, v.quality, v.inventory_rule,
    v.validation_text, v.source_path, v.source_sha256, v.source_card_id, v.source_line_start,
    v.source_line_end,
    v.source_page_ref, v.candidate_category, v.updated_at,
    (SELECT count(*) FROM app.recipe_review_items i WHERE i.recipe_version_id = v.id AND i.status = 'OPEN')
        AS open_review_items
"""
_FROM = (
    "FROM app.recipe_versions v JOIN app.recipes r ON r.id = v.recipe_id "
    "JOIN app.kitchens k ON k.id = r.kitchen_id"
)


@dataclass(frozen=True)
class VersionRow:
    id: uuid.UUID
    recipe_id: uuid.UUID
    name: str
    source_menu_id: str | None
    kitchen_id: uuid.UUID
    region_id: uuid.UUID
    version: int
    status: str
    is_test_fixture: bool
    quarantine_reason: str | None
    prep_type: str | None
    portion: str | None
    method: str | None
    quality: str | None
    inventory_rule: str | None
    validation_text: str | None
    source_path: str | None
    source_sha256: str | None
    source_card_id: str | None
    source_line_start: int | None
    source_line_end: int | None
    source_page_ref: int | None
    candidate_category: str | None
    updated_at: datetime
    open_review_items: int


@dataclass(frozen=True)
class IngredientLineRow:
    line_no: int
    ingredient_id: uuid.UUID
    name: str
    quantity: Decimal
    unit: str
    source_line: int | None
    original_text: str | None


@dataclass(frozen=True)
class SignoffRow:
    signoff_type: str
    signed_by: uuid.UUID
    signed_at: datetime
    note: str | None


@dataclass(frozen=True)
class ReviewItemRow:
    id: uuid.UUID
    recipe_version_id: uuid.UUID
    recipe_name: str
    source_card_id: str | None
    kitchen_id: uuid.UUID
    region_id: uuid.UUID
    reason_code: str
    subject: str
    detail: str
    source_ref: str
    source_line: int | None
    status: str
    acknowledged_by: uuid.UUID | None
    acknowledged_at: datetime | None
    note: str | None


def _version(row: Row[Any]) -> VersionRow:
    return VersionRow(**row._mapping)


def list_versions(
    conn: Connection, kitchen_ids: frozenset[uuid.UUID] | None, status: str | None, test_only: bool
) -> list[VersionRow]:
    """kitchen_ids None = every kitchen (CA, product-owner sign-off); test_only limits to TEST recipes."""
    rows = conn.execute(
        text(
            f"SELECT {_VERSION_COLUMNS} {_FROM} "
            "WHERE (CAST(:all_kitchens AS boolean) OR r.kitchen_id = ANY(:kitchens)) "
            "AND (CAST(:status AS text) IS NULL OR v.status = :status) "
            "AND (NOT CAST(:test_only AS boolean) OR v.is_test_fixture) "
            "ORDER BY v.is_test_fixture DESC, r.source_menu_id NULLS FIRST, r.name, v.version"
        ),
        {
            "all_kitchens": kitchen_ids is None,
            "kitchens": list(kitchen_ids or ()),
            "status": status,
            "test_only": test_only,
        },
    ).all()
    return [_version(r) for r in rows]


def find_version(conn: Connection, version_id: uuid.UUID, *, lock: bool = False) -> VersionRow | None:
    sql = f"SELECT {_VERSION_COLUMNS} {_FROM} WHERE v.id = :id"
    row = conn.execute(text(sql + (" FOR UPDATE OF v" if lock else "")), {"id": version_id}).first()
    return _version(row) if row else None


def ingredient_lines(conn: Connection, version_id: uuid.UUID) -> list[IngredientLineRow]:
    rows = conn.execute(
        text(
            "SELECT ri.line_no, ri.ingredient_id, i.name, ri.quantity, ri.unit, ri.source_line, "
            "ri.original_text "
            "FROM app.recipe_ingredients ri JOIN app.ingredients i ON i.id = ri.ingredient_id "
            "WHERE ri.recipe_version_id = :id ORDER BY ri.line_no"
        ),
        {"id": version_id},
    ).all()
    return [IngredientLineRow(*r) for r in rows]


def signoffs(conn: Connection, version_id: uuid.UUID) -> list[SignoffRow]:
    rows = conn.execute(
        text(
            "SELECT signoff_type, signed_by, signed_at, note FROM app.recipe_signoffs "
            "WHERE recipe_version_id = :id ORDER BY signed_at"
        ),
        {"id": version_id},
    ).all()
    return [SignoffRow(*r) for r in rows]


def insert_signoff(
    conn: Connection, version_id: uuid.UUID, signoff_type: str, user_id: uuid.UUID, note: str | None
) -> bool:
    """False if this sign-off type is already recorded for the version (UNIQUE; recorded once)."""
    inserted = conn.execute(
        text(
            "INSERT INTO app.recipe_signoffs (recipe_version_id, signoff_type, signed_by, note) "
            "SELECT :v, :t, :u, :n WHERE NOT EXISTS (SELECT 1 FROM app.recipe_signoffs "
            "WHERE recipe_version_id = :v AND signoff_type = :t)"
        ),
        {"v": version_id, "t": signoff_type, "u": user_id, "n": note},
    ).rowcount
    return bool(inserted)


def set_status(conn: Connection, version_id: uuid.UUID, status: str) -> None:
    conn.execute(
        text("UPDATE app.recipe_versions SET status = :s WHERE id = :id"), {"s": status, "id": version_id}
    )


_REVIEW_COLUMNS = """
    i.id, i.recipe_version_id, r.name AS recipe_name, v.source_card_id, r.kitchen_id, k.region_id,
    i.reason_code,
    i.subject, i.detail, i.source_ref, i.source_line, i.status, i.acknowledged_by, i.acknowledged_at, i.note
"""
_REVIEW_FROM = (
    "FROM app.recipe_review_items i JOIN app.recipe_versions v ON v.id = i.recipe_version_id "
    "JOIN app.recipes r ON r.id = v.recipe_id JOIN app.kitchens k ON k.id = r.kitchen_id"
)


def review_items(
    conn: Connection,
    kitchen_ids: frozenset[uuid.UUID],
    *,
    status: str | None,
    version_id: uuid.UUID | None,
    limit: int,
) -> list[ReviewItemRow]:
    rows = conn.execute(
        text(
            f"SELECT {_REVIEW_COLUMNS} {_REVIEW_FROM} WHERE r.kitchen_id = ANY(:kitchens) "
            "AND (CAST(:status AS text) IS NULL OR i.status = :status) "
            "AND (CAST(:version AS uuid) IS NULL OR i.recipe_version_id = :version) "
            "ORDER BY v.source_card_id NULLS LAST, i.reason_code, i.subject LIMIT :lim"
        ),
        {"kitchens": list(kitchen_ids), "status": status, "version": version_id, "lim": limit},
    ).all()
    return [ReviewItemRow(**r._mapping) for r in rows]


def find_review_item(conn: Connection, item_id: uuid.UUID, *, lock: bool = False) -> ReviewItemRow | None:
    sql = f"SELECT {_REVIEW_COLUMNS} {_REVIEW_FROM} WHERE i.id = :id"
    row = conn.execute(text(sql + (" FOR UPDATE OF i" if lock else "")), {"id": item_id}).first()
    return ReviewItemRow(**row._mapping) if row else None


def acknowledge_review_item(conn: Connection, item_id: uuid.UUID, user_id: uuid.UUID, note: str) -> None:
    conn.execute(
        text(
            "UPDATE app.recipe_review_items SET status = 'ACKNOWLEDGED', acknowledged_by = :u, "
            "acknowledged_at = now(), note = :n WHERE id = :id AND status = 'OPEN'"
        ),
        {"u": user_id, "n": note, "id": item_id},
    )
