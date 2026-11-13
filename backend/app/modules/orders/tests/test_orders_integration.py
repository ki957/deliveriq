"""Orders, simulated payments, outbox atomicity and the fulfilment rules (plan Task 7; DDR-16, DDR-109).

Needs the core stack and fixtures (`make up`, `make fixtures`, `make test-integration`). Orders are
placed on the TEST dishes, so every order, item, payment and event is a flagged fixture row. They
stay in the local/test database (status history and audit are append-only) and never reach a
production database (the startup check refuses fixture rows).
"""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import psycopg
import pytest

from app.core.permissions import Grant, Principal, Role
from app.modules.identity.tests.test_auth_integration import World, client, login
from app.modules.payments.domain import PaymentMethod

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

ORDERS = "/api/v1/orders"


# ---------------------------------------------------------------- helpers
def scalar(world: World, sql: str, *params: object) -> Any:
    row = world.db.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def rows(world: World, sql: str, *params: object) -> list[tuple[Any, ...]]:
    return list(world.db.execute(sql, params).fetchall())


def dish(world: World, letter: str) -> str:
    return str(
        scalar(world, "SELECT id FROM app.menu_items WHERE name = %s", f"TEST – Synthetic Dish {letter}")
    )


def place(c: httpx.Client, body: dict[str, Any], key: str | None = None) -> httpx.Response:
    return c.post(ORDERS, json=body, headers={"Idempotency-Key": key or str(uuid.uuid4())})


def body(world: World, method: str, *lines: tuple[str, int], note: str | None = None) -> dict[str, Any]:
    return {
        "lines": [{"menu_item_id": dish(world, letter), "quantity": q} for letter, q in lines],
        "payment_method": method,
        **({"special_instructions": note} if note is not None else {}),
    }


def history(world: World, machine: str, entity: str) -> list[tuple[Any, ...]]:
    return rows(
        world,
        "SELECT from_status, to_status, actor_role, reason, changed_at FROM app.status_history "
        "WHERE machine = %s AND entity_id = %s ORDER BY id",
        machine,
        entity,
    )


def events(world: World, order_id: str) -> list[tuple[Any, ...]]:
    return rows(
        world,
        "SELECT event_type, is_test_fixture, published_at IS NULL FROM app.outbox WHERE aggregate_id = %s ORDER BY id",
        order_id,
    )


def act_as(world: World, role: str, user: uuid.UUID | None, reason: str = "integration test") -> None:
    world.db.execute("SELECT set_config('app.actor_role', %s, true)", (role,))
    world.db.execute("SELECT set_config('app.actor_user_id', %s, true)", (str(user) if user else "",))
    world.db.execute("SELECT set_config('app.reason', %s, true)", (reason,))


def user_id(world: World, mobile: str) -> uuid.UUID:
    return uuid.UUID(str(scalar(world, "SELECT id FROM app.users WHERE mobile_e164 = %s", mobile)))


KITCHEN_PATH = ["ACCEPTED", "PREPARING", "READY_FOR_PICKUP"]


def walk_kitchen(world: World, order_id: str, to: str, start: str = "ACCEPTED") -> None:
    """Move an order forward as the kitchen would (Task 8 builds these actions)."""
    km = user_id(world, world.user("KITCHEN_MANAGER", region=world.region_a, kitchen=world.kitchen_a))
    with world.db.transaction():
        act_as(world, "KITCHEN_MANAGER", km)
        for status in KITCHEN_PATH[KITCHEN_PATH.index(start) : KITCHEN_PATH.index(to) + 1]:
            world.db.execute("UPDATE app.orders SET fulfilment_status = %s WHERE id = %s", (status, order_id))


def assign(world: World, order_id: str, agent: uuid.UUID, *, accept: bool = True) -> str:
    with world.db.transaction():
        act_as(world, "SYSTEM", None)
        assignment = scalar(
            world,
            "INSERT INTO app.delivery_assignments (order_id, agent_user_id, status) VALUES (%s, %s, 'OFFERED') "
            "RETURNING id",
            order_id,
            agent,
        )
    if accept:
        with world.db.transaction():
            act_as(world, "DELIVERY_AGENT", agent)
            world.db.execute(
                "UPDATE app.delivery_assignments SET status = 'ACCEPTED' WHERE id = %s", (assignment,)
            )
    return str(assignment)


@pytest.fixture(scope="module", autouse=True)
def remove_test_orders(world: World) -> Iterator[None]:
    """The shared world deletes its users at the end; remove this module's orders first.

    Status history and audit rows stay (append-only); unpublished outbox rows for them are removed so
    the relay (Task 12) never lands events for orders that no longer exist.
    """
    yield
    # Fail fast rather than wait forever if a test ever leaves a transaction holding locks.
    world.db.execute("SET lock_timeout = '10s'")
    users = world.users or []
    orders = [r[0] for r in rows(world, "SELECT id FROM app.orders WHERE customer_user_id = ANY(%s)", users)]
    world.db.execute(
        "DELETE FROM app.delivery_assignments WHERE order_id = ANY(%s) OR agent_user_id = ANY(%s)",
        (orders, users),
    )
    world.db.execute(
        "DELETE FROM app.outbox WHERE aggregate_id = ANY(%s) AND published_at IS NULL", (orders,)
    )
    world.db.execute("DELETE FROM app.payments WHERE order_id = ANY(%s)", (orders,))
    world.db.execute("DELETE FROM app.order_items WHERE order_id = ANY(%s)", (orders,))
    world.db.execute("DELETE FROM app.orders WHERE id = ANY(%s)", (orders,))


@pytest.fixture(scope="module")
def customer(world: World) -> httpx.Client:
    assert (
        scalar(
            world,
            "SELECT count(*) FROM app.menu_items WHERE is_test_fixture AND publication_status = 'PUBLISHED'",
        )
        >= 3
    ), "run `make fixtures`"
    return login(world.user("CUSTOMER"), "customer")


@pytest.fixture()
def api_services(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Call module services in-process as the real `app_api` role, against the running stack."""
    from app.core.config import get_settings
    from app.core.db import get_engine

    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", os.environ.get("INTEGRATION_DB_PORT", "5433"))
    monkeypatch.setenv("DB_USER", "app_api")
    monkeypatch.setenv("DB_PASSWORD", os.environ["APP_API_PASSWORD"])
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")  # unused by these services
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield
    get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()


# ---------------------------------------------------------------- placement
def test_cod_goes_straight_to_the_kitchen_with_snapshots_and_flags(
    world: World, customer: httpx.Client
) -> None:
    r = place(customer, body(world, "COD", ("A", 3), ("B", 1), note="Less spicy"))
    assert r.status_code == 201, r.text
    order = r.json()
    assert (order["fulfilment_status"], order["status_label"]) == (
        "PENDING_KITCHEN",
        "Awaiting kitchen acceptance",
    )
    assert (order["food_subtotal_paise"], order["delivery_fee_paise"], order["payable_paise"]) == (
        3 * 11100 + 22200,
        3000,
        3 * 11100 + 22200 + 3000,
    )
    assert order["is_test_fixture"] is True and order["agent_assigned"] is False
    assert {(i["item_name"], i["unit_price_paise"], i["quantity"]) for i in order["items"]} == {
        ("TEST – Synthetic Dish A", 11100, 3),
        ("TEST – Synthetic Dish B", 22200, 1),
    }
    payment = order["payment"]
    assert (payment["method"], payment["status"], payment["amount_paise"], payment["simulated"]) == (
        "COD",
        "COLLECTION_PENDING",
        order["payable_paise"],
        True,
    )
    assert payment["sim_reference"].startswith("SIM-")
    # Flags derived in the database: order, items and payment are all fixtures (DDR-109).
    assert scalar(
        world, "SELECT bool_and(is_test_fixture) FROM app.order_items WHERE order_id = %s", order["id"]
    )
    assert scalar(world, "SELECT is_test_fixture FROM app.payments WHERE order_id = %s", order["id"])
    assert events(world, order["id"]) == [("order.placed", True, True)]
    assert [h[1] for h in history(world, "fulfilment", order["id"])] == ["PLACED", "PENDING_KITCHEN"]


def test_prepaid_waits_for_the_simulated_payment(world: World, customer: httpx.Client) -> None:
    order = place(customer, body(world, "SIM_UPI", ("C", 2))).json()
    assert (order["fulfilment_status"], order["status_label"], order["payment"]["status"]) == (
        "PLACED",
        "Order placed",
        "PENDING",
    )
    ok = customer.post(f"{ORDERS}/{order['id']}/payment/simulate", json={"outcome": "SUCCESS"})
    assert ok.status_code == 200, ok.text
    assert (ok.json()["fulfilment_status"], ok.json()["payment"]["status"]) == (
        "PENDING_KITCHEN",
        "SUCCEEDED",
    )
    # Idempotent: the same result again changes nothing; a different one is refused.
    again = customer.post(f"{ORDERS}/{order['id']}/payment/simulate", json={"outcome": "SUCCESS"})
    assert again.status_code == 200 and again.json()["payment"]["status"] == "SUCCEEDED"
    assert (
        customer.post(f"{ORDERS}/{order['id']}/payment/simulate", json={"outcome": "FAILED"}).status_code
        == 409
    )
    assert [e[0] for e in events(world, order["id"])] == ["order.placed", "payment.succeeded"]
    assert (
        customer.post(
            f"{ORDERS}/{place(customer, body(world, 'COD', ('A', 1))).json()['id']}/payment/simulate",
            json={"outcome": "SUCCESS"},
        ).status_code
        == 409
    )  # COD has no online step


@pytest.mark.parametrize(
    ("method", "outcome", "status"), [("SIM_CARD", "FAILED", "FAILED"), ("SIM_UPI", "TIMEOUT", "TIMED_OUT")]
)
def test_failed_or_timed_out_payment_never_reaches_the_kitchen(
    world: World, customer: httpx.Client, method: str, outcome: str, status: str
) -> None:
    order = place(customer, body(world, method, ("A", 5))).json()
    r = customer.post(f"{ORDERS}/{order['id']}/payment/simulate", json={"outcome": outcome})
    assert r.status_code == 200
    assert (r.json()["fulfilment_status"], r.json()["status_label"], r.json()["payment"]["status"]) == (
        "CANCELLED",
        "Cancelled",
        status,
    )
    assert "PENDING_KITCHEN" not in [h[1] for h in history(world, "fulfilment", order["id"])]
    assert [e[0] for e in events(world, order["id"])] == ["order.placed", "payment.failed", "order.cancelled"]
    assert (
        customer.post(f"{ORDERS}/{order['id']}/payment/simulate", json={"outcome": "SUCCESS"}).status_code
        == 409
    )


# ---------------------------------------------------------------- idempotency (DDR-109)
def test_duplicate_submissions_create_one_order_and_one_payment(world: World, customer: httpx.Client) -> None:
    key = str(uuid.uuid4())
    request = body(world, "SIM_CARD", ("B", 2))
    first = place(customer, request, key)
    second = place(customer, request, key)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert scalar(world, "SELECT count(*) FROM app.orders WHERE idempotency_key = %s", key) == 1
    assert scalar(world, "SELECT count(*) FROM app.payments WHERE order_id = %s", first.json()["id"]) == 1
    assert place(customer, body(world, "SIM_CARD", ("B", 3)), key).status_code == 409  # same key, new request


def test_concurrent_duplicates_still_create_one_order(world: World, customer: httpx.Client) -> None:
    key = str(uuid.uuid4())
    request = body(world, "COD", ("C", 1))
    codes: list[int] = []

    def submit() -> None:
        with httpx.Client(
            base_url=customer.base_url, headers=customer.headers, cookies=customer.cookies
        ) as c:
            codes.append(place(c, request, key).status_code)

    threads = [threading.Thread(target=submit) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [200, 200, 200, 201]
    assert scalar(world, "SELECT count(*) FROM app.orders WHERE idempotency_key = %s", key) == 1


# ---------------------------------------------------------------- validation and access
def test_input_validation(world: World, customer: httpx.Client) -> None:
    ok = body(world, "COD", ("A", 1))
    assert customer.post(ORDERS, json=ok).status_code == 422  # no Idempotency-Key
    assert place(customer, {**ok, "special_instructions": "x" * 250}).status_code == 201  # DDR-07
    assert place(customer, {**ok, "special_instructions": "x" * 251}).status_code == 422
    assert place(customer, {**ok, "lines": ok["lines"] * 2}).status_code == 422  # one line per dish
    assert place(customer, {**ok, "payment_method": "CASH"}).status_code == 422
    unpublished = scalar(world, "SELECT id FROM app.menu_items WHERE name = 'TEST – Synthetic Dish D'")
    for menu_item in (str(unpublished), str(uuid.uuid4())):
        r = place(customer, {"lines": [{"menu_item_id": menu_item, "quantity": 1}], "payment_method": "COD"})
        assert r.status_code == 422 and r.json()["message"] == "A dish in this order is not available"


def test_orders_are_private_to_their_customer(world: World, customer: httpx.Client) -> None:
    order = place(customer, body(world, "SIM_UPI", ("A", 1))).json()
    other = login(world.user("CUSTOMER"), "customer")
    assert other.get(f"{ORDERS}/{order['id']}").status_code == 404
    assert (
        other.post(f"{ORDERS}/{order['id']}/payment/simulate", json={"outcome": "SUCCESS"}).status_code == 404
    )
    assert other.post(f"{ORDERS}/{order['id']}/cancel").status_code == 404
    assert order["id"] not in [o["id"] for o in other.get(ORDERS).json()]
    assert order["id"] in [o["id"] for o in customer.get(ORDERS).json()]
    staff = login(world.user("KITCHEN_STAFF", region=world.region_a, kitchen=world.kitchen_a), "kitchen")
    assert place(staff, body(world, "COD", ("A", 1))).status_code == 403
    with client() as anonymous:
        assert anonymous.get(ORDERS).status_code == 401
    other.close()
    staff.close()


# ---------------------------------------------------------------- cancellation (CU-19, DDR-109 routine refund)
def test_cancel_before_acceptance_refunds_prepaid_in_full(world: World, customer: httpx.Client) -> None:
    order = place(customer, body(world, "SIM_CARD", ("B", 1))).json()
    assert customer.post(f"{ORDERS}/{order['id']}/cancel").status_code == 409  # payment still pending
    customer.post(f"{ORDERS}/{order['id']}/payment/simulate", json={"outcome": "SUCCESS"})
    r = customer.post(f"{ORDERS}/{order['id']}/cancel", json={"reason": "Changed my mind"})
    assert r.status_code == 200
    assert (r.json()["fulfilment_status"], r.json()["payment"]["status"]) == ("CANCELLED", "REFUNDED")
    payment = scalar(world, "SELECT id FROM app.payments WHERE order_id = %s", order["id"])
    assert [(h[0], h[1], h[3]) for h in history(world, "payment", str(payment))][-2:] == [
        ("SUCCEEDED", "REFUND_PENDING", "Changed my mind"),
        ("REFUND_PENDING", "REFUNDED", "Changed my mind"),
    ]
    assert [e[0] for e in events(world, order["id"])][-1] == "order.cancelled"
    assert customer.post(f"{ORDERS}/{order['id']}/cancel").status_code == 409


def test_cod_cancel_has_no_refund_and_accepted_orders_cannot_be_cancelled(
    world: World, customer: httpx.Client
) -> None:
    cod = place(customer, body(world, "COD", ("A", 1))).json()
    r = customer.post(f"{ORDERS}/{cod['id']}/cancel")
    assert (r.json()["fulfilment_status"], r.json()["payment"]["status"]) == (
        "CANCELLED",
        "COLLECTION_PENDING",
    )
    accepted = place(customer, body(world, "COD", ("A", 1))).json()
    walk_kitchen(world, accepted["id"], "ACCEPTED")
    assert customer.post(f"{ORDERS}/{accepted['id']}/cancel").status_code == 409


# ---------------------------------------------------------------- Agent Assigned (DDR-16)
def test_agent_assigned_is_shown_without_changing_the_fulfilment_status(
    world: World, customer: httpx.Client
) -> None:
    order = place(customer, body(world, "COD", ("C", 1))).json()
    walk_kitchen(world, order["id"], "PREPARING")
    agent = user_id(world, world.user("DELIVERY_AGENT", region=world.region_a))
    assignment = assign(world, order["id"], agent, accept=False)
    offered = customer.get(f"{ORDERS}/{order['id']}").json()
    assert (offered["status_label"], offered["agent_assigned"]) == ("Preparing", False)

    with world.db.transaction():
        act_as(world, "DELIVERY_AGENT", agent)
        world.db.execute(
            "UPDATE app.delivery_assignments SET status = 'ACCEPTED' WHERE id = %s", (assignment,)
        )
    accepted = customer.get(f"{ORDERS}/{order['id']}").json()
    assert (accepted["fulfilment_status"], accepted["status_label"], accepted["agent_assigned"]) == (
        "PREPARING",
        "Preparing",
        True,
    )
    with world.db.transaction():
        act_as(world, "SYSTEM", None, reason="reassignment")
        world.db.execute(
            "UPDATE app.delivery_assignments SET status = 'REVOKED' WHERE id = %s", (assignment,)
        )
    revoked = customer.get(f"{ORDERS}/{order['id']}").json()
    assert (revoked["fulfilment_status"], revoked["agent_assigned"]) == ("PREPARING", False)
    # No assignment change ever wrote a fulfilment transition.
    assert [h[1] for h in history(world, "fulfilment", order["id"])] == [
        "PLACED",
        "PENDING_KITCHEN",
        "ACCEPTED",
        "PREPARING",
    ]


# ---------------------------------------------------------------- pickup and COD collection (rules for Task 9)
def test_pickup_enters_out_for_delivery_in_the_same_transaction(
    world: World, customer: httpx.Client, api_services: None
) -> None:
    from app.modules.orders import service

    order = place(customer, body(world, "COD", ("A", 2))).json()
    agent_mobile = world.user("DELIVERY_AGENT", region=world.region_a)
    agent = user_id(world, agent_mobile)
    principal = Principal(agent, (Grant(Role.DELIVERY_AGENT, world.region_a),))
    walk_kitchen(world, order["id"], "PREPARING")
    assign(world, order["id"], agent)
    with pytest.raises(service.Conflict, match="ready order"):
        service.record_pickup(principal, uuid.UUID(order["id"]))
    walk_kitchen(world, order["id"], "READY_FOR_PICKUP", start="READY_FOR_PICKUP")
    stranger = Principal(uuid.uuid4(), (Grant(Role.DELIVERY_AGENT, world.region_a),))
    with pytest.raises(service.Forbidden):
        service.record_pickup(stranger, uuid.UUID(order["id"]))

    view = service.record_pickup(principal, uuid.UUID(order["id"]))
    assert view.order.fulfilment_status == "OUT_FOR_DELIVERY"
    assert (view.labels.customer, view.labels.kitchen, view.labels.delivery) == (
        "Out for delivery",
        "Handed Over",
        "In transit",
    )
    pickup, transit = history(world, "fulfilment", order["id"])[-2:]
    assert (pickup[1], transit[1]) == ("PICKED_UP", "OUT_FOR_DELIVERY")
    assert pickup[2] == transit[2] == "DELIVERY_AGENT"
    assert pickup[4] == transit[4]  # same now(): one transaction (DDR-16)
    assert events(world, order["id"])[-1][0] == "delivery.picked_up"

    with pytest.raises(service.Conflict, match="needs a reason"):
        service.record_cod_collection(principal, uuid.UUID(order["id"]), collected=False, reason=None)
    paid = service.record_cod_collection(principal, uuid.UUID(order["id"]), collected=True, reason=None)
    assert paid.payment is not None and paid.payment.status == "COLLECTED"


def test_cod_mismatch_is_recorded_with_its_reason(
    world: World, customer: httpx.Client, api_services: None
) -> None:
    from app.modules.orders import service

    order = place(customer, body(world, "COD", ("B", 1))).json()
    agent = user_id(world, world.user("DELIVERY_AGENT", region=world.region_a))
    principal = Principal(agent, (Grant(Role.DELIVERY_AGENT, world.region_a),))
    walk_kitchen(world, order["id"], "READY_FOR_PICKUP")
    assign(world, order["id"], agent)
    service.record_pickup(principal, uuid.UUID(order["id"]))
    view = service.record_cod_collection(
        principal, uuid.UUID(order["id"]), collected=False, reason="Short by ₹50"
    )
    assert view.payment is not None and view.payment.status == "MISMATCH"
    payment = scalar(world, "SELECT id FROM app.payments WHERE order_id = %s", order["id"])
    assert history(world, "payment", str(payment))[-1][1:4] == ("MISMATCH", "DELIVERY_AGENT", "Short by ₹50")


# ---------------------------------------------------------------- outbox atomicity
def test_a_failure_before_commit_leaves_neither_order_nor_event(
    world: World, customer: httpx.Client, api_services: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.orders import service

    customer_id = user_id(world, world.user("CUSTOMER"))
    principal = Principal(customer_id, (Grant(Role.CUSTOMER),))

    def broken_emit(*_: object, **__: object) -> None:
        raise RuntimeError("simulated crash while writing the event")

    monkeypatch.setattr(service, "emit", broken_emit)
    key = str(uuid.uuid4())
    with pytest.raises(RuntimeError):
        service.place(
            principal,
            idempotency_key=key,
            lines=[(uuid.UUID(dish(world, "A")), 1)],
            method=PaymentMethod.COD,
            special_instructions=None,
        )
    assert scalar(world, "SELECT count(*) FROM app.orders WHERE idempotency_key = %s", key) == 0
    assert (
        scalar(
            world,
            "SELECT count(*) FROM app.payments p JOIN app.orders o ON o.id = p.order_id "
            "WHERE o.idempotency_key = %s",
            key,
        )
        == 0
    )


def _api_conn(*, autocommit: bool = False) -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        dbname=os.environ["POSTGRES_DB"],
        user="app_api",
        password=os.environ["APP_API_PASSWORD"],
        autocommit=autocommit,
    )


def test_a_killed_connection_before_commit_loses_both(world: World) -> None:
    """The API process dies after writing the order and its event but before COMMIT: neither survives."""
    key = str(uuid.uuid4())
    customer_id = user_id(world, world.user("CUSTOMER"))
    conn = _api_conn()
    try:
        conn.execute(
            "SELECT set_config('app.actor_role', 'CUSTOMER', true), set_config('app.actor_user_id', %s, true)",
            (str(customer_id),),
        )
        row = conn.execute(
            "SELECT app.create_order(%s, ARRAY[%s]::uuid[], %s, repeat('0', 64), NULL, 11100, 3000)",
            (customer_id, dish(world, "A"), key),
        ).fetchone()
        assert row is not None
        conn.execute(
            "INSERT INTO app.outbox (event_id, event_type, event_version, occurred_at, aggregate_type, "
            "aggregate_id, idempotency_key, is_test_fixture) "
            "VALUES (gen_random_uuid(), 'order.placed', 1, now(), 'order', %s, %s, true)",
            (row[0], f"atomicity:{key}"),
        )
        # A session may be terminated by another session of the same role (no superuser needed).
        with _api_conn(autocommit=True) as killer:
            killed = killer.execute("SELECT pg_terminate_backend(%s)", (conn.info.backend_pid,)).fetchone()
        assert killed == (True,)
        with pytest.raises(psycopg.OperationalError):
            conn.commit()
    finally:
        conn.close()  # never leave an open transaction (it would hold locks on the test users)
    assert scalar(world, "SELECT count(*) FROM app.orders WHERE idempotency_key = %s", key) == 0
    assert (
        scalar(world, "SELECT count(*) FROM app.outbox WHERE idempotency_key = %s", f"atomicity:{key}") == 0
    )


def test_committed_events_wait_unpublished_for_the_relay(world: World, customer: httpx.Client) -> None:
    order = place(customer, body(world, "COD", ("A", 1))).json()
    # Committed with the order; the worker relay (Task 12) publishes it later; nothing is lost meanwhile.
    assert (
        scalar(
            world,
            "SELECT count(*) FROM app.outbox WHERE aggregate_id = %s AND published_at IS NULL",
            order["id"],
        )
        == 1
    )
    envelope = rows(
        world,
        "SELECT event_version, aggregate_type, region_id, kitchen_id, data ? 'order_id' FROM app.outbox "
        "WHERE aggregate_id = %s",
        order["id"],
    )[0]
    assert envelope == (1, "order", world.region_a, world.kitchen_a, True)


# ---------------------------------------------------------------- fixture flags (DDR-109, leak controls)
def test_mixing_test_and_real_dishes_is_refused_by_the_database(world: World) -> None:
    with world.db.transaction():
        act_as(world, "SYSTEM", None)
        recipe = scalar(
            world,
            "INSERT INTO app.recipes (kitchen_id, name) VALUES (%s, 'Integration real') RETURNING id",
            world.kitchen_a,
        )
        real = scalar(
            world,
            "INSERT INTO app.menu_items (kitchen_id, recipe_id, name, publication_status) "
            "VALUES (%s, %s, 'Integration real dish', 'DRAFT') RETURNING id",
            world.kitchen_a,
            recipe,
        )
    try:
        customer_id = user_id(world, world.user("CUSTOMER"))
        with _api_conn() as api:
            api.execute(
                "SELECT set_config('app.actor_role', 'CUSTOMER', true), "
                "set_config('app.actor_user_id', %s, true)",
                (str(customer_id),),
            )
            with pytest.raises(psycopg.errors.CheckViolation, match="cannot mix TEST and real"):
                api.execute(
                    "SELECT app.create_order(%s, ARRAY[%s, %s]::uuid[], %s, repeat('0', 64), NULL, 1, 0)",
                    (customer_id, dish(world, "A"), real, str(uuid.uuid4())),
                )
            api.rollback()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                api.execute("UPDATE app.orders SET is_test_fixture = false WHERE false")
    finally:
        world.db.execute("DELETE FROM app.menu_items WHERE id = %s", (real,))
        world.db.execute("DELETE FROM app.recipes WHERE id = %s", (recipe,))


def test_production_refuses_fixture_dishes(
    world: World, api_services: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from app.modules.orders import service

    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(is_local_or_test=False))
    principal = Principal(user_id(world, world.user("CUSTOMER")), (Grant(Role.CUSTOMER),))
    key = str(uuid.uuid4())
    with pytest.raises(service.Unavailable):
        service.place(
            principal,
            idempotency_key=key,
            lines=[(uuid.UUID(dish(world, "A")), 1)],
            method=PaymentMethod.COD,
            special_instructions=None,
        )
    assert scalar(world, "SELECT count(*) FROM app.orders WHERE idempotency_key = %s", key) == 0
