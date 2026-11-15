"""CA-only Operational Actions; the model proposes and the backend alone executes (DDR-69, DDR-120)."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.ai import gateway
from app.core.db import get_engine
from app.core.permissions import Permission, Principal, Role, can
from app.modules.ai.actions import mock
from app.modules.delivery import repository as delivery_repo
from app.modules.delivery import service as delivery
from app.modules.kitchen_ops import domain as kitchen_domain
from app.modules.kitchen_ops import service as kitchen
from app.modules.menu import repository as menu_repo
from app.modules.menu import service as menu
from app.shared.audit import write_event

HARNESS = "management_actions"
PROMPT_PATH = Path(__file__).with_name("prompt.md")
ALLOWED = frozenset({"kitchen_settings", "agent_assign", "dish_availability", "menu_publish"})
UNAVAILABLE = ("promotion", "review", "regional setting", "exceptional refund")


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Invalid(Exception):
    pass


class Conflict(Exception):
    pass


def _ca(principal: Principal) -> None:
    if not any(grant.role == Role.CENTRAL_ADMIN for grant in principal.grants) or not can(
        principal, Permission.MGMT_AI_ACTIONS
    ):
        raise Forbidden


def _snapshot(
    action: str, args: dict[str, Any], principal: Principal
) -> tuple[dict[str, Any], dict[str, Any]]:
    if action == "kitchen_settings":
        settings = kitchen.get_settings(principal, uuid.UUID(args["kitchen_id"]))
        before = {
            "mode": settings.kitchen.mode,
            "normal_capacity": int(settings.normal_capacity.value),
            "busy_capacity": int(settings.busy_capacity.value),
        }
        after = {
            "mode": args["mode"],
            "normal_capacity": args["normal_capacity"],
            "busy_capacity": args["busy_capacity"],
        }
        capacity_error = kitchen_domain.capacity_error(args["normal_capacity"], args["busy_capacity"])
        if capacity_error:
            raise Invalid(capacity_error)
        if before == after:
            raise Invalid("The kitchen already has these settings")
        return before, {
            "target": args["kitchen_id"],
            "before": before,
            "after": after,
            "reason": args["reason"],
        }
    with get_engine().connect() as conn:
        if action == "agent_assign":
            order_id = uuid.UUID(args["order_id"])
            row = conn.execute(
                text("SELECT fulfilment_status FROM app.orders WHERE id = :id"), {"id": order_id}
            ).first()
            if row is None:
                raise NotFound
            live = delivery_repo.live_for_order(conn, order_id)
            before = {
                "order_status": row.fulfilment_status,
                "assignment_id": str(live.id) if live else None,
                "assignment_status": live.status if live else None,
                "agent_id": str(live.agent_user_id) if live else None,
            }
            if row.fulfilment_status not in ("ACCEPTED", "PREPARING", "READY_FOR_PICKUP"):
                raise Invalid("Only an order held by the kitchen can be assigned")
            try:
                region = delivery_repo.order_region(conn, order_id)
            except LookupError as exc:
                raise NotFound from exc
            agent_id = uuid.UUID(args["agent_id"])
            if not delivery_repo.is_agent_in_region(conn, agent_id, region):
                raise Invalid("Choose an active agent in this order's region")
            if delivery_repo.availability(conn, agent_id)[0] != "ONLINE":
                raise Invalid("The agent is offline")
            if before["agent_id"] == args["agent_id"] and before["assignment_status"] == "ACCEPTED":
                raise Invalid("The order is already assigned to this agent")
            return before, {
                "target": args["order_id"],
                "before": before,
                "after": {"agent_id": args["agent_id"]},
                "reason": args["reason"],
            }
        if action == "dish_availability":
            request = menu_repo.find_request(conn, uuid.UUID(args["request_id"]))
            if request is None:
                raise NotFound
            if request.status != "PENDING":
                raise Invalid("This request is no longer pending")
            source = "PUBLISHED" if request.kind == "MAKE_UNAVAILABLE" else "TEMPORARILY_UNAVAILABLE"
            if request.publication_status != source:
                raise Invalid("The dish changed since the request")
            before = {
                "request_status": request.status,
                "publication_status": request.publication_status,
                "kind": request.kind,
            }
            target_status = (
                ("TEMPORARILY_UNAVAILABLE" if request.kind == "MAKE_UNAVAILABLE" else "PUBLISHED")
                if args["approve"]
                else request.publication_status
            )
            return before, {
                "target": args["request_id"],
                "dish": request.dish_name,
                "before": before,
                "after": {
                    "decision": "APPROVED" if args["approve"] else "REJECTED",
                    "publication_status": target_status,
                },
                "reason": args["reason"],
            }
        if action == "menu_publish":
            item = menu_repo.find_item(conn, uuid.UUID(args["item_id"]))
            if item is None:
                raise NotFound
            if not item.is_test_fixture:
                raise Invalid("Only TEST menu items can be published through Operational Actions")
            if item.publication_status != "READY_FOR_PUBLICATION":
                raise Invalid("The TEST item must be ready for publication")
            before = {
                "publication_status": item.publication_status,
                "updated_at": item.updated_at.isoformat(),
            }
            return before, {
                "target": args["item_id"],
                "dish": item.name,
                "before": before,
                "after": {"publication_status": "PUBLISHED"},
                "reason": args["reason"],
            }
    raise Invalid("Action is not allowlisted")


def propose(principal: Principal, request: str) -> dict[str, Any]:
    _ca(principal)
    if not gateway.ai_enabled():
        raise Invalid("Operational Actions are unavailable in this environment")
    try:
        parsed, used_model = gateway.structured_proposal(HARNESS, request, mock.propose)
    except gateway.GatewayError as exc:
        raise Invalid(str(exc)) from exc
    prompt_hash = hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()
    if parsed is None:
        lowered = request.lower()
        if any(term in lowered for term in UNAVAILABLE):
            response = "This action is unavailable until its rules and UI service are approved."
            status = "unavailable"
        elif re.search(r"\b(kitchen|assign|availability|publish)\b", lowered):
            response = (
                "Please include the exact UUIDs, values and a reason using one supported request format."
            )
            status = "clarification"
        else:
            response = "This request has no allowlisted Operational Actions tool."
            status = "refused"
        with get_engine().begin() as conn:
            conn.execute(
                text("""
                INSERT INTO ops.ai_requests
                (user_id, harness, logical_model, outcome, latency_ms, prompt_sha256)
                VALUES (:u, :h, :m, :o, 0, :p)
            """),
                {
                    "u": principal.user_id,
                    "h": HARNESS,
                    "m": used_model,
                    "o": status,
                    "p": prompt_hash,
                },
            )
        return {
            "status": status,
            "message": response,
            "proposal_id": None,
            "action": None,
            "exact_change": None,
            "simulated": True,
        }
    if parsed.action not in ALLOWED:
        raise Invalid("Action is not allowlisted")
    args = parsed.arguments
    if not args.get("reason"):
        raise Invalid("A reason is required")
    try:
        before, change = _snapshot(parsed.action, args, principal)
    except (kitchen.NotFound, menu.NotFound, delivery.NotFound) as exc:
        raise NotFound from exc
    except (
        kitchen.Invalid,
        kitchen.MissingSetting,
        menu.Invalid,
        menu.Conflict,
        delivery.Invalid,
        delivery.Conflict,
    ) as exc:
        raise Invalid(str(exc)) from exc
    with get_engine().begin() as conn:
        row = conn.execute(
            text("""
            INSERT INTO ops.action_proposals (user_id, action, arguments, before_state, exact_change)
            VALUES (:u, :a, CAST(:args AS jsonb), CAST(:before AS jsonb), CAST(:change AS jsonb))
            RETURNING id
        """),
            {
                "u": principal.user_id,
                "a": parsed.action,
                "args": json.dumps(args),
                "before": json.dumps(before),
                "change": json.dumps(change),
            },
        ).one()
        conn.execute(
            text("""
            INSERT INTO ops.ai_requests (user_id, harness, logical_model, outcome, latency_ms, prompt_sha256)
            VALUES (:u, :h, :m, 'proposed', 0, :p)
        """),
            {"u": principal.user_id, "h": HARNESS, "m": used_model, "p": prompt_hash},
        )
    return {
        "status": "proposed",
        "message": parsed.summary,
        "proposal_id": row.id,
        "action": parsed.action,
        "exact_change": change,
        "simulated": True,
    }


def _execute(
    principal: Principal, action: str, args: dict[str, Any], before: dict[str, Any]
) -> dict[str, Any]:
    if action == "kitchen_settings":
        kitchen_result = kitchen.update_settings(
            principal,
            uuid.UUID(args["kitchen_id"]),
            mode=kitchen_domain.KitchenMode(args["mode"]),
            normal_capacity=args["normal_capacity"],
            busy_capacity=args["busy_capacity"],
            reason=args["reason"],
            expected=before,
        )
        return {"kitchen_id": str(kitchen_result.kitchen.id), "mode": kitchen_result.kitchen.mode}
    if action == "agent_assign":
        delivery_result = delivery.manager_assign(
            principal, uuid.UUID(args["order_id"]), uuid.UUID(args["agent_id"]), args["reason"]
        )
        return {
            "order_id": str(delivery_result.order_id),
            "assignment_id": str(delivery_result.assignment_id),
        }
    if action == "dish_availability":
        availability_result = menu.decide_availability(
            principal, uuid.UUID(args["request_id"]), approve=args["approve"], reason=args["reason"]
        )
        return {"request_id": str(availability_result.id), "status": availability_result.status}
    if action == "menu_publish":
        item_result = menu.transition(
            principal, uuid.UUID(args["item_id"]), "publish", args["reason"], expected=before
        )
        return {"item_id": str(item_result.id), "publication_status": item_result.publication_status}
    raise Invalid("Action is not allowlisted")


def confirm(principal: Principal, proposal_id: uuid.UUID, key: uuid.UUID) -> dict[str, Any]:
    _ca(principal)
    with get_engine().begin() as conn:
        row = conn.execute(
            text("""
            SELECT action, arguments, before_state, status, idempotency_key, payload_hash, result
            FROM ops.action_proposals WHERE id = :id AND user_id = :u FOR UPDATE
        """),
            {"id": proposal_id, "u": principal.user_id},
        ).first()
        if row is None:
            raise NotFound
        digest = hashlib.sha256(
            json.dumps({"action": row.action, "arguments": row.arguments}, sort_keys=True).encode()
        ).hexdigest()
        if row.status == "COMPLETED":
            if row.idempotency_key != key or row.payload_hash != digest:
                raise Conflict("The confirmation key was already used for different content")
            return dict(row.result)
        if row.status == "EXECUTING":
            raise Conflict("This action is already executing; check the audit log")
        if row.action not in ALLOWED:
            raise Forbidden
        try:
            before, _ = _snapshot(row.action, row.arguments, principal)
        except (kitchen.NotFound, menu.NotFound, delivery.NotFound) as exc:
            raise Conflict("The target changed; request a fresh proposal") from exc
        except (
            Invalid,
            kitchen.Invalid,
            kitchen.MissingSetting,
            menu.Invalid,
            menu.Conflict,
            delivery.Invalid,
            delivery.Conflict,
        ) as exc:
            raise Conflict("The target changed; request a fresh proposal") from exc
        if before != row.before_state:
            raise Conflict("The target changed; request a fresh proposal")
        try:
            conn.execute(
                text("""
                UPDATE ops.action_proposals SET status = 'EXECUTING', idempotency_key = :k, payload_hash = :h
                WHERE id = :id
            """),
                {"k": key, "h": digest, "id": proposal_id},
            )
        except IntegrityError as exc:
            raise Conflict("The confirmation key was already used") from exc
    try:
        result = _execute(principal, row.action, row.arguments, row.before_state)
    except (kitchen.NotFound, menu.NotFound, delivery.NotFound):
        error: Exception = NotFound()
    except (kitchen.Invalid, kitchen.MissingSetting, menu.Invalid, delivery.Invalid) as exc:
        error = Invalid(str(exc))
    except (menu.Conflict, delivery.Conflict) as exc:
        error = Conflict(str(exc))
    else:
        with get_engine().begin() as conn:
            conn.execute(
                text("""
                UPDATE ops.action_proposals SET status = 'COMPLETED',
                    result = CAST(:r AS jsonb), completed_at = now()
                WHERE id = :id AND user_id = :u AND status = 'EXECUTING'
            """),
                {"r": json.dumps(result), "id": proposal_id, "u": principal.user_id},
            )
            write_event(
                conn,
                action="management.ai.action.confirmed",
                actor_user_id=principal.user_id,
                actor_role="CENTRAL_ADMIN",
                target_type=row.action,
                target_id=str(proposal_id),
                correlation_id=None,
                after={"action": row.action, "result": result},
            )
        return result
    with get_engine().begin() as conn:
        conn.execute(
            text("""
            UPDATE ops.action_proposals SET status = 'PROPOSED', idempotency_key = NULL, payload_hash = NULL
            WHERE id = :id AND user_id = :u AND status = 'EXECUTING'
        """),
            {"id": proposal_id, "u": principal.user_id},
        )
    raise error
