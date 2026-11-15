"""KM-scoped knowledge approval service (DDR-46, DDR-122)."""

from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy import Connection, text

from app.core.db import get_engine
from app.core.permissions import Permission, Principal, Role, can


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def _kitchens(principal: Principal) -> tuple[uuid.UUID, ...]:
    kitchens = tuple(
        g.kitchen_id
        for g in principal.grants
        if g.role is Role.KITCHEN_MANAGER
        and g.kitchen_id is not None
        and can(principal, Permission.KITCHEN_KNOWLEDGE_APPROVE, kitchen_id=g.kitchen_id)
    )
    if not kitchens:
        raise Forbidden
    return kitchens


def list_versions(principal: Principal) -> list[dict[str, object]]:
    kitchens = _kitchens(principal)
    with get_engine().connect() as conn:
        rows = (
            conn.execute(
                text("""
                SELECT v.id, d.doc_id, d.display_name, v.doc_version, v.content_sha256,
                       v.status, c.kitchen_id, v.submitted_at, v.approved_by, v.approved_at,
                       v.decision_reason
                FROM app.knowledge_document_versions v
                JOIN app.knowledge_documents d ON d.id = v.document_id
                JOIN kitchen_rag.chunks c ON c.doc_id = d.doc_id
                    AND c.content_sha256 = v.content_sha256
                WHERE c.kitchen_id = ANY(:kitchens)
                GROUP BY v.id, d.doc_id, d.display_name, v.doc_version, v.content_sha256,
                         v.status, c.kitchen_id, v.submitted_at, v.approved_by, v.approved_at,
                         v.decision_reason
                ORDER BY v.submitted_at DESC, v.id
            """),
                {"kitchens": list(kitchens)},
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


def _version_kitchen(conn: Connection, principal: Principal, version_id: uuid.UUID) -> uuid.UUID:
    allowed = set(_kitchens(principal))
    row = conn.execute(
        text("""
            SELECT c.kitchen_id
            FROM app.knowledge_document_versions v
            JOIN app.knowledge_documents d ON d.id = v.document_id
            JOIN kitchen_rag.chunks c ON c.doc_id = d.doc_id
                AND c.content_sha256 = v.content_sha256
            WHERE v.id = :id AND c.kitchen_id = ANY(:kitchens)
            ORDER BY c.kitchen_id
            LIMIT 1
        """),
        {"id": version_id, "kitchens": list(allowed)},
    ).scalar_one_or_none()
    if row is None:
        raise NotFound
    return cast(uuid.UUID, row)


def decide(principal: Principal, version_id: uuid.UUID, *, approve: bool, reason: str) -> dict[str, object]:
    if len(reason.strip()) < 3:
        raise Conflict("A reason of 3 to 500 characters is required")
    with get_engine().begin() as conn:
        kitchen_id = _version_kitchen(conn, principal, version_id)
        fn = "app.approve_kitchen_knowledge" if approve else "app.reject_kitchen_knowledge"
        try:
            conn.execute(
                text(f"SELECT {fn}(:version, :actor, :kitchen, :reason)"),
                {
                    "version": version_id,
                    "actor": principal.user_id,
                    "kitchen": kitchen_id,
                    "reason": reason.strip(),
                },
            )
        except Exception as exc:
            if "not draft" in str(exc):
                raise Conflict("Knowledge version is no longer a draft") from exc
            raise
        row = (
            conn.execute(
                text("""
                SELECT v.id, d.doc_id, d.display_name, v.doc_version, v.content_sha256,
                       v.status, :kitchen AS kitchen_id, v.submitted_at, v.approved_by,
                       v.approved_at, v.decision_reason
                FROM app.knowledge_document_versions v
                JOIN app.knowledge_documents d ON d.id = v.document_id
                WHERE v.id = :version
            """),
                {"version": version_id, "kitchen": kitchen_id},
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise NotFound
    return dict(row)


def golden_set(principal: Principal) -> dict[str, object]:
    _kitchens(principal)
    with get_engine().connect() as conn:
        row = (
            conn.execute(
                text("""
                SELECT id, suite, portal, name, approval_label, case_count, leak_count, status,
                       dataset_hash, approved_by, approved_at, decision_reason
                FROM ops.ai_golden_sets
                WHERE suite = 'DDR-90' AND portal = 'KITCHEN'
                ORDER BY created_at DESC, id
                LIMIT 1
            """)
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise NotFound
    return dict(row)


def approve_golden_set(principal: Principal, set_id: uuid.UUID, reason: str) -> dict[str, object]:
    _kitchens(principal)
    if len(reason.strip()) < 3:
        raise Conflict("A reason of 3 to 500 characters is required")
    with get_engine().begin() as conn:
        try:
            conn.execute(
                text("SELECT app.approve_kitchen_golden_set(:set_id, :actor, :reason)"),
                {"set_id": set_id, "actor": principal.user_id, "reason": reason.strip()},
            )
        except Exception as exc:
            if "golden set" in str(exc):
                raise Conflict(str(exc).split("CONTEXT", 1)[0].strip()) from exc
            raise
        row = (
            conn.execute(
                text("""
                SELECT id, suite, portal, name, approval_label, case_count, leak_count, status,
                       dataset_hash, approved_by, approved_at, decision_reason
                FROM ops.ai_golden_sets WHERE id = :set_id
            """),
                {"set_id": set_id},
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise NotFound
    return dict(row)
