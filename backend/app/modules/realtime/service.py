"""Subscription checks (DDR-115 (5); PL-06, ADR-006): the same scope rules as the REST views.

Sync like every service (DDR-82); the socket layer calls these through the threadpool.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text

from app.core.db import get_engine
from app.core.permissions import Permission, Principal, Role, can
from app.modules.identity import service as identity
from app.modules.pipelines import service as pipelines
from app.modules.realtime.domain import Topic

P = Permission


@dataclass(frozen=True)
class Access:
    """Granted. `regions` filters pipeline hints: None = every run (CA), else own-region runs (RM)."""

    regions: frozenset[uuid.UUID] | None = None


def _scalar(sql: str, ref: uuid.UUID) -> uuid.UUID | None:
    with get_engine().connect() as conn:
        value: uuid.UUID | None = conn.execute(text(sql), {"id": ref}).scalar_one_or_none()
        return value


def authorize(principal: Principal, topic: Topic) -> Access | None:
    """None = refused. Anything unknown or out of scope is refused (deny by default)."""
    match topic.kind:
        case "order" if topic.ref is not None:
            customer = _scalar("SELECT customer_user_id FROM app.orders WHERE id = :id", topic.ref)
            ok = customer is not None and can(principal, P.CUSTOMER_ORDERS_READ, customer_id=customer)
            return Access() if ok else None
        case "kitchen" if topic.ref is not None:
            region = _scalar("SELECT region_id FROM app.kitchens WHERE id = :id", topic.ref)
            if region is None:
                return None
            ok = can(principal, P.KITCHEN_ORDERS_VIEW, kitchen_id=topic.ref) or can(
                principal, P.MGMT_OPERATIONS_VIEW, region_id=region
            )
            return Access() if ok else None
        case "region" if topic.ref is not None:
            exists = _scalar("SELECT id FROM app.regions WHERE id = :id", topic.ref)
            ok = exists is not None and can(principal, P.MGMT_OPERATIONS_VIEW, region_id=topic.ref)
            return Access() if ok else None
        case "agent" if topic.ref == principal.user_id:
            # Only the agent's own topic; parse_topic never builds another agent's.
            ok = any(
                g.role == Role.DELIVERY_AGENT
                and can(principal, P.DELIVERY_ASSIGNMENTS_VIEW, region_id=g.region_id)
                for g in principal.grants
            )
            return Access() if ok else None
        case "pipelines":
            try:
                return Access(pipelines.view_scope(principal))
            except pipelines.Forbidden:
                return None
    return None


def principal(session_token: str, *, touch: bool) -> Principal | None:
    """The live principal of a session; re-validation does not extend the idle timeout (touch=False)."""
    return identity.principal_for_session(session_token, touch=touch)
