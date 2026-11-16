"""AI gateway service; management copilot has no write tools (DDR-119)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from app.ai import gateway
from app.core.db import get_engine
from app.core.permissions import Permission, Principal, Role, can
from app.shared.audit import write_event

P = Permission
HARNESS = "management_copilot"


class Forbidden(Exception):
    pass


class Invalid(Exception):
    pass


class NotFound(Exception):
    pass


@dataclass(frozen=True)
class Status:
    enabled: bool
    knowledge_status: str
    models: list[tuple[str, list[str], bool]]


def _require(principal: Principal, permission: Permission) -> None:
    if not can(principal, permission):
        raise Forbidden


def _require_management_copilot(principal: Principal) -> None:
    """Allow a regional grant to use the read-only copilot within its assigned region."""
    if any(
        can(principal, P.MGMT_AI_COPILOT, region_id=grant.region_id)
        for grant in principal.grants
        if grant.role in {Role.REGIONAL_MANAGER, Role.CENTRAL_ADMIN}
    ):
        return
    raise Forbidden


def status(principal: Principal) -> Status:
    _require_management_copilot(principal)
    catalog = gateway.load_catalog()
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT logical_model FROM ops.ai_routing_overrides WHERE harness = :h"), {"h": HARNESS}
        ).first()
    selected = row.logical_model if row else catalog.harnesses[HARNESS].default_model
    models = [(name, sorted(spec.capabilities), name == selected) for name, spec in catalog.models.items()]
    return Status(gateway.ai_enabled(), "pending approval", models)


def settings(principal: Principal) -> tuple[str, datetime | None]:
    _require(principal, P.MGMT_AI_SETTINGS)
    catalog = gateway.load_catalog()
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT logical_model, updated_at FROM ops.ai_routing_overrides WHERE harness = :h"),
            {"h": HARNESS},
        ).first()
    return (row.logical_model, row.updated_at) if row else (catalog.harnesses[HARNESS].default_model, None)


def set_settings(principal: Principal, logical_model: str, reason: str) -> tuple[str, datetime]:
    _require(principal, P.MGMT_AI_SETTINGS)
    model = gateway.select_model(gateway.load_catalog(), HARNESS, logical_model)
    if model.provider != "mock":
        raise Invalid("The selected provider is not configured")
    with get_engine().begin() as conn:
        conn.execute(
            text("""
            INSERT INTO ops.ai_routing_overrides (harness, logical_model, updated_by, reason)
            VALUES (:h, :m, :u, :reason)
            ON CONFLICT (harness) DO UPDATE SET logical_model = excluded.logical_model,
                updated_by = excluded.updated_by, updated_at = now(), reason = excluded.reason
        """),
            {"h": HARNESS, "m": logical_model, "u": principal.user_id, "reason": reason.strip()},
        )
        row = conn.execute(
            text("SELECT updated_at FROM ops.ai_routing_overrides WHERE harness = :h"), {"h": HARNESS}
        ).one()
        write_event(
            conn,
            action="management.ai.routing_changed",
            actor_user_id=principal.user_id,
            actor_role="CENTRAL_ADMIN",
            target_type="ai_harness",
            target_id=HARNESS,
            correlation_id=None,
            after={"model": logical_model, "reason": reason.strip()},
        )
    return logical_model, row.updated_at


def copilot(
    principal: Principal, question: str, conversation_id: uuid.UUID | None
) -> tuple[str, uuid.UUID, str]:
    _require_management_copilot(principal)
    start = time.monotonic()
    model = settings_for_request(principal)
    with get_engine().begin() as conn:
        if conversation_id is None:
            row = conn.execute(
                text("INSERT INTO app.ai_conversations (user_id) VALUES (:u) RETURNING id"),
                {"u": principal.user_id},
            ).one()
            conversation_id = row.id
        else:
            owned = conn.execute(
                text(
                    "SELECT id FROM app.ai_conversations "
                    "WHERE id = :id AND user_id = :u AND deleted_at IS NULL"
                ),
                {"id": conversation_id, "u": principal.user_id},
            ).first()
            if owned is None:
                raise NotFound
        old = conn.execute(
            text(
                "SELECT role, content FROM app.ai_messages "
                "WHERE conversation_id = :id ORDER BY created_at DESC LIMIT 12"
            ),
            {"id": conversation_id},
        ).all()
        messages = [{"role": r.role, "content": r.content} for r in reversed(old)] + [
            {"role": "user", "content": question}
        ]
        answer, used_model = gateway.complete(HARNESS, messages, model)
        conn.execute(
            text(
                "INSERT INTO app.ai_messages (conversation_id, role, content) "
                "VALUES (:id, 'user', :q), (:id, 'assistant', :a)"
            ),
            {"id": conversation_id, "q": question, "a": answer},
        )
        conn.execute(
            text(
                "DELETE FROM app.ai_messages WHERE conversation_id = :id "
                "AND id NOT IN (SELECT id FROM app.ai_messages "
                "WHERE conversation_id = :id ORDER BY created_at DESC LIMIT 12)"
            ),
            {"id": conversation_id},
        )
        conn.execute(
            text(
                "INSERT INTO ops.ai_requests "
                "(user_id, harness, logical_model, outcome, latency_ms) "
                "VALUES (:u, :h, :m, 'success', :lat)"
            ),
            {
                "u": principal.user_id,
                "h": HARNESS,
                "m": used_model,
                "lat": int((time.monotonic() - start) * 1000),
            },
        )
    return answer, conversation_id, used_model


def settings_for_request(principal: Principal) -> str | None:
    catalog = gateway.load_catalog()
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT logical_model FROM ops.ai_routing_overrides WHERE harness = :h"), {"h": HARNESS}
        ).first()
    return row.logical_model if row else catalog.harnesses[HARNESS].default_model


def delete_conversation(principal: Principal, conversation_id: uuid.UUID) -> None:
    _require_management_copilot(principal)
    with get_engine().begin() as conn:
        result = conn.execute(
            text(
                "UPDATE app.ai_conversations SET deleted_at = now() "
                "WHERE id = :id AND user_id = :u AND deleted_at IS NULL"
            ),
            {"id": conversation_id, "u": principal.user_id},
        )
        if result.rowcount != 1:
            raise NotFound
