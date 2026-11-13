"""Unified management over the real stack (plan Task 10; #10 §16; DDR-114).

Needs the core stack and fixtures. An RM of the module's second region (world.region_b) must see nothing of
the Chennai region; the Chennai RM and the CA see it. Orders are TEST orders; the module rejects any order
it leaves held and removes what it created.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.modules.identity.tests.test_auth_integration import World, client, login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

M = "/api/v1/management"
KITCHEN = "/api/v1/kitchen/orders"
DELIVERY = "/api/v1/delivery"
SEED_LAT, SEED_LNG = 13.0835, 80.2710


def scalar(world: World, sql: str, *params: object) -> Any:
    row = world.db.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def user_id(world: World, mobile: str) -> uuid.UUID:
    return uuid.UUID(str(scalar(world, "SELECT id FROM app.users WHERE mobile_e164 = %s", mobile)))


class Team:
    def __init__(self, world: World) -> None:
        a, b = world.region_a, world.region_b
        self.rm = login(world.user("REGIONAL_MANAGER", region=a), "management")
        self.rm_mobile = world.mobiles[-1] if world.mobiles else ""
        self.other_rm = login(world.user("REGIONAL_MANAGER", region=b), "management")
        self.ca = login(world.user("CENTRAL_ADMIN"), "management")
        self.ks = login(world.user("KITCHEN_STAFF", region=a, kitchen=world.kitchen_a), "kitchen")
        self.km = login(world.user("KITCHEN_MANAGER", region=a, kitchen=world.kitchen_a), "kitchen")
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
def team(world: World) -> Iterator[Team]:
    t = Team(world)
    yield t
    world.db.execute("SET lock_timeout = '10s'")
    users = [
        r[0]
        for r in world.db.execute("SELECT id FROM app.users WHERE mobile_e164 = ANY(%s)", (world.mobiles,))
    ]
    orders = [
        r[0] for r in world.db.execute("SELECT id FROM app.orders WHERE customer_user_id = ANY(%s)", (users,))
    ]
    for (order_id,) in world.db.execute(
        "SELECT id FROM app.orders WHERE id = ANY(%s) AND fulfilment_status IN ('ACCEPTED', 'PREPARING', "
        "'READY_FOR_PICKUP')",
        (orders,),
    ).fetchall():
        t.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test cleanup"})
    world.db.execute("DELETE FROM app.agent_availability WHERE agent_user_id = ANY(%s)", (users,))
    world.db.execute("DELETE FROM app.delivery_locations WHERE order_id = ANY(%s)", (orders,))
    world.db.execute("DELETE FROM app.delivery_otps WHERE order_id = ANY(%s)", (orders,))
    world.db.execute(
        "DELETE FROM app.delivery_assignments WHERE order_id = ANY(%s) OR agent_user_id = ANY(%s)",
        (orders, users),
    )
    world.db.execute("DELETE FROM app.stock_reservations WHERE order_id = ANY(%s)", (orders,))
    world.db.execute(
        "DELETE FROM app.outbox WHERE aggregate_id = ANY(%s) AND published_at IS NULL", (orders,)
    )
    world.db.execute("DELETE FROM app.payments WHERE order_id = ANY(%s)", (orders,))
    world.db.execute("DELETE FROM app.order_items WHERE order_id = ANY(%s)", (orders,))
    world.db.execute("DELETE FROM app.orders WHERE id = ANY(%s)", (orders,))
    world.db.execute("DELETE FROM app.customer_addresses WHERE customer_user_id = ANY(%s)", (users,))
    world.db.execute("UPDATE app.role_assignments SET granted_by = NULL WHERE granted_by = ANY(%s)", (users,))
    world.db.execute("DELETE FROM app.role_assignments WHERE user_id = ANY(%s)", (users,))


def prepaid_order(world: World, team: Team) -> str:
    row = world.db.execute(
        "SELECT id, price_paise FROM app.menu_items WHERE name = 'TEST – Synthetic Dish A'"
    ).fetchone()
    assert row is not None, "run `make fixtures`"
    placed = team.customer.post(
        "/api/v1/orders",
        json={"lines": [{"menu_item_id": str(row[0]), "quantity": 5, "unit_price_paise": row[1]}],
              "payment_method": "SIM_UPI", "address_id": team.address},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )  # fmt: skip
    assert placed.status_code == 201, placed.text
    order_id = str(placed.json()["id"])
    team.customer.post(f"/api/v1/orders/{order_id}/payment/simulate", json={"outcome": "SUCCESS"})
    return order_id


# ---------------------------------------------------------------- region scope (#10 §16.1, §16.13)
def test_regional_manager_sees_only_assigned_regions_across_views_and_exports(
    world: World, team: Team
) -> None:
    order_id = prepaid_order(world, team)
    own = team.rm.get(f"{M}/orders").json()
    assert any(r["id"] == order_id for r in own["rows"])
    assert team.ca.get(f"{M}/orders/{order_id}").status_code == 200
    other = team.other_rm
    assert all(r["id"] != order_id for r in other.get(f"{M}/orders").json()["rows"])
    assert other.get(f"{M}/orders/{order_id}").status_code == 404
    assert order_id not in other.get(f"{M}/orders.csv").text
    assert order_id in team.rm.get(f"{M}/orders.csv").text
    assert all(k["id"] != str(world.kitchen_a) for k in other.get(f"{M}/kitchens").json())
    assert other.get(f"{M}/kitchens/{world.kitchen_a}/inventory").status_code == 404
    assert (
        team.rm.get(f"{M}/kitchens/{world.kitchen_a}/inventory").json()["stock"][0]["is_test_fixture"] is True
    )
    assert other.get(f"{M}/overview").json()["orders_by_status"].get("PENDING_KITCHEN", 0) == 0
    assert other.get(f"/api/v1/kitchen/orders?kitchen_id={world.kitchen_a}").status_code == 404
    assert team.ks.get(f"{M}/overview").status_code == 403
    with client() as anonymous:
        assert anonymous.get(f"{M}/overview").status_code == 401
    # The export itself is audited.
    assert scalar(world, "SELECT count(*) FROM audit.events WHERE action = 'management.export.orders' "
                  "AND occurred_at > now() - interval '1 minute'") >= 2  # fmt: skip
    team.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})


def test_date_ranges_are_bounded(team: Team) -> None:
    start = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    assert team.rm.get(f"{M}/orders", params={"date_from": start}).status_code == 422
    assert team.rm.get(f"{M}/audit", params={"date_from": start}).status_code == 422


# ---------------------------------------------------------------- order detail and refunds (MG-05; DDR-114 (6), (9))
def test_order_timeline_and_refund_record_with_exceptional_refunds_disabled(world: World, team: Team) -> None:
    order_id = prepaid_order(world, team)
    assert team.ks.post(f"{KITCHEN}/{order_id}/accept").status_code == 200
    assert (
        team.rm.post(
            f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration: cannot fulfil"}
        ).status_code
        == 200
    )
    detail = team.rm.get(f"{M}/orders/{order_id}").json()
    steps = [(t["machine"], t["to_status"], t["actor_role"]) for t in detail["timeline"]]
    assert ("fulfilment", "REJECTED", "REGIONAL_MANAGER") in steps
    assert ("payment", "REFUNDED", "REGIONAL_MANAGER") in steps
    assert any(t["reason"] == "Integration: cannot fulfil" for t in detail["timeline"])
    assert detail["order"]["status_label"] == "Rejected"
    refunds = team.rm.get(f"{M}/refunds").json()
    assert refunds["exceptional_refunds_enabled"] is False and "DDR-44" in refunds["disabled_reason"]
    row = next(r for r in refunds["rows"] if r["order_id"] == order_id)
    assert row["status"] == "REFUNDED" and row["actor_role"] == "REGIONAL_MANAGER" and row["amount_paise"] > 0
    assert all(r["order_id"] != order_id for r in team.other_rm.get(f"{M}/refunds").json()["rows"])


# ---------------------------------------------------------------- staff access (#10 §4, §16.2–§16.5; DDR-114 (3)–(5))
def test_staff_provisioning_scope_and_no_self_escalation(world: World, team: Team) -> None:
    new_ks = world.mobile()
    body = {"display_name": "TEST Staff", "mobile": new_ks, "role": "KITCHEN_STAFF", "region_id": str(world.region_a),
            "kitchen_id": str(world.kitchen_a), "reason": "New hire"}  # fmt: skip
    created = team.rm.post(f"{M}/staff", json=body)
    assert created.status_code == 201, created.text
    assert "*" in created.json()["mobile_masked"]
    assert team.rm.post(f"{M}/staff", json=body).status_code == 409  # already has the role
    # The new person signs in with OTP and has exactly that role.
    assert [g["role"] for g in login(new_ks, "kitchen").get("/api/v1/me").json()["roles"]] == [
        "KITCHEN_STAFF"
    ]
    # RM cannot create RMs, act in another region, grant CA, or escalate themselves.
    rm_body = {**body, "mobile": world.mobile(), "role": "REGIONAL_MANAGER", "kitchen_id": None}
    assert team.rm.post(f"{M}/staff", json=rm_body).status_code == 403
    assert team.other_rm.post(f"{M}/staff", json={**body, "mobile": world.mobile()}).status_code == 403
    assert team.rm.post(f"{M}/staff", json={**rm_body, "role": "CENTRAL_ADMIN"}).status_code == 422
    assert team.rm.post(f"{M}/staff", json={**body, "mobile": team.rm_mobile, "role": "DELIVERY_AGENT",
                                            "kitchen_id": None}).status_code == 403  # fmt: skip
    assert team.rm.put(f"{M}/staff/{user_id(world, team.rm_mobile)}/status",
                       json={"active": False, "reason": "x"}).status_code == 403  # fmt: skip
    # The CA may create an RM.
    assert team.ca.post(f"{M}/staff", json=rm_body).status_code == 201
    staff = team.rm.get(f"{M}/staff").json()
    assert any(s["display_name"] == "TEST Staff" for s in staff)
    assert all(s["role"] != "REGIONAL_MANAGER" for s in staff)  # RM manages KM, KS and agents only
    assert scalar(world, "SELECT count(*) FROM audit.events WHERE action = 'management.staff.role_granted' "
                  "AND target_id = %s", str(user_id(world, new_ks))) == 1  # fmt: skip


def test_role_removal_and_deactivation_take_effect_at_once(world: World, team: Team) -> None:
    mobile = world.mobile()
    created = team.rm.post(f"{M}/staff", json={"display_name": "TEST Agent", "mobile": mobile, "role": "DELIVERY_AGENT",
                                               "region_id": str(world.region_a), "reason": "Hire"})  # fmt: skip
    assert created.status_code == 201
    agent = login(mobile, "delivery")
    assert agent.put(f"{DELIVERY}/me/availability", json={"online": True}).status_code == 200

    # An accepted delivery blocks deactivation (MG-01).
    order_id = prepaid_order(world, team)
    assert team.ks.post(f"{KITCHEN}/{order_id}/accept").status_code == 200
    offers = agent.get(f"{DELIVERY}/me").json()
    if offers["assignment"] and offers["order"]["order_id"] == order_id:
        agent.post(f"{DELIVERY}/assignments/{offers['assignment']['id']}/respond", json={"accept": True})
        blocked = team.rm.put(
            f"{M}/staff/{user_id(world, mobile)}/status", json={"active": False, "reason": "Leaving"}
        )
        assert blocked.status_code == 409
    team.km.post(f"{KITCHEN}/{order_id}/reject", json={"reason": "Integration test"})

    done = team.rm.put(
        f"{M}/staff/{user_id(world, mobile)}/status", json={"active": False, "reason": "Leaving"}
    )
    assert done.status_code == 204
    assert agent.get(f"{DELIVERY}/me").status_code == 401  # sessions ended at once
    assert team.other_rm.put(f"{M}/staff/{user_id(world, mobile)}/status",
                             json={"active": True, "reason": "x"}).status_code == 404  # fmt: skip
    assert (
        team.rm.put(
            f"{M}/staff/{user_id(world, mobile)}/status", json={"active": True, "reason": "Back"}
        ).status_code
        == 204
    )

    # Removing the role also ends sessions.
    again = login(mobile, "delivery")
    assert again.get(f"{DELIVERY}/me").status_code == 200
    assignment = created.json()["assignment_id"]
    assert (
        team.rm.post(f"{M}/staff/roles/{assignment}/remove", json={"reason": "Role ended"}).status_code == 204
    )
    assert again.get(f"{DELIVERY}/me").status_code == 401


# ---------------------------------------------------------------- audit viewer (#10 §12; DDR-114 (7))
def test_audit_viewer_is_scoped_and_exportable(world: World, team: Team) -> None:
    rm_rows = team.rm.get(f"{M}/audit").json()["rows"]
    assert rm_rows and all(r["region_id"] == str(world.region_a) for r in rm_rows)
    ca_rows = team.ca.get(f"{M}/audit", params={"action": "auth."}).json()["rows"]
    assert any(r["region_id"] is None for r in ca_rows)  # global events (e.g. logins) for the CA only
    assert all(r["region_id"] != str(world.region_a) for r in team.other_rm.get(f"{M}/audit").json()["rows"])
    csv_text = team.ca.get(f"{M}/audit.csv", params={"action": "management."}).text
    assert csv_text.startswith("occurred_at,actor_role,actor,action")
    assert team.ks.get(f"{M}/audit").status_code == 403


def test_deliveries_board_and_overview_counts(world: World, team: Team) -> None:
    overview = team.rm.get(f"{M}/overview").json()
    assert overview["kpis_available"] is False
    assert any(
        k["id"] == str(world.kitchen_a) and k["intake"]["mode"] == "NORMAL" for k in overview["kitchens"]
    )
    assert isinstance(team.rm.get(f"{M}/deliveries").json(), list)
    assert team.other_rm.get(f"{M}/deliveries").json() == [] or all(
        d["order_id"] for d in team.other_rm.get(f"{M}/deliveries").json()
    )
