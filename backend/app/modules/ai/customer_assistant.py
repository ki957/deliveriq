"""Customer Assistant orchestration: public/customer scope, read-only tools and Prompt Guard."""

from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.ai import gateway
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.permissions import Principal, Role
from app.modules.ai.customer_rag import retrieve

HARNESS = "customer_assistant"
PROMPT_PATH = Path(__file__).with_name("customer_assistant").joinpath("prompt.md")


class Invalid(Exception):
    pass


class NotFound(Exception):
    pass


class Forbidden(Exception):
    pass


def _guard(question: str) -> tuple[bool, str]:
    if not get_settings().ai_prompt_guard_enabled:
        return False, "off"
    # The mock classifier is deterministic in local/test; a classifier outage is non-blocking.
    try:
        flagged, _model = gateway.classify("customer_assistant", question, "guard")
        return flagged, "blocked" if flagged else "clear"
    except Exception:
        return False, "unavailable"


def _public_live_context(question: str, principal: Principal | None) -> str:
    """Read-only live facts. SQL is deliberately limited to public menu and own-order data."""
    with get_engine().connect() as conn:
        menu = (
            conn.execute(
                text("""
                SELECT name, price_paise, publication_status FROM app.menu_items
                WHERE publication_status IN ('PUBLISHED', 'TEMPORARILY_UNAVAILABLE')
                  AND is_test_fixture=false ORDER BY name LIMIT 20
        """)
            )
            .mappings()
            .all()
        )
        orders: list[Any] = []
        if principal and Role.CUSTOMER in principal.roles:
            orders = list(
                conn.execute(
                    text("""
                SELECT id, fulfilment_status FROM app.orders
                WHERE customer_user_id=:customer AND is_test_fixture=false ORDER BY placed_at DESC LIMIT 10
            """),
                    {"customer": principal.user_id},
                )
                .mappings()
                .all()
            )
    facts = [
        f"menu:{r['name']} price_paise={r['price_paise']} "
        f"availability={'available' if r['publication_status'] == 'PUBLISHED' else 'unavailable'} "
        f"status={r['publication_status']}"
        for r in menu
    ]
    facts += [f"own_order:{r['id']} status={r['fulfilment_status']}" for r in orders]
    return "\n".join(facts[:30])


def _prompt() -> tuple[str, str]:
    content = PROMPT_PATH.read_text(encoding="utf-8")
    return content, hashlib.sha256(content.encode("utf-8")).hexdigest()


def _record_guard_event(principal: Principal | None, status: str) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text("""
                INSERT INTO ops.prompt_guard_events (user_id, harness, outcome)
                VALUES (:user_id, :harness, :outcome)
            """),
            {
                "user_id": principal.user_id if principal and Role.CUSTOMER in principal.roles else None,
                "harness": HARNESS,
                "outcome": status,
            },
        )


def ask(
    principal: Principal | None, question: str, conversation_id: uuid.UUID | None
) -> tuple[str, list[str], str, str | None, str]:
    if principal is not None and Role.CUSTOMER not in principal.roles:
        raise Forbidden
    owner = principal.user_id if principal and Role.CUSTOMER in principal.roles else None
    if conversation_id is not None:
        if owner is None:
            raise NotFound
        with get_engine().connect() as conn:
            owned = conn.execute(
                text("""
                    SELECT 1 FROM app.ai_conversations
                    WHERE id=:id AND user_id=:user_id AND deleted_at IS NULL
                """),
                {"id": conversation_id, "user_id": owner},
            ).first()
        if owned is None:
            raise NotFound
    flagged, guard_status = _guard(question)
    _record_guard_event(principal, guard_status)
    if flagged:
        return (
            "I can help with DeliverIQ menu, delivery and support questions, but I cannot "
            "follow that instruction.",
            [],
            "guarded",
            None,
            guard_status,
        )
    chunks = retrieve(question, principal)
    citations = [chunk.source_ref for chunk in chunks]
    facts = _public_live_context(question, principal)
    prompt, prompt_sha256 = _prompt()
    messages = [
        {
            "role": "system",
            "content": prompt
            + "\nFor current price, availability, order status, and delivery quotes, use live read-tool "
            "facts only; never take these changing facts from Customer RAG.",
        },
        {
            "role": "user",
            "content": question
            + "\n\nCustomer sources:\n"
            + "\n".join(f"[{i + 1}] {c.content}" for i, c in enumerate(chunks))
            + "\n\nLive read-only facts:\n"
            + facts,
        },
    ]
    start = time.monotonic()
    answer, model = gateway.complete(HARNESS, messages)
    with get_engine().begin() as conn:
        if owner is not None:
            if conversation_id is None:
                conversation_id = conn.execute(
                    text("INSERT INTO app.ai_conversations (user_id) VALUES (:u) RETURNING id"), {"u": owner}
                ).scalar_one()
            elif (
                conn.execute(
                    text(
                        "SELECT 1 FROM app.ai_conversations WHERE id=:id AND user_id=:u "
                        "AND deleted_at IS NULL"
                    ),
                    {"id": conversation_id, "u": owner},
                ).first()
                is None
            ):
                raise NotFound
            conn.execute(
                text(
                    "INSERT INTO app.ai_messages (conversation_id, role, content) "
                    "VALUES (:id,'user',:q),(:id,'assistant',:a)"
                ),
                {"id": conversation_id, "q": question, "a": answer},
            )
        if owner is not None:
            conn.execute(
                text(
                    "INSERT INTO ops.ai_requests "
                    "(user_id, harness, logical_model, outcome, latency_ms, prompt_sha256) "
                    "VALUES (:u,:h,:m,'success',:lat,:prompt_sha256)"
                ),
                {
                    "u": owner,
                    "h": HARNESS,
                    "m": model,
                    "lat": int((time.monotonic() - start) * 1000),
                    "prompt_sha256": prompt_sha256,
                },
            )
    return (
        answer,
        citations,
        "hybrid" if chunks else "reduced retrieval",
        str(conversation_id) if conversation_id else None,
        guard_status,
    )
