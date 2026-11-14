"""Notifications and retention purges over the real stack (plan Task 11; DDR-115 (10)–(12)).

Needs the core stack and fixtures. Rows are written by the migration 0013 triggers, whoever makes the
change; the API shows a person only their own. Uses the identity world and the management team (cleanup).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

import psycopg
import pytest

from app.modules.identity.tests.test_auth_integration import World, login
from app.modules.management.tests.test_management_integration import KITCHEN, Team, prepaid_order, user_id

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

N = "/api/v1/me/notifications"
DELIVERY = "/api/v1/delivery"


def kinds_for(box: dict[str, Any], order_id: str) -> list[str]:
    return [r["kind"] for r in box["rows"] if r["order_id"] == order_id]


@contextmanager
def as_worker() -> Iterator[psycopg.Connection[tuple[Any, ...]]]:
    with psycopg.connect(
        host="127.0.0.1", port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")), dbname=os.environ["POSTGRES_DB"],
        user="worker", password=os.environ["WORKER_PASSWORD"], autocommit=True,
    ) as worker:  # fmt: skip
        yield worker


def test_the_customer_gets_order_lifecycle_notifications_and_only_their_own(world: World, team: Team) -> None:
    order_id = prepaid_order(world, team)
    assert team.km.post(f"{KITCHEN}/{order_id}/accept").status_code == 200
    box = team.customer.get(N).json()
    assert "order.accepted" in kinds_for(box, order_id)
    assert box["sms"] == "Not configured (DDR-40)" and box["history_days"] == 30
    assert box["unread"] >= 1
    first = next(r for r in box["rows"] if r["order_id"] == order_id)
    assert first["is_test_fixture"] is True and set(first) == {
        "id", "kind", "order_id", "ingredient_name", "is_test_fixture", "created_at", "read_at",
    }  # fmt: skip

    # Nobody else sees it, and nobody else can mark it read.
    stranger = login(world.user("CUSTOMER"), "customer")
    assert kinds_for(stranger.get(N).json(), order_id) == []
    assert stranger.post(f"{N}/read", json={"ids": [first["id"]]}).status_code == 204
    assert next(r for r in team.customer.get(N).json()["rows"] if r["id"] == first["id"])["read_at"] is None
    stranger.close()

    assert team.customer.post(f"{N}/read", json={"ids": [first["id"]]}).status_code == 204
    assert (
        next(r for r in team.customer.get(N).json()["rows"] if r["id"] == first["id"])["read_at"] is not None
    )
    assert team.customer.post(f"{N}/read", json={}).status_code == 204
    assert team.customer.get(N).json()["unread"] == 0
    assert team.customer.post(f"{N}/read", json={}, headers={"X-DeliverIQ-CSRF": ""}).status_code == 403


def test_the_agent_hears_of_an_offer_and_its_withdrawal(world: World, team: Team) -> None:
    mobile = world.user("DELIVERY_AGENT", region=world.region_a)
    agent = login(mobile, "delivery")
    agent_id = user_id(world, mobile)
    assert agent.put(f"{DELIVERY}/me/availability", json={"online": True}).status_code == 200
    for _ in range(10):  # decline orders already waiting (going online picks one up, DL-01)
        waiting = agent.get(f"{DELIVERY}/me").json()["assignment"]
        if not waiting:
            break
        agent.post(
            f"{DELIVERY}/assignments/{waiting['id']}/respond", json={"accept": False, "reason": "Test"}
        )
    order_id = prepaid_order(world, team)
    assert team.km.post(f"{KITCHEN}/{order_id}/accept").status_code == 200
    mine = agent.get(f"{DELIVERY}/me").json()
    if not (mine["order"] and mine["order"]["order_id"] == order_id):
        r = team.rm.post(
            f"{DELIVERY}/manage/orders/{order_id}/assign",
            json={"agent_user_id": str(agent_id), "reason": "Test"},
        )
        assert r.status_code == 200, r.text
    assert "delivery.offered" in kinds_for(agent.get(N).json(), order_id)
    # The kitchen cannot fulfil it: the offer is withdrawn, and the customer hears it was rejected.
    assert team.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Test"}).status_code == 200
    assert "delivery.withdrawn" in kinds_for(agent.get(N).json(), order_id)
    assert "order.rejected" in kinds_for(team.customer.get(N).json(), order_id)
    agent.put(f"{DELIVERY}/me/availability", json={"online": False})
    agent.close()


def test_the_kitchen_manager_hears_when_stock_falls_to_its_threshold(world: World, team: Team) -> None:
    row = world.db.execute(
        "SELECT s.ingredient_id, s.low_stock_threshold, s.on_hand - s.reserved, i.name FROM app.ingredient_stock s "
        "JOIN app.ingredients i ON i.id = s.ingredient_id WHERE s.kitchen_id = %s AND s.is_test_fixture "
        "ORDER BY i.name LIMIT 1",
        (world.kitchen_a,),
    ).fetchone()
    assert row is not None, "run `make fixtures`"
    ingredient, old, available, name = row
    assert isinstance(available, Decimal)
    try:
        # Below the threshold → one notification; another update while still low → none.
        world.db.execute("UPDATE app.ingredient_stock SET low_stock_threshold = %s WHERE kitchen_id = %s "
                         "AND ingredient_id = %s", (available + 1, world.kitchen_a, ingredient))  # fmt: skip
        world.db.execute("UPDATE app.ingredient_stock SET updated_at = now() WHERE kitchen_id = %s "
                         "AND ingredient_id = %s", (world.kitchen_a, ingredient))  # fmt: skip
        lows = [
            r
            for r in team.km.get(N).json()["rows"]
            if r["kind"] == "stock.low" and r["ingredient_name"] == name
        ]
        assert len(lows) == 1 and lows[0]["order_id"] is None
        assert all(r["kind"] != "stock.low" for r in team.ks.get(N).json()["rows"])  # KM only (KI-23)
    finally:
        world.db.execute("UPDATE app.ingredient_stock SET low_stock_threshold = %s WHERE kitchen_id = %s "
                         "AND ingredient_id = %s", (old, world.kitchen_a, ingredient))  # fmt: skip
        world.db.execute("DELETE FROM app.notifications WHERE kind = 'stock.low' AND ingredient_id = %s "
                         "AND created_at > now() - interval '1 hour'", (ingredient,))  # fmt: skip


def test_purges_keep_day_29_delete_day_31_and_run_as_the_worker(world: World, team: Team) -> None:
    mobile = world.user("CUSTOMER")
    person = user_id(world, mobile)
    order_id = prepaid_order(world, team)
    notes = [
        world.db.execute(
            "INSERT INTO app.notifications (user_id, kind, order_id, created_at) "
            "VALUES (%s, 'order.accepted', %s, now() - make_interval(days => %s)) RETURNING id",
            (person, order_id, days),
        ).fetchone()[0]  # type: ignore[index]
        for days in (29, 31)
    ]
    otps = [
        world.db.execute(
            "INSERT INTO app.otp_challenges (mobile_e164, portal, code_hash, max_attempts, expires_at, created_at) "
            "VALUES (%s, 'customer', repeat('0', 64), 5, now() - make_interval(days => %s), "
            "now() - make_interval(days => %s)) RETURNING id",
            (mobile, days, days),
        ).fetchone()[0]  # type: ignore[index]
        for days in (29, 31)
    ]
    sessions = [
        world.db.execute(
            "INSERT INTO app.sessions (user_id, portal, token_hash, created_at, last_seen_at, expires_at, revoked_at, "
            "revoke_reason) VALUES (%s, 'customer', %s, now() - make_interval(days => %s), "
            "now() - make_interval(days => %s), now() + interval '1 day', now() - make_interval(days => %s), 'test') "
            "RETURNING id",
            (person, uuid.uuid4().hex * 2, days, days, days),
        ).fetchone()[0]  # type: ignore[index]
        for days in (29, 31)
    ]
    with as_worker() as worker:
        assert worker.execute("SELECT app.purge_notifications(30)").fetchone()[0] >= 1  # type: ignore[index]
        purged = worker.execute("SELECT app.purge_auth(30)").fetchone()[0]  # type: ignore[index]
        assert purged["otp_challenges"] >= 1 and purged["sessions"] >= 1
        assert worker.execute("SELECT app.purge_notifications(30)").fetchone()[0] == 0  # type: ignore[index]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            worker.execute("SELECT count(*) FROM app.notifications")
    left = {r[0] for r in world.db.execute("SELECT id FROM app.notifications WHERE id = ANY(%s)", (notes,))}
    assert left == {notes[0]}
    assert {
        r[0] for r in world.db.execute("SELECT id FROM app.otp_challenges WHERE id = ANY(%s)", (otps,))
    } == {otps[0]}
    assert {
        r[0] for r in world.db.execute("SELECT id FROM app.sessions WHERE id = ANY(%s)", (sessions,))
    } == {sessions[0]}
    audited = world.db.execute(
        "SELECT count(*) FROM audit.events WHERE action IN ('notifications.purged', 'auth.records.purged') "
        "AND occurred_at > now() - interval '1 minute'"
    ).fetchone()
    assert audited is not None and isinstance(audited[0], int) and audited[0] >= 2
    world.db.execute("DELETE FROM app.otp_challenges WHERE id = ANY(%s)", (otps,))
    world.db.execute("DELETE FROM app.sessions WHERE id = ANY(%s)", (sessions,))
