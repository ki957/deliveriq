"""Realtime over the real stack: Postgres trigger → API listener → Redis → socket (plan Task 11; DDR-115).

Needs the core stack and fixtures. Uses the identity world (second region and kitchen) and the
management team (RM per region, CA, kitchen staff, customer); TEST orders are cleaned up by `team`.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import ClientConnection, connect

from app.modules.identity.tests.test_auth_integration import API, World, login
from app.modules.management.tests.test_management_integration import KITCHEN, M, Team, prepaid_order, user_id

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

WS = API.replace("http", "ws", 1) + "/api/v1/realtime"
DELIVERY = "/api/v1/delivery"
Frame = dict[str, Any]


@contextmanager
def socket(c: httpx.Client | None, *, origin: str = API) -> Iterator[ClientConnection]:
    headers = {"Origin": origin}
    if c is not None:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in c.cookies.items())
    with connect(WS, additional_headers=headers, open_timeout=5) as ws:
        yield ws


def ready(ws: ClientConnection) -> None:
    assert json.loads(ws.recv(timeout=3)) == {"type": "ready"}


def subscribe(ws: ClientConnection, *topics: str) -> dict[str, str]:
    ws.send(json.dumps({"type": "subscribe", "topics": list(topics)}))
    out: dict[str, str] = {}
    while len(out) < len(topics):
        frame = json.loads(ws.recv(timeout=3))
        if frame.get("type") in ("subscribed", "denied"):
            out[frame["topic"]] = frame["type"]
    return out


def wait_for(ws: ClientConnection, match: Callable[[Frame], bool], timeout: float = 3.0) -> Frame | None:
    end = time.monotonic() + timeout
    while (left := end - time.monotonic()) > 0:
        try:
            frame: Frame = json.loads(ws.recv(timeout=left))
        except TimeoutError:
            return None
        if match(frame):
            return frame
    return None


def hint_for(topic: str, ref: str) -> Callable[[Frame], bool]:
    return lambda f: f.get("topic") == topic and f.get("id") == ref


def closed_with(ws: ClientConnection, timeout: float = 2.0) -> int | None:
    end = time.monotonic() + timeout
    try:
        while time.monotonic() < end:
            ws.recv(timeout=max(end - time.monotonic(), 0.01))
    except ConnectionClosed:
        return ws.close_code
    except TimeoutError:
        return None
    return None


# ---------------------------------------------------------------- authentication (DDR-115 (6))
def test_sockets_need_a_session_and_this_app_as_origin(team: Team) -> None:
    with socket(None) as ws:
        assert closed_with(ws) == 4401
    with pytest.raises(InvalidStatus), socket(team.rm, origin="https://evil.example"):
        pass
    with pytest.raises(InvalidStatus), socket(team.rm, origin=""):
        pass
    with socket(team.rm) as ws:
        ready(ws)


# ---------------------------------------------------------------- subscriptions (DDR-115 (5); DDR-114 (13))
def test_subscriptions_follow_the_rest_scope(world: World, team: Team) -> None:
    order_id = prepaid_order(world, team)
    stranger = login(world.user("CUSTOMER"), "customer")
    a, b, ka, kb = world.region_a, world.region_b, world.kitchen_a, world.kitchen_b
    cases: list[tuple[httpx.Client, dict[str, str]]] = [
        (team.customer, {f"order:{order_id}": "subscribed", f"kitchen:{ka}": "denied", f"region:{a}": "denied"}),
        (stranger, {f"order:{order_id}": "denied", "agent:me": "denied", "pipelines": "denied"}),
        (team.ks, {f"kitchen:{ka}": "subscribed", f"kitchen:{kb}": "denied", f"region:{a}": "denied",
                   f"order:{order_id}": "denied"}),
        (team.rm, {f"region:{a}": "subscribed", f"kitchen:{ka}": "subscribed", f"region:{b}": "denied",
                   f"kitchen:{kb}": "denied", "pipelines": "subscribed"}),
        (team.other_rm, {f"region:{a}": "denied", f"kitchen:{ka}": "denied", f"region:{b}": "subscribed"}),
        (team.ca, {f"region:{a}": "subscribed", f"region:{b}": "subscribed", f"kitchen:{kb}": "subscribed",
                   "pipelines": "subscribed", f"order:{order_id}": "denied"}),
    ]  # fmt: skip
    for client, expected in cases:
        with socket(client) as ws:
            ready(ws)
            assert subscribe(ws, *expected) == expected
    with socket(team.rm) as ws:
        ready(ws)
        someone = uuid.uuid4()  # never another agent's topic, whatever the id
        assert subscribe(ws, f"agent:{someone}", "order:x", "nope") == {
            f"agent:{someone}": "denied",
            "order:x": "denied",
            "nope": "denied",
        }
    stranger.close()


# ---------------------------------------------------------------- hints (DDR-115 (4); criteria 5–7)
def test_order_changes_arrive_as_bare_hints_and_the_kitchen_hears_nothing_before_payment(
    world: World, team: Team
) -> None:
    row = world.db.execute(
        "SELECT id, price_paise FROM app.menu_items WHERE name = 'TEST – Synthetic Dish A'"
    ).fetchone()
    assert row is not None
    with socket(team.ks) as kitchen, socket(team.rm) as manager:
        ready(kitchen)
        ready(manager)
        subscribe(kitchen, f"kitchen:{world.kitchen_a}")
        subscribe(manager, f"region:{world.region_a}")
        placed = team.customer.post(
            "/api/v1/orders",
            json={"lines": [{"menu_item_id": str(row[0]), "quantity": 5, "unit_price_paise": row[1]}],
                  "payment_method": "SIM_UPI", "address_id": team.address},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )  # fmt: skip
        order_id = str(placed.json()["id"])
        assert wait_for(manager, hint_for(f"region:{world.region_a}", order_id)) is not None
        assert wait_for(kitchen, hint_for(f"kitchen:{world.kitchen_a}", order_id), timeout=1.5) is None

        with socket(team.customer) as customer:
            ready(customer)
            subscribe(customer, f"order:{order_id}")
            team.customer.post(f"/api/v1/orders/{order_id}/payment/simulate", json={"outcome": "SUCCESS"})
            seen = wait_for(kitchen, hint_for(f"kitchen:{world.kitchen_a}", order_id))
            assert seen is not None and set(seen) == {"topic", "kind", "id"}
            assert team.km.post(f"{KITCHEN}/{order_id}/accept").status_code == 200
            mine = wait_for(customer, hint_for(f"order:{order_id}", order_id))
            assert mine is not None and set(mine) == {"topic", "kind", "id"}
    # The REST view (not the hint) carries the canonical label.
    assert team.customer.get(f"/api/v1/orders/{order_id}").json()["status_label"] == "Accepted"


def test_agent_assigned_reaches_the_customer_without_changing_the_fulfilment_label(
    world: World, team: Team
) -> None:
    agent_mobile = world.user("DELIVERY_AGENT", region=world.region_a)
    agent = login(agent_mobile, "delivery")
    agent_id = user_id(world, agent_mobile)
    assert agent.put(f"{DELIVERY}/me/availability", json={"online": True}).status_code == 200
    # Going online picks up an order already waiting (DL-01); decline those so this test's order is next.
    for _ in range(10):
        waiting = agent.get(f"{DELIVERY}/me").json()["assignment"]
        if not waiting:
            break
        agent.post(
            f"{DELIVERY}/assignments/{waiting['id']}/respond",
            json={"accept": False, "reason": "Test: waiting for another order"},
        )
    order_id = prepaid_order(world, team)
    with socket(agent) as a, socket(team.customer) as customer:
        ready(a)
        ready(customer)
        assert subscribe(a, "agent:me") == {"agent:me": "subscribed"}
        subscribe(customer, f"order:{order_id}")
        assert team.km.post(f"{KITCHEN}/{order_id}/accept").status_code == 200
        # Acceptance offers it to an online agent; if another agent of the shared region got it, a manager
        # reassigns it to this one (DDR-113 (5)).
        mine = agent.get(f"{DELIVERY}/me").json()
        if not (mine["order"] and mine["order"]["order_id"] == order_id):
            assign = team.rm.post(
                f"{DELIVERY}/manage/orders/{order_id}/assign",
                json={"agent_user_id": str(agent_id), "reason": "Test"},
            )
            assert assign.status_code == 200, assign.text
        offer = wait_for(a, lambda f: f.get("topic") == "agent:me" and f.get("kind") == "assignment")
        assert offer is not None and offer["id"] == order_id
        me = agent.get(f"{DELIVERY}/me").json()
        r = agent.post(f"{DELIVERY}/assignments/{me['assignment']['id']}/respond", json={"accept": True})
        assert r.status_code == 200, r.text
        assert (
            wait_for(customer, lambda f: f.get("id") == order_id and f.get("kind") == "assignment")
            is not None
        )
        # The agent holding the order hears its kitchen progress (the pickup gate opens live).
        assert team.ks.post(f"{KITCHEN}/{order_id}/start").status_code == 200
        progress = wait_for(a, lambda f: f.get("topic") == "agent:me" and f.get("kind") == "order")
        assert progress is not None and progress["id"] == order_id
    view = team.customer.get(f"/api/v1/orders/{order_id}").json()
    assert view["agent_assigned"] is True
    assert (view["fulfilment_status"], view["status_label"]) == ("PREPARING", "Preparing")
    agent.close()


def test_pipeline_hints_reach_only_viewers_of_the_run_region(world: World, team: Team) -> None:
    with socket(team.rm) as rm, socket(team.other_rm) as other, socket(team.ca) as ca:
        for ws in (rm, other, ca):
            ready(ws)
            assert subscribe(ws, "pipelines") == {"pipelines": "subscribed"}
        run = world.db.execute(
            "INSERT INTO ops.pipeline_runs (pipeline, trigger, status, is_test, region_id) "
            "VALUES ('p1_sop', 'cli', 'cancelled', true, %s) RETURNING id",
            (world.region_a,),
        ).fetchone()
        assert run is not None
        run_id = str(run[0])
        try:
            assert wait_for(rm, hint_for("pipelines", run_id)) is not None
            assert wait_for(ca, hint_for("pipelines", run_id)) is not None
            assert wait_for(other, hint_for("pipelines", run_id), timeout=1.5) is None
        finally:
            world.db.execute("DELETE FROM ops.pipeline_runs WHERE id = %s", (run_id,))


# ---------------------------------------------------------------- revocation (DDR-115 (7); PL-04)
def test_logout_and_deactivation_close_the_socket_within_two_seconds(world: World, team: Team) -> None:
    ks = login(world.user("KITCHEN_STAFF", region=world.region_a, kitchen=world.kitchen_a), "kitchen")
    with socket(ks) as ws:
        ready(ws)
        subscribe(ws, f"kitchen:{world.kitchen_a}")
        assert ks.post("/api/v1/auth/logout").status_code == 204
        assert closed_with(ws) == 4401

    mobile = world.user("KITCHEN_STAFF", region=world.region_a, kitchen=world.kitchen_a)
    other = login(mobile, "kitchen")
    with socket(other) as ws:
        ready(ws)
        r = team.rm.put(
            f"{M}/staff/{user_id(world, mobile)}/status", json={"active": False, "reason": "Test"}
        )
        assert r.status_code == 204, r.text
        assert closed_with(ws) == 4401
    with socket(other) as ws:  # the revoked session cannot open a new socket
        assert closed_with(ws) == 4401
    ks.close()
    other.close()
