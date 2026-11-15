"""Kitchen knowledge retrieval with SQL-enforced publication and fixture scope."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.permissions import Principal, Role


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    content: str
    source_ref: str
    recipe_version_id: str | None


def retrieve(question: str, principal: Principal, recipe_version_id: str | None = None) -> list[Evidence]:
    """Return published evidence visible to this kitchen role and environment."""
    kitchen_grants = [g for g in principal.grants if g.role in {Role.KITCHEN_STAFF, Role.KITCHEN_MANAGER}]
    kitchen_ids = [str(g.kitchen_id) for g in kitchen_grants if g.kitchen_id is not None]
    if not kitchen_ids:
        return []
    include_fixtures = get_settings().app_env in {"local", "test", "demo"}
    sql = text("""
        SELECT * FROM app.retrieve_kitchen_chunks(
            :question, CAST(:kitchen_ids AS uuid[]), :include_fixtures,
            CAST(:recipe_version_id AS uuid), CAST(:roles AS text[])
        )
    """)
    with get_engine().connect() as conn:
        rows = conn.execute(
            sql,
            {
                "question": question,
                "kitchen_ids": kitchen_ids,
                "roles": [role.value for role in principal.roles],
                "include_fixtures": include_fixtures,
                "recipe_version_id": recipe_version_id,
            },
        ).all()
    return [
        Evidence(
            str(row.id),
            row.content,
            row.source_ref,
            str(row.recipe_version_id) if row.recipe_version_id else None,
        )
        for row in rows
    ]


def retrieve_hybrid(
    question: str,
    principal: Principal,
    query_vector: list[float],
    recipe_version_id: str | None = None,
) -> list[Evidence]:
    """Run vector + English full-text RRF retrieval when a worker embedding is available."""
    kitchen_grants = [g for g in principal.grants if g.role in {Role.KITCHEN_STAFF, Role.KITCHEN_MANAGER}]
    kitchen_ids = [str(g.kitchen_id) for g in kitchen_grants if g.kitchen_id is not None]
    if not kitchen_ids:
        return []
    include_fixtures = get_settings().app_env in {"local", "test", "demo"}
    sql = text("""
        SELECT * FROM app.retrieve_kitchen_chunks_hybrid(
            :question, CAST(:query_vector AS vector), CAST(:kitchen_ids AS uuid[]), :include_fixtures,
            CAST(:recipe_version_id AS uuid), CAST(:roles AS text[])
        )
    """)
    with get_engine().connect() as conn:
        rows = conn.execute(
            sql,
            {
                "question": question,
                "query_vector": "[" + ",".join(str(value) for value in query_vector) + "]",
                "kitchen_ids": kitchen_ids,
                "roles": [role.value for role in principal.roles],
                "include_fixtures": include_fixtures,
                "recipe_version_id": recipe_version_id,
            },
        ).all()
    return [
        Evidence(
            str(row.id),
            row.content,
            row.source_ref,
            str(row.recipe_version_id) if row.recipe_version_id else None,
        )
        for row in rows
    ]
