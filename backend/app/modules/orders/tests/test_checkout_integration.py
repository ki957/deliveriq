"""Task 6 checkout rules over real HTTP and the real database (plan Task 6; CU-01–CU-17; DDR-53, DDR-110).

Needs the core stack and fixtures (`make up`, `make fixtures`, `make test-integration`). Orders use the
TEST dishes, so every order, item, payment and event is a flagged fixture row. Prices changed here are
restored at the end of each test; test users, carts, addresses and orders are removed afterwards.
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

from app.modules.identity.tests.test_auth_integration import World, client, login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

ORDERS, CART = "/api/v1/orders", "/api/v1/cart"
# Kitchen KIT-CHN-001 is at 13.0827, 80.2707 (#15 §3, synthetic). #15 §5 seed address is ~0.1 km away.
NEAR = (13.0835, 80.2710)
FAR = (13.1300, 80.2707)  # ~5.3 km north: outside the 4 km straight-line limit


def scalar(world: World, sql: str, *params: object) -> Any:
    row = world.db.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def dish(world: World, letter: str) -> str:
    return str(
        scalar(world, "SELECT id FROM app.menu_items WHERE name = %s", f"TEST – Synthetic Dish {letter}")
    )


def price(world: World, letter: str) -> int:
    return int(scalar(world, "SELECT price_paise FROM app.menu_items WHERE id = %s", dish(world, letter)))


def add_address(c: httpx.Client, point: tuple[float, float], label: str = "Home") -> dict[str, Any]:
    r = c.post(
        "/api/v1/me/addresses",
        json={
            "label": label,
            "address_line": "Synthetic Test Address, Chennai",
            "lat": point[0],
            "lng": point[1],
        },
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


def order_body(
    world: World,
    address: str,
    *lines: tuple[str, int],
    method: str = "COD",
    coupon: str | None = None,
    prices: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "lines": [
            {
                "menu_item_id": dish(world, letter),
                "quantity": q,
                "unit_price_paise": (prices or {}).get(letter, price(world, letter)),
            }
            for letter, q in lines
        ],
        "payment_method": method,
        "address_id": address,
        **({"coupon_code": coupon} if coupon else {}),
    }


def place(c: httpx.Client, body: dict[str, Any], key: str | None = None) -> httpx.Response:
    return c.post(ORDERS, json=body, headers={"Idempotency-Key": key or str(uuid.uuid4())})


@pytest.fixture(scope="module", autouse=True)
def cleanup(world: World) -> Iterator[None]:
    yield
    world.db.execute("SET lock_timeout = '10s'")
    users = world.users or []
    orders = [
        r[0]
        for r in world.db.execute(
            "SELECT id FROM app.orders WHERE customer_user_id = ANY(%s)", (users,)
        ).fetchall()
    ]
    world.db.execute(
        "DELETE FROM app.outbox WHERE aggregate_id = ANY(%s) AND published_at IS NULL", (orders,)
    )
    world.db.execute("DELETE FROM app.payments WHERE order_id = ANY(%s)", (orders,))
    world.db.execute("DELETE FROM app.order_items WHERE order_id = ANY(%s)", (orders,))
    world.db.execute("DELETE FROM app.orders WHERE id = ANY(%s)", (orders,))
    world.db.execute("DELETE FROM app.cart_items WHERE customer_user_id = ANY(%s)", (users,))
    world.db.execute("DELETE FROM app.customer_addresses WHERE customer_user_id = ANY(%s)", (users,))
    world.db.execute("DELETE FROM app.coupons WHERE code LIKE 'TESTLIM%%'")


@pytest.fixture()
def shopper(world: World) -> Iterator[tuple[httpx.Client, str]]:
    assert scalar(world, "SELECT count(*) FROM app.coupons WHERE code = 'TEST50'") == 1, "run `make fixtures`"
    c = login(world.user("CUSTOMER"), "customer")
    yield c, add_address(c, NEAR)["id"]
    c.close()


@pytest.fixture()
def dish_c_price(world: World) -> Iterator[int]:
    """Dish C's published price, restored after a test changes it."""
    original = price(world, "C")
    yield original
    world.db.execute("UPDATE app.menu_items SET price_paise = %s WHERE id = %s", (original, dish(world, "C")))


# ---------------------------------------------------------------- serviceability (CU-01–CU-04)
def test_visitors_can_check_serviceability_without_an_account() -> None:
    with client() as anonymous:
        near = anonymous.get("/api/v1/serviceability", params={"lat": NEAR[0], "lng": NEAR[1]}).json()
        far = anonymous.get("/api/v1/serviceability", params={"lat": FAR[0], "lng": FAR[1]}).json()
        assert anonymous.get("/api/v1/serviceability", params={"lat": 0, "lng": 0}).status_code == 422
    assert near["serviceable"] is True and near["road_km_estimated"] is True
    assert near["kitchen_location_is_synthetic"] is True
    assert (far["serviceable"], far["straight_line_ok"]) == (False, False)
    assert float(far["straight_line_km"]) > 4


def test_addresses_are_private_with_one_default(world: World, shopper: tuple[httpx.Client, str]) -> None:
    c, first = shopper
    second = add_address(c, FAR, "Office")
    listed = c.get("/api/v1/me/addresses").json()
    assert [(a["label"], a["is_default"]) for a in listed] == [("Home", True), ("Office", False)]
    assert listed[1]["serviceability"]["serviceable"] is False
    assert c.post(f"/api/v1/me/addresses/{second['id']}/default").json()["is_default"] is True
    assert [a["is_default"] for a in c.get("/api/v1/me/addresses").json()].count(True) == 1
    other = login(world.user("CUSTOMER"), "customer")
    assert other.post(f"/api/v1/me/addresses/{first}/default").status_code == 404
    assert other.delete(f"/api/v1/me/addresses/{first}").status_code == 404
    other.close()
    assert c.delete(f"/api/v1/me/addresses/{second['id']}").status_code == 204
    assert [a["id"] for a in c.get("/api/v1/me/addresses").json()] == [first]


def test_out_of_area_address_cannot_order(world: World, shopper: tuple[httpx.Client, str]) -> None:
    c, _ = shopper
    far = add_address(c, FAR, "Far")["id"]
    r = place(c, order_body(world, far, ("A", 5)))
    assert r.status_code == 422 and r.json()["code"] == "not_serviceable"
    assert r.json()["road_km_estimated"] is True


# ---------------------------------------------------------------- menu (CU-06, CU-07, CU-08)
def test_menu_filters_and_dish_detail(world: World) -> None:
    with client() as visitor:
        items = visitor.get("/api/v1/menu/items").json()
        names = {i["name"] for i in items}
        assert {"TEST – Synthetic Dish A", "TEST – Synthetic Dish B", "TEST – Synthetic Dish C"} <= names
        assert "TEST – Synthetic Dish D" not in names  # unpublished
        cheap = visitor.get("/api/v1/menu/items", params={"max_price_paise": 20000}).json()
        assert {i["name"] for i in cheap} >= {"TEST – Synthetic Dish A"}
        assert all(i["price_paise"] <= 20000 for i in cheap)
        assert (
            visitor.get("/api/v1/menu/items", params={"q": "Dish B"}).json()[0]["name"]
            == "TEST – Synthetic Dish B"
        )
        assert visitor.get("/api/v1/menu/items", params={"q": "%"}).json() == []  # wildcards are literal
        assert all(i["is_veg"] for i in visitor.get("/api/v1/menu/items", params={"veg": True}).json())
        assert visitor.get("/api/v1/menu/items", params={"bestseller": True}).json() == []  # none flagged
        filters = visitor.get("/api/v1/menu/filters").json()
        assert "TEST" in filters["spice_levels"] and "TEST – Category" in filters["categories"]
        assert filters["has_bestsellers"] is False
        detail = visitor.get(f"/api/v1/menu/items/{dish(world, 'A')}").json()
        assert detail["ingredients"] == ["TEST – Ingredient 1", "TEST – Ingredient 2"]
        assert detail["customizations"] == []
        d_id = scalar(world, "SELECT id FROM app.menu_items WHERE name = 'TEST – Synthetic Dish D'")
        assert visitor.get(f"/api/v1/menu/items/{d_id}").status_code == 404


# ---------------------------------------------------------------- cart (CU-11, CU-13, CU-14)
def test_cart_is_persisted_and_quoted(world: World, shopper: tuple[httpx.Client, str]) -> None:
    c, address = shopper
    assert c.put(f"{CART}/items/{dish(world, 'A')}", json={"quantity": 2}).status_code == 200
    c.put(f"{CART}/items/{dish(world, 'B')}", json={"quantity": 1})
    quote = c.get(CART, params={"address_id": address}).json()
    assert [(line["name"], line["quantity"]) for line in quote["lines"]] == [
        ("TEST – Synthetic Dish A", 2),
        ("TEST – Synthetic Dish B", 1),
    ]
    assert quote["bill"]["food_subtotal_paise"] == 2 * 11100 + 22200
    assert (quote["bill"]["minimum_met"], quote["bill"]["delivery_fee_paise"]) == (False, 3000)
    assert quote["blockers"] == ["below_minimum"]
    assert quote["serviceability"]["serviceable"] is True
    c.put(f"{CART}/items/{dish(world, 'C')}", json={"quantity": 1})
    quote = c.get(CART, params={"address_id": address, "coupon_code": "test50"}).json()
    assert quote["blockers"] == [] and quote["coupon_code"] == "TEST50"
    assert quote["bill"]["discount_paise"] == 5000
    assert c.get(CART).json()["blockers"] == ["address_required"]
    assert c.get(CART, params={"coupon_code": "NOPE1"}).json()["coupon_error"] == "coupon_unknown"
    assert c.put(f"{CART}/items/{dish(world, 'A')}", json={"quantity": 0}).status_code == 422
    unpublished = scalar(world, "SELECT id FROM app.menu_items WHERE name = 'TEST – Synthetic Dish D'")
    r = c.put(f"{CART}/items/{unpublished}", json={"quantity": 1})
    assert r.status_code == 422 and r.json()["code"] == "dish_unavailable"
    with client() as anonymous:
        assert anonymous.get(CART).status_code == 401


def test_unavailable_dish_is_removed_only_with_confirmation(
    world: World, shopper: tuple[httpx.Client, str]
) -> None:
    c, _ = shopper
    c.put(f"{CART}/items/{dish(world, 'A')}", json={"quantity": 5})
    # The Regional Manager marks the dish temporarily unavailable (DDR-11; RM/CA only, reason required).
    a_id, original = dish(world, "A"), price(world, "A")
    rm = scalar(
        world,
        "SELECT id FROM app.users WHERE mobile_e164 = %s",
        world.user("REGIONAL_MANAGER", region=world.region_a),
    )

    def as_rm(status: str) -> None:
        with world.db.transaction():
            world.db.execute(
                "SELECT set_config('app.actor_role', 'REGIONAL_MANAGER', true), "
                "set_config('app.actor_user_id', %s, true), "
                "set_config('app.reason', 'integration test: dish unavailable', true)",
                (str(rm),),
            )
            world.db.execute(
                "UPDATE app.menu_items SET publication_status = %s WHERE id = %s", (status, a_id)
            )

    as_rm("TEMPORARILY_UNAVAILABLE")
    try:
        cart = c.get(CART).json()
        assert cart["lines"][0]["available"] is False and "dish_unavailable" in cart["blockers"]
        assert len(cart["lines"]) == 1  # still there until the customer confirms (CU-14)
        with client() as visitor:
            assert a_id not in [i["id"] for i in visitor.get("/api/v1/menu/items").json()]  # hidden (CU-07)
        assert c.post(f"{CART}/remove-unavailable").json()["lines"] == []
    finally:
        as_rm("PUBLISHED")
    assert price(world, "A") == original


def test_price_protection_and_explicit_confirmation(
    world: World, shopper: tuple[httpx.Client, str], dish_c_price: int
) -> None:
    c, address = shopper
    c_id = dish(world, "C")
    c.put(f"{CART}/items/{c_id}", json={"quantity": 2})
    raised = dish_c_price + 1000
    world.db.execute("UPDATE app.menu_items SET price_paise = %s WHERE id = %s", (raised, c_id))

    # Within 30 minutes the cart price is protected: the order is charged the old price.
    protected = c.get(CART).json()["lines"][0]
    assert (protected["charge_price_paise"], protected["price_changed"]) == (dish_c_price, False)

    # After 30 minutes the new price applies and needs explicit confirmation (CU-13).
    # Age every line of this cart (the shopper is the only customer with Dish C in a cart here).
    world.db.execute(
        "UPDATE app.cart_items SET added_at = now() - interval '31 minutes' WHERE menu_item_id = %s",
        (c_id,),
    )
    expired = c.get(CART).json()
    assert expired["lines"][0]["price_changed"] is True and "price_changed" in expired["blockers"]
    r = place(c, order_body(world, address, ("C", 2), prices={"C": dish_c_price}))
    assert r.status_code == 409 and r.json()["code"] == "price_changed"
    assert r.json()["price_changes"] == [
        {"menu_item_id": c_id, "stated_price_paise": dish_c_price, "current_price_paise": raised}
    ]
    accepted = c.post(f"{CART}/items/{c_id}/accept-price").json()["lines"][0]
    assert (accepted["cart_price_paise"], accepted["price_changed"]) == (raised, False)
    order = place(c, order_body(world, address, ("C", 2), prices={"C": raised}))
    assert order.status_code == 201, order.text
    assert order.json()["items"][0]["unit_price_paise"] == raised  # the accepted price is stored
    assert c.get(CART).json()["lines"] == []  # ordered dishes leave the cart


# ---------------------------------------------------------------- minimum, coupon, fee (CU-12, CU-16; DDR-53, DDR-38)
def test_499_is_refused_and_500_accepted(
    world: World, shopper: tuple[httpx.Client, str], dish_c_price: int
) -> None:
    c, address = shopper
    c_id = dish(world, "C")
    for value, expected in ((49900, 422), (50000, 201)):
        world.db.execute("UPDATE app.menu_items SET price_paise = %s WHERE id = %s", (value, c_id))
        c.delete(CART)
        r = place(c, order_body(world, address, ("C", 1), prices={"C": value}))
        assert r.status_code == expected, r.text
        if expected == 422:
            assert (r.json()["code"], r.json()["minimum_paise"]) == ("below_minimum", 50000)
        else:
            assert (r.json()["food_subtotal_paise"], r.json()["delivery_fee_paise"]) == (50000, 3000)


def test_coupon_after_the_minimum_may_take_the_payable_below_500(
    world: World, shopper: tuple[httpx.Client, str], dish_c_price: int
) -> None:
    c, address = shopper
    world.db.execute("UPDATE app.menu_items SET price_paise = 50000 WHERE id = %s", (dish(world, "C"),))
    r = place(c, order_body(world, address, ("C", 1), coupon="TEST50", prices={"C": 50000}))
    assert r.status_code == 201, r.text
    o = r.json()
    assert (o["food_subtotal_paise"], o["delivery_fee_paise"], o["discount_paise"], o["payable_paise"]) == (
        50000,
        3000,
        5000,
        48000,
    )
    assert o["payment"]["amount_paise"] == 48000
    bad = place(c, order_body(world, address, ("A", 5), coupon="NOPE1"))
    assert bad.status_code == 422 and bad.json()["code"] == "coupon_unknown"


def test_coupon_usage_limit_holds_under_concurrent_checkouts(world: World) -> None:
    code = f"TESTLIM{uuid.uuid4().hex[:6].upper()}"
    world.db.execute(
        "INSERT INTO app.coupons (code, discount_paise, usage_limit, is_active, is_test_fixture) "
        "VALUES (%s, 1000, 1, true, true)",
        (code,),
    )
    shoppers = []
    for _ in range(3):
        c = login(world.user("CUSTOMER"), "customer")
        shoppers.append((c, add_address(c, NEAR)["id"]))
    codes: list[int] = []

    def checkout(c: httpx.Client, address: str) -> None:
        codes.append(place(c, order_body(world, address, ("A", 5), coupon=code)).status_code)

    threads = [threading.Thread(target=checkout, args=s) for s in shoppers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [201, 422, 422]
    assert scalar(world, "SELECT used_count FROM app.coupons WHERE code = %s", code) == 1
    for c, _ in shoppers:
        c.close()


def test_delivery_fee_is_30_at_every_subtotal(world: World, shopper: tuple[httpx.Client, str]) -> None:
    c, address = shopper
    for lines in ((("A", 5),), (("C", 9), ("B", 9))):
        r = place(c, order_body(world, address, *lines))
        assert r.status_code == 201 and r.json()["delivery_fee_paise"] == 3000


def test_checkout_snapshot_and_test_labels(world: World, shopper: tuple[httpx.Client, str]) -> None:
    c, address = shopper
    order = place(c, order_body(world, address, ("B", 3), method="SIM_UPI")).json()
    assert order["is_test_fixture"] is True and order["payment"]["simulated"] is True
    assert order["delivery_address"] == "Synthetic Test Address, Chennai"
    assert order["road_km_estimated"] is True
    row = world.db.execute(
        "SELECT straight_line_km, road_km FROM app.orders WHERE id = %s", (order["id"],)
    ).fetchone()
    assert row is not None and row[0] is not None
    assert Decimal(str(row[1])) > Decimal(str(row[0]))  # stub road = straight-line x 1.4


def test_unknown_or_foreign_address_is_refused(world: World, shopper: tuple[httpx.Client, str]) -> None:
    _, address = shopper
    other = login(world.user("CUSTOMER"), "customer")
    r = place(other, order_body(world, address, ("A", 5)))
    assert r.status_code == 422 and r.json()["code"] == "address_unknown"
    other.close()


def test_special_instructions_limit_holds_when_the_ui_is_bypassed(
    world: World, shopper: tuple[httpx.Client, str]
) -> None:
    c, address = shopper
    body = order_body(world, address, ("A", 5))
    assert place(c, {**body, "special_instructions": "x" * 250}).status_code == 201
    assert place(c, {**body, "special_instructions": "x" * 251}).status_code == 422  # DDR-07
