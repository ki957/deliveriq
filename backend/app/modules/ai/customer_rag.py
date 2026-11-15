"""Customer-scoped hybrid retrieval; no Kitchen or Management rows are queryable."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

from app.core.db import get_engine
from app.core.permissions import Principal, Role


@dataclass(frozen=True)
class CustomerChunk:
    id: str
    content: str
    source_ref: str
    score: float


def retrieve(question: str, principal: Principal | None) -> list[CustomerChunk]:
    authenticated = bool(principal and Role.CUSTOMER in principal.roles)
    with get_engine().connect() as conn:
        rows = (
            conn.execute(
                text("""
                SELECT id, content, source_ref, retrieval_score
                FROM app.retrieve_customer_chunks_hybrid(
                    :question, NULL, :authenticated, :fixtures
                )
            """),
                {"question": question, "authenticated": authenticated, "fixtures": False},
            )
            .mappings()
            .all()
        )
    return [
        CustomerChunk(str(r["id"]), r["content"], r["source_ref"], float(r["retrieval_score"])) for r in rows
    ]
