"""Kitchen operations and inventory over the real stack (plan Task 8; DDR-10, DDR-51, DDR-111).

Needs the core stack and fixtures (`make up`, `make fixtures`, `make test-integration`). Orders use the
TEST dishes and the TEST opening stock, so every order, reservation and ledger row is a flagged
fixture row. The module restores what it changes on shared fixtures: kitchen mode and capacity
labels, TEST stock quantities (through a KM adjustment, so the ledger stays honest) and dish
availability. Ledger rows are append-only: the one order picked up here keeps its consumption row
and belongs to the seed customer, so it is never deleted.
"""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.core.permissions import Grant, Principal, Role
from app.modules.identity.tests.test_auth_integration import World, client, login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

ORDERS = "/api/v1/orders"
KITCHEN = "/api/v1/kitchen/orders"
SETTINGS = "/api/v1/kitchen/settings"
INVENTORY = "/api/v1/kitchen/inventory"
AVAILABILITY = "/api/v1/menu/availability"
SEED_CUSTOMER = "+910000000001"
SEED_LAT, SEED_LNG = 13.0835, 80.2710
OPENING_STOCK = Decimal("10000")
CREATED: list[str] = []  # orders placed by this module


# ---------------------------------------------------------------- helpers
def scalar(world: World, sql: str, *params: object) -> Any:
    row = world.db.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def rows(world: World, sql: str, *params: object) -> list[tuple[Any, ...]]:
    return list(world.db.execute(sql, params).fetchall())


def dish(world: World, letter: str) -> tuple[str, int]:
    row = world.db.execute(
        "SELECT id, price_paise FROM app.menu_items WHERE name = %s", (f"TEST – Synthetic Dish {letter}",)
    ).fetchone()
    assert row is not None, "run `make fixtures`"
    return str(row[0]), int(row[1])  # type: ignore[call-overload]


def place(
    c: httpx.Client, address: str, lines: list[tuple[str, int, int]], method: str = "COD"
) -> httpx.Response:
    return c.post(
        ORDERS,
        json={
            "lines": [{"menu_item_id": m, "quantity": q, "unit_price_paise": p} for m, q, p in lines],
            "payment_method": method,
            "address_id": address,
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )


def order_of(world: World, c: httpx.Client, address: str, letter: str, qty: int, method: str = "COD") -> str:
    menu_item, price = dish(world, letter)
    response = place(c, address, [(menu_item, qty, price)], method)
    assert response.status_code == 201, response.text
    order_id = str(response.json()["id"])
    CREATED.append(order_id)
    if method != "COD":
        paid = c.post(f"{ORDERS}/{order_id}/payment/simulate", json={"outcome": "SUCCESS"})
        assert paid.status_code == 200, paid.text
    return order_id


def stock(world: World, letter_ingredient: int) -> tuple[Decimal, Decimal]:
    row = world.db.execute(
        "SELECT s.on_hand, s.reserved FROM app.ingredient_stock s JOIN app.ingredients i ON i.id = s.ingredient_id "
        "WHERE i.name = %s AND s.kitchen_id = (SELECT id FROM app.kitchens WHERE code = 'KIT-CHN-001')",
        (f"TEST – Ingredient {letter_ingredient}",),
    ).fetchone()
    assert row is not None, "run `make fixtures` (TEST opening stock)"
    return Decimal(row[0]), Decimal(row[1])  # type: ignore[arg-type]


def ingredient_id(world: World, n: int) -> str:
    return str(scalar(world, "SELECT id FROM app.ingredients WHERE name = %s", f"TEST – Ingredient {n}"))


def status(world: World, order_id: str) -> str:
    return str(scalar(world, "SELECT fulfilment_status FROM app.orders WHERE id = %s", order_id))


def events(world: World, order_id: str) -> list[str]:
    return [
        r[0]
        for r in rows(
            world, "SELECT event_type FROM app.outbox WHERE aggregate_id = %s ORDER BY id", order_id
        )
    ]


def act_as(world: World, role: str, user: uuid.UUID | None, reason: str = "integration test") -> None:
    world.db.execute("SELECT set_config('app.actor_role', %s, true)", (role,))
    world.db.execute("SELECT set_config('app.actor_user_id', %s, true)", (str(user) if user else "",))
    world.db.execute("SELECT set_config('app.reason', %s, true)", (reason,))


def user_id(world: World, mobile: str) -> uuid.UUID:
    return uuid.UUID(str(scalar(world, "SELECT id FROM app.users WHERE mobile_e164 = %s", mobile)))


def public_menu() -> list[dict[str, Any]]:
    with client() as anonymous:
        menu: list[dict[str, Any]] = anonymous.get("/api/v1/menu/items").json()
    return menu


# ---------------------------------------------------------------- module world
class Staff:
    def __init__(self, world: World) -> None:
        a, b = world.region_a, world.region_b
        self.ks = login(world.user("KITCHEN_STAFF", region=a, kitchen=world.kitchen_a), "kitchen")
        self.km_mobile = world.user("KITCHEN_MANAGER", region=a, kitchen=world.kitchen_a)
        self.km = login(self.km_mobile, "kitchen")
        self.other_ks = login(world.user("KITCHEN_STAFF", region=b, kitchen=world.kitchen_b), "kitchen")
        self.rm = login(world.user("REGIONAL_MANAGER", region=a), "management")
        self.other_rm = login(world.user("REGIONAL_MANAGER", region=b), "management")
        self.ca = login(world.user("CENTRAL_ADMIN"), "management")
        self.customer = login(world.user("CUSTOMER"), "customer")
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


@pytest.fixture(scope="module")
def staff(world: World) -> Iterator[Staff]:
    assert stock(world, 1)[0] > 0
    saved = rows(
        world,
        "SELECT key, value, is_test_default, source_ref FROM app.config_settings WHERE kitchen_id = %s "
        "AND key IN ('MAX_CONCURRENT_ORDERS', 'MAX_CONCURRENT_ORDERS_BUSY')",
        world.kitchen_a,
    )
    yield Staff(world)
    # Restore the shared kitchen settings and their DDR-42 test-default labels.
    world.db.execute("SET lock_timeout = '10s'")
    for key, value, test_default, source in saved:
        world.db.execute(
            "UPDATE app.config_settings SET value = %s, is_test_default = %s, source_ref = %s "
            "WHERE key = %s AND kitchen_id = %s",
            (value, test_default, source, key, world.kitchen_a),
        )
    world.db.execute("UPDATE app.kitchens SET mode = 'NORMAL' WHERE id = %s", (world.kitchen_a,))


@pytest.fixture(scope="module", autouse=True)
def cleanup(world: World) -> Iterator[None]:
    yield
    world.db.execute("SET lock_timeout = '10s'")
    removable = [
        r[0]
        for r in rows(
            world,
            "SELECT id FROM app.orders o WHERE id::text = ANY(%s) "
            "AND NOT EXISTS (SELECT 1 FROM app.stock_movements m WHERE m.order_id = o.id)",
            CREATED,
        )
    ]
    world.db.execute("DELETE FROM app.delivery_assignments WHERE order_id::text = ANY(%s)", (CREATED,))
    world.db.execute("DELETE FROM app.stock_reservations WHERE order_id = ANY(%s)", (removable,))
    world.db.execute(
        "DELETE FROM app.outbox WHERE aggregate_id = ANY(%s) AND published_at IS NULL", (removable,)
    )
    world.db.execute("DELETE FROM app.payments WHERE order_id = ANY(%s)", (removable,))
    world.db.execute("DELETE FROM app.order_items WHERE order_id = ANY(%s)", (removable,))
    world.db.execute("DELETE FROM app.orders WHERE id = ANY(%s)", (removable,))
    users = world.users or []
    world.db.execute("DELETE FROM app.dish_availability_requests WHERE requested_by = ANY(%s)", (users,))
    world.db.execute("DELETE FROM app.cart_items WHERE customer_user_id = ANY(%s)", (users,))
    world.db.execute("DELETE FROM app.customer_addresses WHERE customer_user_id = ANY(%s)", (users,))


@pytest.fixture()
def api_services(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Call module services in-process as the real `app_api` role (pickup has no endpoint until Task 9)."""
    from app.core.config import get_settings
    from app.core.db import get_engine

    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", os.environ.get("INTEGRATION_DB_PORT", "5433"))
    monkeypatch.setenv("DB_USER", "app_api")
    monkeypatch.setenv("DB_PASSWORD", os.environ["APP_API_PASSWORD"])
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield
    get_engine().dispose()


def restore_stock(world: World, km: httpx.Client, *numbers: int) -> None:
    """Bring TEST stock back to the opening quantity with a reasoned KM adjustment (ledger kept)."""
    for n in numbers:
        on_hand, _reserved = stock(world, n)
        if on_hand != OPENING_STOCK:
            r = km.post(
                f"{INVENTORY}/{ingredient_id(world, n)}/adjust",
                json={
                    "delta": str(OPENING_STOCK - on_hand),
                    "reason": "Integration test: restore TEST stock",
                },
            )
            assert r.status_code == 200, r.text


# ---------------------------------------------------------------- acceptance: pin, reserve, FIFO, assign
def test_acceptance_pins_reserves_and_offers_an_agent_in_one_step(world: World, staff: Staff) -> None:
    # Two free agents in the region, so both orders can be offered whatever the seed agent is doing.
    agents = {user_id(world, world.user("DELIVERY_AGENT", region=world.region_a)) for _ in range(2)}
    before = {n: stock(world, n) for n in (1, 2)}
    first = order_of(world, staff.customer, staff.address, "A", 5)
    second = order_of(world, staff.customer, staff.address, "A", 5)

    queue = staff.ks.get(KITCHEN).json()
    incoming = [o["id"] for o in queue["incoming"]]
    assert first in incoming and second in incoming
    assert queue["incoming"][0]["status_label"] == "Incoming"

    # Accept the later order first: the held queue is FIFO by acceptance time, not placement (KI-03).
    for order_id in (second, first):
        accepted = staff.ks.post(f"{KITCHEN}/{order_id}/accept")
        assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["fulfilment_status"] == "ACCEPTED" and body["accepted_at"]
    assert all(i["recipe_version_id"] and i["recipe_version"] == 1 for i in body["items"])
    held = [o["id"] for o in staff.ks.get(KITCHEN).json()["held"]]
    assert held.index(second) < held.index(first)

    # 5 x Dish A = 5 x 100 g of Ingredient 1 and of Ingredient 2, reserved per order (KI-22).
    for n in (1, 2):
        assert stock(world, n) == (before[n][0], before[n][1] + Decimal("1000"))
    reserved = rows(world, "SELECT status, quantity FROM app.stock_reservations WHERE order_id = %s", first)
    assert sorted(reserved) == [("RESERVED", Decimal("500.000"))] * 2
    assert events(world, first)[-2:] == ["inventory.reserved", "order.accepted"]

    # DDR-51: acceptance offers the order to an eligible agent; the fulfilment status is unchanged.
    offers = rows(
        world,
        "SELECT a.status, a.agent_user_id FROM app.delivery_assignments a WHERE a.order_id = ANY(%s::uuid[])",
        [first, second],
    )
    assert len(offers) == 2 and {s for s, _ in offers} == {"OFFERED"}
    assert len({a for _, a in offers}) == 2  # one live offer per agent
    # Agents never offered before come first (least recently offered).
    assert {a for _, a in offers} <= agents | {user_id(world, "+910000000002")}
    assert status(world, first) == "ACCEPTED"  # an offer never changes the fulfilment status (DDR-16)

    for order_id in (first, second):
        assert (
            staff.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"}).status_code
            == 200
        )


def test_accepting_twice_or_a_rejected_order_is_refused(world: World, staff: Staff) -> None:
    order_id = order_of(world, staff.customer, staff.address, "A", 5)
    assert (
        staff.ks.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Out of packaging"}).status_code == 200
    )
    again = staff.ks.post(f"{KITCHEN}/{order_id}/accept")
    assert again.status_code == 409
    history = rows(
        world,
        "SELECT to_status, actor_role, reason FROM app.status_history WHERE machine = 'fulfilment' "
        "AND entity_id = %s ORDER BY id",
        order_id,
    )
    assert history[-1] == ("REJECTED", "KITCHEN_STAFF", "Out of packaging")
    assert staff.ks.post(f"{KITCHEN}/{order_id}/reject", json={"reason": " "}).status_code == 422


def test_capacity_holds_under_concurrent_acceptance(world: World, staff: Staff) -> None:
    active = int(staff.ks.get(KITCHEN).json()["intake"]["active_orders"])
    settings = staff.km.get(SETTINGS).json()
    one_left = staff.km.put(
        SETTINGS,
        json={"mode": "NORMAL", "normal_capacity": active + 1, "busy_capacity": min(5, active + 1),
              "reason": "Integration test: one slot left"},
    )  # fmt: skip
    assert one_left.status_code == 200, one_left.text
    assert one_left.json()["normal_capacity"] == {"value": active + 1, "is_test_default": False}
    orders = [order_of(world, staff.customer, staff.address, "A", 5) for _ in range(2)]

    results: dict[str, int] = {}
    barrier = threading.Barrier(2)

    def accept(order_id: str, c: httpx.Client) -> None:
        barrier.wait()
        results[order_id] = c.post(f"{KITCHEN}/{order_id}/accept").status_code

    clients = [staff.ks, staff.km]
    threads = [threading.Thread(target=accept, args=(o, c)) for o, c in zip(orders, clients, strict=True)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(results.values()) == [200, 409]
    refused = next(o for o, code in results.items() if code == 409)
    assert status(world, refused) == "PENDING_KITCHEN"
    assert not rows(world, "SELECT 1 FROM app.stock_reservations WHERE order_id = %s", refused)

    # Checkout is refused at capacity (KI-13), and the cart says why.
    menu_item, price = dish(world, "A")
    full = place(staff.customer, staff.address, [(menu_item, 5, price)])
    assert full.status_code == 422 and full.json()["code"] == "kitchen_at_capacity"
    staff.customer.put(f"/api/v1/cart/items/{menu_item}", json={"quantity": 5})
    assert "kitchen_at_capacity" in staff.customer.get("/api/v1/cart").json()["blockers"]
    staff.customer.delete("/api/v1/cart")

    accepted = next(o for o, code in results.items() if code == 200)
    for order_id in (accepted, refused):
        staff.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})
    restore = staff.km.put(
        SETTINGS,
        json={"mode": "NORMAL", "normal_capacity": settings["normal_capacity"]["value"],
              "busy_capacity": settings["busy_capacity"]["value"], "reason": "Integration test: restore"},
    )  # fmt: skip
    assert restore.status_code == 200


def test_paused_stops_new_orders_but_accepted_orders_continue(world: World, staff: Staff) -> None:
    held = order_of(world, staff.customer, staff.address, "A", 5)
    waiting = order_of(world, staff.customer, staff.address, "A", 5)
    assert staff.ks.post(f"{KITCHEN}/{held}/accept").status_code == 200
    current = staff.km.get(SETTINGS).json()
    caps = {
        "normal_capacity": current["normal_capacity"]["value"],
        "busy_capacity": current["busy_capacity"]["value"],
    }
    # Kitchen Staff cannot change the mode (Matrix §3.1); the reason is required.
    assert staff.ks.put(SETTINGS, json={"mode": "PAUSED", **caps, "reason": "x"}).status_code == 403
    assert staff.km.put(SETTINGS, json={"mode": "PAUSED", **caps, "reason": ""}).status_code == 422
    paused = staff.km.put(
        SETTINGS, json={"mode": "PAUSED", **caps, "reason": "Integration test: equipment check"}
    )
    assert paused.status_code == 200 and paused.json()["intake"]["refusal"] == "kitchen_paused"
    # Labelled test default kept when only the mode changes.
    assert paused.json()["busy_capacity"]["is_test_default"] == current["busy_capacity"]["is_test_default"]

    refused = staff.ks.post(f"{KITCHEN}/{waiting}/accept")
    assert refused.status_code == 409 and refused.json()["code"] == "kitchen_paused"
    menu_item, price = dish(world, "A")
    checkout = place(staff.customer, staff.address, [(menu_item, 5, price)])
    assert checkout.status_code == 422 and checkout.json()["code"] == "kitchen_paused"
    assert staff.ks.post(f"{KITCHEN}/{held}/start").status_code == 200  # KI-14
    audit = scalar(
        world,
        "SELECT reason FROM audit.events WHERE action = 'kitchen.settings.changed' AND target_id = %s "
        "ORDER BY occurred_at DESC LIMIT 1",
        str(world.kitchen_a),
    )
    assert audit == "Integration test: equipment check"

    assert (
        staff.km.put(
            SETTINGS, json={"mode": "NORMAL", **caps, "reason": "Integration test: resume"}
        ).status_code
        == 200
    )
    for order_id in (held, waiting):
        staff.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})


# ---------------------------------------------------------------- stock: all or nothing, no oversell
def test_reservation_is_all_or_nothing_and_cannot_oversell(world: World, staff: Staff) -> None:
    # Dish B uses Ingredients 3 and 4. Leave room for exactly one 3 x Dish B order (300 g each).
    on_hand, reserved = stock(world, 3)
    cut = staff.km.post(
        f"{INVENTORY}/{ingredient_id(world, 3)}/adjust",
        json={
            "delta": str(-(on_hand - reserved - Decimal("400"))),
            "reason": "Integration test: scarce stock",
        },
    )
    assert cut.status_code == 200, cut.text
    assert Decimal(cut.json()["available"]) == Decimal("400")
    assert cut.json()["is_test_fixture"] is True
    orders = [order_of(world, staff.customer, staff.address, "B", 3) for _ in range(2)]
    four_before = stock(world, 4)

    results: dict[str, httpx.Response] = {}
    barrier = threading.Barrier(2)

    def accept(order_id: str, c: httpx.Client) -> None:
        barrier.wait()
        results[order_id] = c.post(f"{KITCHEN}/{order_id}/accept")

    threads = [
        threading.Thread(target=accept, args=(o, c))
        for o, c in zip(orders, [staff.ks, staff.km], strict=True)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    codes = sorted(r.status_code for r in results.values())
    assert codes == [200, 409]
    short = next(r for r in results.values() if r.status_code == 409).json()
    assert short["code"] == "stock_short"
    assert short["shortages"] == [
        {"ingredient": "TEST – Ingredient 3", "unit": "g", "needed": "300.000", "available": "100.000"}
    ]
    # All or nothing: the refused order reserved neither ingredient.
    assert stock(world, 4) == (four_before[0], four_before[1] + Decimal("300"))
    assert stock(world, 3)[1] == reserved + Decimal("300")

    for order_id in orders:
        staff.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})
    restore_stock(world, staff.km, 3)


def test_rejecting_after_acceptance_releases_refunds_and_revokes(world: World, staff: Staff) -> None:
    order_id = order_of(world, staff.customer, staff.address, "A", 5, method="SIM_UPI")
    before = stock(world, 1)
    assert staff.ks.post(f"{KITCHEN}/{order_id}/accept").status_code == 200
    assert staff.ks.post(f"{KITCHEN}/{order_id}/start").status_code == 200
    # Kitchen Staff cannot reject once accepted (DDR-111 (5)); another region's RM sees nothing.
    assert staff.ks.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "x"}).status_code == 403
    assert staff.other_rm.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "x"}).status_code == 404
    rejected = staff.rm.post(
        f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test: cannot fulfil"}
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["fulfilment_status"] == "REJECTED"
    assert stock(world, 1) == before
    assert {
        r[0] for r in rows(world, "SELECT status FROM app.stock_reservations WHERE order_id = %s", order_id)
    } == {"RELEASED"}
    assert scalar(world, "SELECT status FROM app.payments WHERE order_id = %s", order_id) == "REFUNDED"
    assignments = {
        r[0] for r in rows(world, "SELECT status FROM app.delivery_assignments WHERE order_id = %s", order_id)
    }
    assert assignments <= {"REVOKED"}
    assert events(world, order_id)[-2:] == ["inventory.released", "order.rejected"]
    assert (
        scalar(
            world,
            "SELECT actor_role FROM app.status_history WHERE machine = 'fulfilment' AND entity_id = %s "
            "AND to_status = 'REJECTED'",
            order_id,
        )
        == "REGIONAL_MANAGER"
    )


# ---------------------------------------------------------------- preparation and handover
def test_items_drive_the_order_and_handover_deducts_once(
    world: World, staff: Staff, api_services: None
) -> None:
    from app.modules.orders import service

    seed = login(SEED_CUSTOMER, "customer")
    address = str(seed.get("/api/v1/me/addresses").json()[0]["id"])
    order_id = order_of(world, seed, address, "A", 5)
    before = stock(world, 1)
    accepted = staff.ks.post(f"{KITCHEN}/{order_id}/accept").json()
    items = accepted["items"]
    started = staff.ks.post(
        f"{KITCHEN}/{order_id}/items/{items[0]['id']}/status", json={"status": "PREPARING"}
    )
    assert started.json()["fulfilment_status"] == "PREPARING"
    # Another staff member continues the order (KI-06); the order is Ready once every item is Prepared.
    done = staff.km.post(f"{KITCHEN}/{order_id}/items/{items[0]['id']}/status", json={"status": "PREPARED"})
    assert done.json()["fulfilment_status"] == "READY_FOR_PICKUP"
    assert done.json()["status_label"] == "Ready for Pickup"
    item_actors = rows(
        world,
        "SELECT to_status, actor_role FROM app.status_history WHERE machine = 'item' AND entity_id = %s ORDER BY id",
        items[0]["id"],
    )
    assert item_actors[-2:] == [("PREPARING", "KITCHEN_STAFF"), ("PREPARED", "KITCHEN_MANAGER")]
    assert events(world, order_id)[-2:] == ["order.preparing", "order.ready_for_pickup"]

    # The offered agent accepts (Task 9 builds that action), then picks up.
    agent, assignment = rows(
        world, "SELECT agent_user_id, id FROM app.delivery_assignments WHERE order_id = %s AND status = 'OFFERED'",
        order_id,
    )[0]  # fmt: skip
    with world.db.transaction():
        act_as(world, "DELIVERY_AGENT", agent)
        world.db.execute(
            "UPDATE app.delivery_assignments SET status = 'ACCEPTED' WHERE id = %s", (assignment,)
        )
    principal = Principal(agent, (Grant(Role.DELIVERY_AGENT, world.region_a),))
    view = service.record_pickup(principal, uuid.UUID(order_id))
    assert view.order.fulfilment_status == "OUT_FOR_DELIVERY"
    assert stock(world, 1) == (before[0] - Decimal("500"), before[1])
    with pytest.raises(service.Conflict):
        service.record_pickup(principal, uuid.UUID(order_id))  # duplicate handover
    consumed = rows(
        world, "SELECT kind, delta, is_test_fixture FROM app.stock_movements WHERE order_id = %s", order_id
    )
    assert sorted(consumed) == [("CONSUMPTION", Decimal("-500.000"), True)] * 2
    assert stock(world, 1) == (before[0] - Decimal("500"), before[1])
    assert "inventory.consumed" in events(world, order_id)

    # Finish the delivery so the agent is free again, then restore the TEST stock.
    with world.db.transaction():
        act_as(world, "SYSTEM", None)
        world.db.execute("UPDATE app.orders SET fulfilment_status = 'DELIVERED' WHERE id = %s", (order_id,))
        act_as(world, "DELIVERY_AGENT", agent)
        world.db.execute(
            "UPDATE app.delivery_assignments SET status = 'COMPLETED' WHERE id = %s", (assignment,)
        )
    restore_stock(world, staff.km, 1, 2)


def test_concurrent_duplicate_handover_deducts_once(world: World, staff: Staff, api_services: None) -> None:
    from app.modules.orders import service

    seed = login(SEED_CUSTOMER, "customer")
    address = str(seed.get("/api/v1/me/addresses").json()[0]["id"])
    order_id = order_of(world, seed, address, "A", 5)
    before = stock(world, 2)
    assert staff.ks.post(f"{KITCHEN}/{order_id}/accept").status_code == 200
    assert staff.ks.post(f"{KITCHEN}/{order_id}/start").status_code == 200
    item = staff.ks.get(KITCHEN).json()["held"]
    item_id = next(o for o in item if o["id"] == order_id)["items"][0]["id"]
    assert (
        staff.ks.post(f"{KITCHEN}/{order_id}/items/{item_id}/status", json={"status": "PREPARED"}).status_code
        == 200
    )
    agent, assignment = rows(
        world, "SELECT agent_user_id, id FROM app.delivery_assignments WHERE order_id = %s AND status = 'OFFERED'",
        order_id,
    )[0]  # fmt: skip
    with world.db.transaction():
        act_as(world, "DELIVERY_AGENT", agent)
        world.db.execute(
            "UPDATE app.delivery_assignments SET status = 'ACCEPTED' WHERE id = %s", (assignment,)
        )
    principal = Principal(agent, (Grant(Role.DELIVERY_AGENT, world.region_a),))
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def pickup() -> None:
        barrier.wait()
        try:
            service.record_pickup(principal, uuid.UUID(order_id))
            outcomes.append("ok")
        except service.Conflict:
            outcomes.append("conflict")

    threads = [threading.Thread(target=pickup) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(outcomes) == ["conflict", "ok"]
    assert stock(world, 2) == (before[0] - Decimal("500"), before[1])
    assert (
        scalar(
            world,
            "SELECT count(*) FROM app.stock_movements WHERE order_id = %s AND kind = 'CONSUMPTION'",
            order_id,
        )
        == 2
    )  # one per ingredient, never doubled

    with world.db.transaction():
        act_as(world, "SYSTEM", None)
        world.db.execute("UPDATE app.orders SET fulfilment_status = 'DELIVERED' WHERE id = %s", (order_id,))
        act_as(world, "DELIVERY_AGENT", agent)
        world.db.execute(
            "UPDATE app.delivery_assignments SET status = 'COMPLETED' WHERE id = %s", (assignment,)
        )
    restore_stock(world, staff.km, 1, 2)


def test_reject_racing_accept_leaves_no_reservation_behind(world: World, staff: Staff) -> None:
    order_id = order_of(world, staff.customer, staff.address, "A", 5)
    before = stock(world, 1)
    results: dict[str, int] = {}
    barrier = threading.Barrier(2)

    def act(name: str, call: Any) -> None:
        barrier.wait()
        results[name] = call().status_code

    threads = [
        threading.Thread(target=act, args=("accept", lambda: staff.ks.post(f"{KITCHEN}/{order_id}/accept"))),
        threading.Thread(
            target=act,
            args=("reject", lambda: staff.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Race"})),
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    # Whichever ran first, the order ends rejected (KM may reject after acceptance) and stock is whole.
    assert results["reject"] == 200 and results["accept"] in (200, 409)
    assert status(world, order_id) == "REJECTED"
    assert stock(world, 1) == before
    open_lines = scalar(
        world,
        "SELECT count(*) FROM app.stock_reservations WHERE order_id = %s AND status = 'RESERVED'",
        order_id,
    )
    assert open_lines == 0


def test_items_cannot_skip_steps_or_change_after_ready(world: World, staff: Staff) -> None:
    order_id = order_of(world, staff.customer, staff.address, "A", 5)
    pending = staff.ks.post(f"{KITCHEN}/{order_id}/start")
    assert pending.status_code == 409  # not accepted yet
    item = staff.ks.post(f"{KITCHEN}/{order_id}/accept").json()["items"][0]["id"]
    skip = staff.ks.post(f"{KITCHEN}/{order_id}/items/{item}/status", json={"status": "PREPARED"})
    assert skip.status_code == 409
    staff.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})


# ---------------------------------------------------------------- recipe pinning (DDR-10, KI-18)
def test_a_later_recipe_version_does_not_change_pinned_orders(world: World, staff: Staff) -> None:
    # Seed KM and CA act here: sign-offs keep their signer (foreign key), and seed users are never removed.
    km = user_id(world, "+910000000004")
    ca = user_id(world, "+910000000006")
    name = f"TEST – Pin check {world.prefix}"
    with world.db.transaction():
        act_as(world, "SYSTEM", None)
        recipe = scalar(world, "INSERT INTO app.recipes (kitchen_id, name) VALUES (%s, %s) RETURNING id",
                        world.kitchen_a, name)  # fmt: skip
        v1 = scalar(
            world,
            "INSERT INTO app.recipe_versions (recipe_id, version, status, is_test_fixture) "
            "VALUES (%s, 1, 'DRAFT', true) RETURNING id",
            recipe,
        )
        for line, n in ((1, 1), (2, 6)):
            world.db.execute(
                "INSERT INTO app.recipe_ingredients (recipe_version_id, line_no, ingredient_id, quantity, unit) "
                "VALUES (%s, %s, %s, 100, 'g')",
                (v1, line, ingredient_id(world, n)),
            )
        category = scalar(world, "SELECT id FROM app.menu_categories WHERE name = 'TEST – Category'")
        item = scalar(
            world,
            "INSERT INTO app.menu_items (kitchen_id, recipe_id, category_id, name, description, is_veg, spice_level, "
            "price_paise, tax_classification, prep_time_minutes, image_is_placeholder, publication_status, "
            "is_test_fixture) VALUES (%s, %s, %s, %s, 'TEST – synthetic dish for workflow testing', true, 'TEST', "
            "44400, 'TEST', 10, true, 'DRAFT', true) RETURNING id",
            world.kitchen_a, recipe, category, name,
        )  # fmt: skip
    _activate(world, v1, km)
    with world.db.transaction():
        act_as(world, "CENTRAL_ADMIN", ca, reason="Integration test")
        world.db.execute(
            "UPDATE app.menu_items SET publication_status = 'READY_FOR_PUBLICATION' WHERE id = %s", (item,)
        )
        world.db.execute("UPDATE app.menu_items SET publication_status = 'PUBLISHED' WHERE id = %s", (item,))

    def accept_one() -> str:
        response = place(staff.customer, staff.address, [(str(item), 2, 44400)])
        assert response.status_code == 201, response.text
        order_id = str(response.json()["id"])
        CREATED.append(order_id)
        assert staff.ks.post(f"{KITCHEN}/{order_id}/accept").status_code == 200
        return order_id

    pinned = accept_one()
    # Version 2 supersedes version 1 for new orders only.
    with world.db.transaction():
        act_as(world, "SYSTEM", None)
        v2 = scalar(
            world,
            "INSERT INTO app.recipe_versions (recipe_id, version, status, is_test_fixture) "
            "VALUES (%s, 2, 'DRAFT', true) RETURNING id",
            recipe,
        )
        for line, n in ((1, 1), (2, 6)):
            world.db.execute(
                "INSERT INTO app.recipe_ingredients (recipe_version_id, line_no, ingredient_id, quantity, unit) "
                "VALUES (%s, %s, %s, 100, 'g')",
                (v2, line, ingredient_id(world, n)),
            )
    with world.db.transaction():
        act_as(world, "KITCHEN_MANAGER", km, reason="Integration test: new version")
        world.db.execute("UPDATE app.recipe_versions SET status = 'SUPERSEDED' WHERE id = %s", (v1,))
    _activate(world, v2, km)
    later = accept_one()

    def pins(order_id: str) -> set[object]:
        return {
            r[0]
            for r in rows(
                world, "SELECT recipe_version_id FROM app.order_items WHERE order_id = %s", order_id
            )
        }

    assert pins(pinned) == {v1} and pins(later) == {v2}
    # The database refuses to pin a version that is not ACTIVE.
    with pytest.raises(Exception, match="only an ACTIVE recipe version"), world.db.transaction():
        act_as(world, "KITCHEN_MANAGER", km)
        world.db.execute("UPDATE app.order_items SET recipe_version_id = %s WHERE order_id = %s", (v1, later))
    for order_id in (pinned, later):
        staff.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})
    with world.db.transaction():
        act_as(world, "CENTRAL_ADMIN", ca, reason="Integration test done")
        world.db.execute("UPDATE app.menu_items SET publication_status = 'RETIRED' WHERE id = %s", (item,))


def _activate(world: World, version: object, km: uuid.UUID) -> None:
    with world.db.transaction():
        for target in ("PENDING_VALIDATION", "VALIDATED"):
            act_as(world, "KITCHEN_MANAGER", km, reason=f"Integration test: {target}")
            world.db.execute("UPDATE app.recipe_versions SET status = %s WHERE id = %s", (target, version))
        for kind in ("CHEF", "FOOD_SAFETY_LEAD", "INVENTORY_OWNER", "KITCHEN_MANAGER", "PRODUCT_OWNER"):
            world.db.execute(
                "INSERT INTO app.recipe_signoffs (recipe_version_id, signoff_type, signed_by) VALUES (%s, %s, %s)",
                (version, kind, km),
            )
        act_as(world, "KITCHEN_MANAGER", km, reason="Integration test: activate")
        world.db.execute("UPDATE app.recipe_versions SET status = 'ACTIVE' WHERE id = %s", (version,))


# ---------------------------------------------------------------- inventory permissions and low stock
def test_inventory_roles_and_low_stock_alerts(world: World, staff: Staff) -> None:
    assert staff.ks.get(INVENTORY).status_code == 403  # full stock is KM only (DDR-111 (9))
    assert staff.other_ks.get(f"{INVENTORY}?kitchen_id={world.kitchen_a}").status_code == 404
    full = staff.km.get(INVENTORY).json()
    five = next(s for s in full if s["name"] == "TEST – Ingredient 5")
    assert five["is_test_fixture"] is True and five["unit"] == "g"
    assert five["used_in"] == ["TEST – Synthetic Dish C"]
    target = five["ingredient_id"]
    assert (
        staff.ks.post(f"{INVENTORY}/{target}/adjust", json={"delta": "1", "reason": "x"}).status_code == 403
    )
    below = staff.km.post(
        f"{INVENTORY}/{target}/adjust", json={"delta": str(-Decimal(five["on_hand"]) - 1), "reason": "x"}
    )
    assert below.status_code == 422
    assert staff.ks.get(f"{INVENTORY}/low-stock").json() == []  # no threshold set, no alert
    try:
        threshold = staff.km.put(
            f"{INVENTORY}/{target}/threshold",
            json={"low_stock_threshold": five["available"], "reason": "Integration test: alert check"},
        )
        assert threshold.status_code == 200, threshold.text
        alerts = staff.ks.get(f"{INVENTORY}/low-stock").json()
        assert [a["name"] for a in alerts] == ["TEST – Ingredient 5"] and alerts[0]["is_low"]
    finally:
        cleared = staff.km.put(
            f"{INVENTORY}/{target}/threshold",
            json={"low_stock_threshold": None, "reason": "Integration test: clear"},
        )
        assert cleared.status_code == 200


def test_kitchen_routes_deny_other_kitchens_and_non_kitchen_roles(world: World, staff: Staff) -> None:
    order_id = order_of(world, staff.customer, staff.address, "A", 5)
    assert staff.other_ks.post(f"{KITCHEN}/{order_id}/accept").status_code == 404
    assert staff.rm.post(f"{KITCHEN}/{order_id}/accept").status_code == 403  # RM views, never runs the line
    assert staff.customer.post(f"{KITCHEN}/{order_id}/accept").status_code == 404
    assert staff.customer.get(KITCHEN).status_code == 404
    assert staff.other_ks.get(f"{KITCHEN}?kitchen_id={world.kitchen_a}").status_code == 404
    assert staff.rm.get(f"{KITCHEN}?kitchen_id={world.kitchen_a}").status_code == 200
    assert staff.other_rm.get(f"{KITCHEN}?kitchen_id={world.kitchen_a}").status_code == 404
    with client() as anonymous:
        assert anonymous.get(KITCHEN).status_code == 401
    # The kitchen card carries no customer contact details.
    card = next(o for o in staff.ks.get(KITCHEN).json()["incoming"] if o["id"] == order_id)
    assert not {"delivery_address", "customer_user_id", "mobile"} & set(card)
    staff.ks.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})


# ---------------------------------------------------------------- dish availability (KI-24; DDR-111 (7))
def test_dish_unavailability_needs_rm_approval(world: World, staff: Staff) -> None:
    menu_item, _price = dish(world, "C")
    dishes = staff.ks.get(f"{AVAILABILITY}/dishes?kitchen_id={world.kitchen_a}").json()
    assert any(d["id"] == menu_item for d in dishes)
    try:
        asked = staff.ks.post(
            f"{AVAILABILITY}/requests",
            json={
                "menu_item_id": menu_item,
                "kind": "MAKE_UNAVAILABLE",
                "reason": "TEST – Ingredient 5 spoiled",
            },
        )
        assert asked.status_code == 201, asked.text
        request_id = asked.json()["id"]
        duplicate = staff.km.post(
            f"{AVAILABILITY}/requests",
            json={"menu_item_id": menu_item, "kind": "MAKE_UNAVAILABLE", "reason": "again"},
        )
        assert duplicate.status_code == 409
        # Requested only: the customer menu still shows the dish.
        assert any(m["id"] == menu_item for m in public_menu())
        assert (
            staff.ks.post(
                f"{AVAILABILITY}/requests/{request_id}/decision", json={"approve": True}
            ).status_code
            == 403
        )
        assert (
            staff.other_rm.post(
                f"{AVAILABILITY}/requests/{request_id}/decision", json={"approve": True}
            ).status_code
            == 404
        )
        assert (
            staff.rm.post(
                f"{AVAILABILITY}/requests/{request_id}/decision", json={"approve": False}
            ).status_code
            == 422
        )
        approved = staff.rm.post(f"{AVAILABILITY}/requests/{request_id}/decision", json={"approve": True})
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        assert approved.json()["publication_status"] == "TEMPORARILY_UNAVAILABLE"
        menu = public_menu()
        assert not any(m["id"] == menu_item for m in menu)
        assert (
            scalar(
                world,
                "SELECT count(*) FROM audit.events WHERE action = 'menu.availability.decided' AND target_id = %s",
                menu_item,
            )
            >= 1
        )

        back = staff.ks.post(
            f"{AVAILABILITY}/requests",
            json={"menu_item_id": menu_item, "kind": "MAKE_AVAILABLE", "reason": "Restocked"},
        ).json()
        rejected = staff.rm.post(
            f"{AVAILABILITY}/requests/{back['id']}/decision",
            json={"approve": False, "reason": "Check quality first"},
        )
        assert rejected.json()["status"] == "REJECTED"
        assert rejected.json()["publication_status"] == "TEMPORARILY_UNAVAILABLE"
        again = staff.ks.post(
            f"{AVAILABILITY}/requests",
            json={"menu_item_id": menu_item, "kind": "MAKE_AVAILABLE", "reason": "Checked"},
        ).json()
        restored = staff.ca.post(f"{AVAILABILITY}/requests/{again['id']}/decision", json={"approve": True})
        assert restored.json()["publication_status"] == "PUBLISHED"
        own = staff.ks.get(f"{AVAILABILITY}/requests").json()
        assert {r["id"] for r in own} >= {request_id, back["id"], again["id"]}
        assert staff.other_ks.get(f"{AVAILABILITY}/requests").json() == [] or all(
            r["kitchen_id"] != str(world.kitchen_a)
            for r in staff.other_ks.get(f"{AVAILABILITY}/requests").json()
        )
    finally:
        # Never leave the shared TEST dish off the menu.
        if (
            scalar(world, "SELECT publication_status FROM app.menu_items WHERE id = %s", menu_item)
            != "PUBLISHED"
        ):
            with world.db.transaction():
                act_as(world, "CENTRAL_ADMIN", user_id(world, "+910000000006"), reason="Integration test")
                world.db.execute(
                    "UPDATE app.menu_items SET publication_status = 'PUBLISHED' WHERE id = %s", (menu_item,)
                )
