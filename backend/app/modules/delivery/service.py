"""Delivery assignment at kitchen acceptance (DDR-51, DDR-111 (6); #7 §3).

Runs in the caller's transaction (kitchen acceptance or rejection in the orders service), with the
caller's actor context. Assignment never changes the order's fulfilment status (DDR-16, DDR-17).
The agent's response, the 60-second timeout, the pool and online/offline come with Task 9.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.modules.delivery import domain as d
from app.modules.delivery import repository as repo

LiveAssignment = repo.LiveAssignment


def offer_on_acceptance(conn: Connection, order_id: uuid.UUID, region_id: uuid.UUID) -> LiveAssignment | None:
    """Offer the order to one eligible agent. None when no agent qualifies ("Awaiting agent")."""
    agent = repo.eligible_agent(conn, region_id)
    if agent is None:
        return None
    try:
        with conn.begin_nested():
            repo.insert_offer(conn, order_id, agent)
    except IntegrityError as exc:
        # Another acceptance offered this agent first (one live assignment per agent): no offer now.
        if "delivery_assignments_one_live_per_agent_uq" not in str(exc.orig):
            raise
        return None
    return repo.live(conn, [order_id]).get(order_id)


def revoke(conn: Connection, order_id: uuid.UUID) -> bool:
    """Revoke the order's live offer or assignment (DL-07). The caller's actor context holds the reason."""
    current = repo.live(conn, [order_id], lock=True).get(order_id)
    if current is None:
        return False
    if not d.can_transition(d.Assignment(current.status), d.Assignment.REVOKED):
        return False  # a failure request stays with the manager (DA-18)
    repo.set_status(conn, current.assignment_id, d.Assignment.REVOKED.value)
    return True


def live_for(conn: Connection, order_ids: list[uuid.UUID]) -> dict[uuid.UUID, LiveAssignment]:
    return repo.live(conn, order_ids) if order_ids else {}
