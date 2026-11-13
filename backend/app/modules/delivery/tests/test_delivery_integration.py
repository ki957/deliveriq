"""Delivery and tracking over the real stack (plan Task 9; DDR-14, DDR-16, DDR-43, DDR-51, DDR-52, DDR-113).

Needs the core stack and fixtures (`make up`, `make fixtures`, `make test-integration`). Orders are TEST
orders (5 x Dish A, COD) placed by a module customer and accepted by the kitchen through the API; the
module's agents are the only ONLINE agents of the region. The module starts from a kitchen with no held
orders (leftovers of failed runs are rejected by the KM through the API) and leaves none behind.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import psycopg
import pytest

from app.modules.identity.tests.test_auth_integration import World, client, login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

KITCHEN = "/api/v1/kitchen/orders"
DELIVERY = "/api/v1/delivery"
MANAGE = "/api/v1/delivery/manage"
SEED_LAT, SEED_LNG = 13.0835, 80.2710
CREATED: list[str] = []


def scalar(world: World, sql: str, *params: object) -> Any:
    row = world.db.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def user_id(world: World, mobile: str) -> uuid.UUID:
    return uuid.UUID(str(scalar(world, "SELECT id FROM app.users WHERE mobile_e164 = %s", mobile)))


def now() -> datetime:
    return datetime.now(UTC)


class Crew:
    def __init__(self, world: World) -> None:
        a = world.region_a
        self.ks = login(world.user("KITCHEN_STAFF", region=a, kitchen=world.kitchen_a), "kitchen")
        self.km = login(world.user("KITCHEN_MANAGER", region=a, kitchen=world.kitchen_a), "kitchen")
        self.rm = login(world.user("REGIONAL_MANAGER", region=a), "management")
        self.other_rm = login(world.user("REGIONAL_MANAGER", region=world.region_b), "management")
        self.customer = login(world.user("CUSTOMER"), "customer")
        self.other_customer = login(world.user("CUSTOMER"), "customer")
        mobiles = [world.user("DELIVERY_AGENT", region=a) for _ in range(2)]
        self.agents = [login(m, "delivery") for m in mobiles]
        self.agent_ids = [user_id(world, m) for m in mobiles]
        self.far_agent = login(world.user("DELIVERY_AGENT", region=world.region_b), "delivery")
        address = self.customer.post(
            "/api/v1/me/addresses",
            json={
                "label": "Home",
                "address_line": "Synthetic Test Address, Chennai",
                "lat": SEED_LAT,
                "lng": SEED_LNG,
            },
        )
        assert address.status_code == 201, address.text
        self.address = str(address.json()["id"])


def held_test_orders(world: World) -> list[str]:
    return [
        str(r[0])
        for r in world.db.execute(
            "SELECT id FROM app.orders WHERE kitchen_id = %s AND is_test_fixture "
            "AND fulfilment_status IN ('ACCEPTED', 'PREPARING', 'READY_FOR_PICKUP')",
            (world.kitchen_a,),
        ).fetchall()
    ]


@pytest.fixture(scope="module")
def crew(world: World) -> Iterator[Crew]:
    c = Crew(world)
    for order_id in held_test_orders(world):  # leftovers of a failed run: end them as the KM would
        c.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test: clean kitchen"})
    assert held_test_orders(world) == []
    yield c
    world.db.execute("SET lock_timeout = '10s'")
    for order_id in held_test_orders(world):
        c.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test cleanup"})
    users = world.users or []
    world.db.execute(
        "UPDATE app.agent_availability SET status = 'OFFLINE' WHERE agent_user_id = ANY(%s)", (users,)
    )
    # Agents' finished assignments keep their GPS points and history; remove them with the users.
    world.db.execute("DELETE FROM app.delivery_locations WHERE agent_user_id = ANY(%s)", (users,))
    world.db.execute("DELETE FROM app.agent_availability WHERE agent_user_id = ANY(%s)", (users,))
    orders = [
        r[0] for r in world.db.execute("SELECT id FROM app.orders WHERE customer_user_id = ANY(%s)", (users,))
    ]
    open_orders = [
        r[0]
        for r in world.db.execute(
            "SELECT o.id FROM app.orders o WHERE o.id = ANY(%s) "
            "AND NOT EXISTS (SELECT 1 FROM app.stock_movements m WHERE m.order_id = o.id)",
            (orders,),
        )
    ]
    world.db.execute("DELETE FROM app.delivery_otps WHERE order_id = ANY(%s)", (orders,))
    world.db.execute("DELETE FROM app.delivery_assignments WHERE order_id = ANY(%s) OR agent_user_id = ANY(%s)",
                     (orders, users))  # fmt: skip
    world.db.execute("DELETE FROM app.stock_reservations WHERE order_id = ANY(%s)", (open_orders,))
    world.db.execute(
        "DELETE FROM app.outbox WHERE aggregate_id = ANY(%s) AND published_at IS NULL", (open_orders,)
    )
    world.db.execute("DELETE FROM app.payments WHERE order_id = ANY(%s)", (open_orders,))
    world.db.execute("DELETE FROM app.order_items WHERE order_id = ANY(%s)", (open_orders,))
    world.db.execute("DELETE FROM app.orders WHERE id = ANY(%s)", (open_orders,))
    # Orders that consumed stock keep their ledger rows (append-only); re-home them on the seed customer.
    seed = user_id(world, "+910000000001")
    world.db.execute("UPDATE app.orders SET customer_user_id = %s WHERE id = ANY(%s)", (seed, orders))
    world.db.execute("DELETE FROM app.customer_addresses WHERE customer_user_id = ANY(%s)", (users,))


# ---------------------------------------------------------------- helpers
def accepted_order(world: World, crew: Crew) -> str:
    """A TEST COD order the kitchen accepted (the offer goes to an online module agent)."""
    row = world.db.execute(
        "SELECT id, price_paise FROM app.menu_items WHERE name = 'TEST – Synthetic Dish A'"
    ).fetchone()
    assert row is not None, "run `make fixtures`"
    placed = crew.customer.post(
        "/api/v1/orders",
        json={"lines": [{"menu_item_id": str(row[0]), "quantity": 5, "unit_price_paise": row[1]}],
              "payment_method": "COD", "address_id": crew.address},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )  # fmt: skip
    assert placed.status_code == 201, placed.text
    order_id = str(placed.json()["id"])
    CREATED.append(order_id)
    assert crew.ks.post(f"{KITCHEN}/{order_id}/accept").status_code == 200
    return order_id


def online(agent: httpx.Client) -> dict[str, Any]:
    r = agent.put(f"{DELIVERY}/me/availability", json={"online": True})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def offline(agent: httpx.Client) -> None:
    agent.put(f"{DELIVERY}/me/availability", json={"online": False})


def offer_of(agent: httpx.Client, order_id: str) -> str | None:
    me = agent.get(f"{DELIVERY}/me").json()
    if me["assignment"] and me["order"] and me["order"]["order_id"] == order_id:
        return str(me["assignment"]["id"])
    return None


def who_has(crew: Crew, order_id: str) -> int | None:
    for i, agent in enumerate(crew.agents):
        if offer_of(agent, order_id):
            return i
    return None


def ready(crew: Crew, order_id: str) -> None:
    assert crew.ks.post(f"{KITCHEN}/{order_id}/start").status_code == 200
    item = crew.ks.get(KITCHEN).json()["held"]
    item_id = next(o for o in item if o["id"] == order_id)["items"][0]["id"]
    r = crew.ks.post(f"{KITCHEN}/{order_id}/items/{item_id}/status", json={"status": "PREPARED"})
    assert r.json()["fulfilment_status"] == "READY_FOR_PICKUP"


def assigned(world: World, crew: Crew) -> tuple[str, int]:
    """An accepted order whose offer one module agent accepted."""
    for agent in crew.agents:
        online(agent)
    order_id = accepted_order(world, crew)
    i = who_has(crew, order_id)
    assert i is not None, "the order should be offered to an online module agent"
    offer = offer_of(crew.agents[i], order_id)
    r = crew.agents[i].post(f"{DELIVERY}/assignments/{offer}/respond", json={"accept": True})
    assert r.status_code == 200, r.text
    return order_id, i


def on_the_way(world: World, crew: Crew) -> tuple[str, int]:
    order_id, i = assigned(world, crew)
    ready(crew, order_id)
    picked = crew.agents[i].post(f"{DELIVERY}/orders/{order_id}/pickup")
    assert picked.status_code == 200, picked.text
    return order_id, i


def code_for(crew: Crew, order_id: str) -> str:
    code = crew.customer.get(f"/api/v1/orders/{order_id}").json()["delivery_code"]
    assert code and len(code) == 6
    return str(code)


def finish(crew: Crew, order_id: str, i: int) -> None:
    r = crew.agents[i].post(f"{DELIVERY}/orders/{order_id}/deliver", json={"code": code_for(crew, order_id)})
    assert r.status_code == 200, r.text


def events(world: World, order_id: str) -> list[str]:
    return [str(r[0]) for r in world.db.execute(
        "SELECT event_type FROM app.outbox WHERE aggregate_id = %s ORDER BY id", (order_id,)).fetchall()]  # fmt: skip


# ---------------------------------------------------------------- availability and offers (DL-01–DL-07)
def test_only_online_agents_get_offers_and_accepting_shows_agent_assigned(world: World, crew: Crew) -> None:
    for agent in crew.agents:
        offline(agent)
    order_id = accepted_order(world, crew)
    assert who_has(crew, order_id) is None  # everyone offline: "Awaiting agent"
    online(crew.agents[0])  # going online picks up the waiting order at once
    offer = offer_of(crew.agents[0], order_id)
    assert offer is not None
    me = crew.agents[0].get(f"{DELIVERY}/me").json()
    assert me["assignment"]["status"] == "OFFERED" and 0 < me["assignment"]["offer_seconds_left"] <= 60
    assert me["order"]["delivery_address"] is None  # the address is shown after accepting (DL-08)
    assert crew.customer.get(f"/api/v1/orders/{order_id}").json()["agent_assigned"] is False

    r = crew.agents[0].post(f"{DELIVERY}/assignments/{offer}/respond", json={"accept": True})
    assert r.status_code == 200
    body = r.json()
    assert body["order"]["delivery_address"] and body["order"]["customer_phone_masked"].endswith(
        body["order"]["customer_phone_masked"][-2:]
    )
    assert "*" in body["order"]["customer_phone_masked"]
    customer_view = crew.customer.get(f"/api/v1/orders/{order_id}").json()
    assert customer_view["agent_assigned"] is True and customer_view["fulfilment_status"] == "ACCEPTED"
    assert "delivery.assigned" in events(world, order_id)
    # One active delivery per agent; cannot go offline holding it.
    blocked = crew.agents[0].put(f"{DELIVERY}/me/availability", json={"online": False})
    assert blocked.status_code == 409
    crew.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})
    assert crew.agents[0].get(f"{DELIVERY}/me").json()["assignment"] is None  # revoked with the order


def test_rejection_needs_a_reason_and_never_returns_to_the_same_agent(world: World, crew: Crew) -> None:
    for agent in crew.agents:
        online(agent)
    order_id = accepted_order(world, crew)
    first = who_has(crew, order_id)
    assert first is not None
    offer = offer_of(crew.agents[first], order_id)
    no_reason = crew.agents[first].post(f"{DELIVERY}/assignments/{offer}/respond", json={"accept": False})
    assert no_reason.status_code == 422
    r = crew.agents[first].post(
        f"{DELIVERY}/assignments/{offer}/respond", json={"accept": False, "reason": "Flat tyre"}
    )
    assert r.status_code == 200
    second = who_has(crew, order_id)
    assert second is not None and second != first
    reason = scalar(world, "SELECT reason FROM app.status_history WHERE machine = 'assignment' AND entity_id = %s "
                    "AND to_status = 'REJECTED'", uuid.UUID(offer or ""))  # fmt: skip
    assert reason == "Flat tyre"
    crew.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})


def test_an_unanswered_offer_expires_after_60_seconds_and_goes_to_the_pool(world: World, crew: Crew) -> None:
    for agent in crew.agents:
        online(agent)
    order_id = accepted_order(world, crew)
    first = who_has(crew, order_id)
    assert first is not None
    offer = offer_of(crew.agents[first], order_id)
    world.db.execute(
        "UPDATE app.delivery_assignments SET offered_at = now() - interval '61 seconds' WHERE id = %s",
        (offer,),
    )
    late = crew.agents[first].post(f"{DELIVERY}/assignments/{offer}/respond", json={"accept": True})
    assert late.status_code == 409 and "expired" in late.json()["message"]
    assert scalar(world, "SELECT status FROM app.delivery_assignments WHERE id = %s", offer) == "EXPIRED"
    second = who_has(crew, order_id)
    assert second is not None and second != first
    # The worker's sweep does the same through its one granted function (DDR-113 (17)).
    other = offer_of(crew.agents[second], order_id)
    world.db.execute(
        "UPDATE app.delivery_assignments SET offered_at = now() - interval '61 seconds' WHERE id = %s",
        (other,),
    )
    with psycopg.connect(
        host="127.0.0.1", port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")), dbname=os.environ["POSTGRES_DB"],
        user="worker", password=os.environ["WORKER_PASSWORD"], autocommit=True,
    ) as worker:  # fmt: skip
        assert worker.execute("SELECT app.expire_and_reoffer()").fetchone()[0] >= 1  # type: ignore[index]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            worker.execute("SELECT count(*) FROM app.delivery_assignments")
    assert scalar(world, "SELECT status FROM app.delivery_assignments WHERE id = %s", other) == "EXPIRED"
    assert who_has(crew, order_id) is None  # both module agents had their chance: "Awaiting agent"
    crew.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})


# ---------------------------------------------------------------- pickup, code, tracking (DL-09–DL-11, DL-G*)
def test_pickup_needs_ready_and_the_customer_sees_code_and_location_only_after(
    world: World, crew: Crew
) -> None:
    order_id, i = assigned(world, crew)
    agent = crew.agents[i]
    early = agent.post(f"{DELIVERY}/orders/{order_id}/pickup")
    assert early.status_code == 409  # not Ready yet
    # GPS starts at assignment (DL-G1), but the customer sees nothing before pickup (DL-10).
    sent = agent.post(f"{DELIVERY}/locations", json={"points": [
        {"lat": 13.08, "lng": 80.27, "recorded_at": (now() - timedelta(seconds=3)).isoformat(), "source": "REAL"}]})  # fmt: skip
    assert sent.json() == {"accepted": 1, "refused": {}}
    view = crew.customer.get(f"/api/v1/orders/{order_id}").json()
    assert view["live_location"] is None and view["delivery_code"] is None
    ready(crew, order_id)
    picked = agent.post(f"{DELIVERY}/orders/{order_id}/pickup")
    assert picked.json()["fulfilment_status"] == "OUT_FOR_DELIVERY"
    assert picked.json()["delivery_code"] is None  # never shown to the agent
    agent.post(f"{DELIVERY}/locations", json={"points": [
        {"lat": 13.081, "lng": 80.271, "recorded_at": (now() - timedelta(seconds=1)).isoformat(), "source": "SIMULATED"}]})  # fmt: skip
    view = crew.customer.get(f"/api/v1/orders/{order_id}").json()
    assert len(view["delivery_code"]) == 6
    assert view["live_location"]["simulated"] is True and view["live_location"]["lat"] == pytest.approx(
        13.081
    )
    assert crew.other_customer.get(f"/api/v1/orders/{order_id}").status_code == 404
    assert (
        scalar(world, "SELECT is_test_fixture FROM app.delivery_otps WHERE order_id = %s", order_id) is True
    )
    assert "nonce" not in view and scalar(world, "SELECT count(*) FROM app.delivery_otps WHERE order_id = %s "
                                                 "AND nonce LIKE %s", order_id, f"%{view['delivery_code']}%") == 0  # fmt: skip
    finish(crew, order_id, i)


def test_gps_rejects_stale_out_of_order_and_other_agents(world: World, crew: Crew) -> None:
    order_id, i = assigned(world, crew)
    agent, other = crew.agents[i], crew.agents[1 - i]
    t = now()
    points = [
        {
            "lat": 13.08,
            "lng": 80.27,
            "recorded_at": (t - timedelta(seconds=10)).isoformat(),
            "source": "REAL",
        },
        {
            "lat": 13.08,
            "lng": 80.27,
            "recorded_at": (t - timedelta(seconds=300)).isoformat(),
            "source": "REAL",
        },
        {"lat": 13.08, "lng": 80.27, "recorded_at": (t + timedelta(minutes=5)).isoformat(), "source": "REAL"},
    ]
    assert agent.post(f"{DELIVERY}/locations", json={"points": points}).json() == {
        "accepted": 1, "refused": {"stale": 1, "future": 1}}  # fmt: skip
    again = agent.post(f"{DELIVERY}/locations", json={"points": [points[0]]}).json()
    assert again == {"accepted": 0, "refused": {"out_of_order": 1}}  # a re-sent buffer is harmless
    offline_other = other.post(f"{DELIVERY}/locations", json={"points": [points[0]]})
    assert offline_other.status_code == 409  # no accepted delivery, nothing stored
    too_many = agent.post(f"{DELIVERY}/locations", json={"points": [points[0]] * 101})
    assert too_many.status_code == 422
    crew.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})


def test_three_wrong_codes_escalate_and_a_new_code_completes_the_delivery(world: World, crew: Crew) -> None:
    order_id, i = on_the_way(world, crew)
    agent = crew.agents[i]
    real = code_for(crew, order_id)
    wrong = "000000" if real != "000000" else "111111"
    for left in (2, 1, 0):
        r = agent.post(f"{DELIVERY}/orders/{order_id}/deliver", json={"code": wrong})
        assert r.status_code == 422 and (f"{left} attempt" in r.json()["message"] or left == 0)
    locked = agent.post(f"{DELIVERY}/orders/{order_id}/deliver", json={"code": real})
    assert locked.status_code == 409  # locked even for the right code
    assert scalar(world, "SELECT delivery_exception_open FROM app.orders WHERE id = %s", order_id) is True
    assert crew.other_rm.post(f"{MANAGE}/orders/{order_id}/code", json={"reason": "x"}).status_code == 404
    assert (
        crew.rm.post(
            f"{MANAGE}/orders/{order_id}/code", json={"reason": "Customer confirmed by phone"}
        ).status_code
        == 200
    )
    new = code_for(crew, order_id)
    done = agent.post(f"{DELIVERY}/orders/{order_id}/deliver", json={"code": new})
    assert done.status_code == 200 and done.json()["fulfilment_status"] == "DELIVERED"
    assert scalar(world, "SELECT status FROM app.delivery_assignments WHERE order_id = %s AND agent_user_id = %s",
                  order_id, crew.agent_ids[i]) == "COMPLETED"  # fmt: skip
    gps = scalar(world, "SELECT data->'gps' FROM app.outbox WHERE aggregate_id = %s AND event_type = 'delivery.completed'",
                 order_id)  # fmt: skip
    assert set(gps) == {"points", "km", "duration_seconds", "real_points", "simulated_points"}
    assert not [e for e in events(world, order_id) if "location" in e]  # no per-point events (DDR-78)
    history = agent.get(f"{DELIVERY}/history").json()
    assert any(h["order_id"] == order_id and h["fulfilment_status"] == "DELIVERED" for h in history)


def test_the_status_cannot_be_set_delivered_without_the_code(world: World, crew: Crew) -> None:
    order_id, i = on_the_way(world, crew)
    for body in ({}, {"code": "12345"}, {"code": "abcdef"}):
        assert crew.agents[i].post(f"{DELIVERY}/orders/{order_id}/deliver", json=body).status_code == 422
    assert crew.agents[1 - i].post(f"{DELIVERY}/orders/{order_id}/deliver",
                                   json={"code": code_for(crew, order_id)}).status_code == 404  # fmt: skip
    assert (
        scalar(world, "SELECT fulfilment_status FROM app.orders WHERE id = %s", order_id)
        == "OUT_FOR_DELIVERY"
    )
    finish(crew, order_id, i)


# ---------------------------------------------------------------- exceptions (#7 §7; DDR-14, DDR-113 (7), (18))
def test_unavailable_customer_wait_and_failure_decisions(world: World, crew: Crew) -> None:
    order_id, i = on_the_way(world, crew)
    agent = crew.agents[i]
    started = agent.post(f"{DELIVERY}/orders/{order_id}/customer-unavailable")
    assert started.json()["wait_minutes"] == 5
    too_soon = agent.post(f"{DELIVERY}/orders/{order_id}/contact-manager", json={})
    assert too_soon.status_code == 409
    world.db.execute("UPDATE app.orders SET customer_unavailable_since = now() - interval '6 minutes' WHERE id = %s",
                     (order_id,))  # fmt: skip
    escalated = agent.post(f"{DELIVERY}/orders/{order_id}/contact-manager", json={})
    assert escalated.status_code == 200
    assert scalar(world, "SELECT delivery_exception_open FROM app.orders WHERE id = %s", order_id) is True

    assert (
        agent.post(
            f"{DELIVERY}/orders/{order_id}/failure-request", json={"refused": True, "reason": ""}
        ).status_code
        == 422
    )
    asked = agent.post(
        f"{DELIVERY}/orders/{order_id}/failure-request", json={"refused": True, "reason": "Not home"}
    )
    assert asked.status_code == 200
    assert (
        agent.post(
            f"{DELIVERY}/orders/{order_id}/deliver", json={"code": code_for(crew, order_id)}
        ).status_code
        == 409
    )
    # The manager returns it to the agent (DDR-113 (18)), then the customer turns up.
    back = crew.rm.post(
        f"{MANAGE}/orders/{order_id}/failure-decision", json={"approve": False, "reason": "Try again"}
    )
    assert back.status_code == 200
    finish(crew, order_id, i)


def test_an_approved_failure_ends_the_delivery(world: World, crew: Crew) -> None:
    order_id, i = on_the_way(world, crew)
    crew.agents[i].post(
        f"{DELIVERY}/orders/{order_id}/failure-request", json={"refused": False, "reason": "Road closed"}
    )
    assert crew.ks.post(
        f"{MANAGE}/orders/{order_id}/failure-decision", json={"approve": True, "reason": "x"}
    ).status_code in (403, 404)
    r = crew.rm.post(
        f"{MANAGE}/orders/{order_id}/failure-decision", json={"approve": True, "reason": "Confirmed"}
    )
    assert r.json()["fulfilment_status"] == "DELIVERY_FAILED"
    assert "delivery.failed" in events(world, order_id)
    assert crew.agents[i].get(f"{DELIVERY}/me").json()["assignment"] is None  # the agent is free again


# ---------------------------------------------------------------- manager actions (DDR-113 (5))
def test_reassignment_revokes_the_old_agent_at_once(world: World, crew: Crew) -> None:
    order_id, i = assigned(world, crew)
    old, new = crew.agents[i], crew.agents[1 - i]
    assert crew.rm.post(f"{MANAGE}/orders/{order_id}/assign", json={"agent_user_id": str(crew.agent_ids[1 - i]),
                        "reason": ""}).status_code == 422  # fmt: skip
    assert crew.other_rm.post(f"{MANAGE}/orders/{order_id}/assign", json={"agent_user_id": str(crew.agent_ids[1 - i]),
                              "reason": "x"}).status_code == 404  # fmt: skip
    # Force offline is refused while the old agent holds the delivery.
    assert (
        crew.rm.post(f"{MANAGE}/agents/{crew.agent_ids[i]}/force-offline", json={"reason": "x"}).status_code
        == 409
    )
    r = crew.rm.post(f"{MANAGE}/orders/{order_id}/assign",
                     json={"agent_user_id": str(crew.agent_ids[1 - i]), "reason": "Old agent delayed"})  # fmt: skip
    assert r.status_code == 200 and r.json()["status"] == "OFFERED"
    assert old.get(f"{DELIVERY}/me").json()["assignment"] is None
    assert old.get(f"{DELIVERY}/orders/{order_id}/customer-phone").status_code == 404
    assert offer_of(new, order_id) is not None
    agents = crew.rm.get(f"{MANAGE}/agents").json()
    assert {a["id"] for a in agents} >= {str(x) for x in crew.agent_ids}
    assert (
        crew.rm.post(
            f"{MANAGE}/agents/{crew.agent_ids[i]}/force-offline", json={"reason": "Shift over"}
        ).status_code
        == 204
    )
    assert old.get(f"{DELIVERY}/me").json()["availability"] == "OFFLINE"
    crew.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})


def test_phone_reveal_is_audited_and_scoped(world: World, crew: Crew) -> None:
    order_id, i = assigned(world, crew)
    phone = crew.agents[i].get(f"{DELIVERY}/orders/{order_id}/customer-phone")
    assert phone.status_code == 200 and phone.json()["phone"].startswith("+91")
    assert crew.agents[1 - i].get(f"{DELIVERY}/orders/{order_id}/customer-phone").status_code == 404
    assert crew.far_agent.get(f"{DELIVERY}/orders/{order_id}/customer-phone").status_code == 404
    assert scalar(world, "SELECT count(*) FROM audit.events WHERE action = 'delivery.customer_phone.revealed' "
                  "AND target_id = %s", order_id) == 1  # fmt: skip
    with client() as anonymous:
        assert anonymous.get(f"{DELIVERY}/me").status_code == 401
    assert crew.customer.get(f"{DELIVERY}/me").status_code == 403
    crew.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})


# ---------------------------------------------------------------- retention (DDR-43, DDR-113 (11))
def test_retention_keeps_day_29_and_deletes_day_31(world: World, crew: Crew) -> None:
    order_id, i = assigned(world, crew)
    assignment = scalar(world, "SELECT id FROM app.delivery_assignments WHERE order_id = %s AND status = 'ACCEPTED'",
                        order_id)  # fmt: skip
    ids = []
    for days in (29, 31):
        ids.append(scalar(
            world,
            "INSERT INTO app.delivery_locations (assignment_id, order_id, agent_user_id, location, recorded_at, "
            "received_at, source) VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(80.27, 13.08), 4326)::geography, "
            "now() - make_interval(days => %s), now() - make_interval(days => %s), 'SIMULATED') RETURNING id",
            assignment, order_id, crew.agent_ids[i], days, days,
        ))  # fmt: skip
    first = scalar(world, "SELECT app.purge_delivery_locations(NULL)")
    second = scalar(world, "SELECT app.purge_delivery_locations(NULL)")
    assert first >= 1 and second == 0  # idempotent
    kept = {
        r[0] for r in world.db.execute("SELECT id FROM app.delivery_locations WHERE id = ANY(%s)", (ids,))
    }
    assert kept == {ids[0]}
    assert scalar(world, "SELECT after_summary->>'days' FROM audit.events WHERE action = 'delivery.locations.purged' "
                  "ORDER BY occurred_at DESC LIMIT 1") == "30"  # fmt: skip
    crew.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})
