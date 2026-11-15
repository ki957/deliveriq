"""Confirmed Operational Actions over the real stack (DDR-69, DDR-120)."""

from __future__ import annotations

import os
import uuid

import pytest

from app.modules.identity.tests.test_auth_integration import World, login
from app.modules.management.tests.test_management_integration import Team, prepaid_order, user_id
from app.modules.recipes.tests.test_workflow_integration import (
    MOBILE,
    act,
    new_test_item,
    sign_all,
    walk_to_validated,
)

pytest_plugins = (
    "app.modules.identity.tests.test_auth_integration",
    "app.modules.management.tests.test_management_integration",
)
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]
BASE = "/api/v1/management/ai/actions"


def test_ca_confirmation_is_audited_idempotent_and_stale_safe(team: Team, world: World) -> None:
    kitchen_id = world.kitchen_a
    settings_url = f"/api/v1/kitchen/settings?kitchen_id={kitchen_id}"
    original = team.ca.get(settings_url)
    assert original.status_code == 200, original.text
    old = original.json()
    target_mode = "BUSY" if old["mode"] != "BUSY" else "NORMAL"
    request = (
        f"Set kitchen {kitchen_id} to {target_mode} with normal capacity "
        f"{old['normal_capacity']['value']} and busy capacity {old['busy_capacity']['value']}."
        " Reason: Task 15A integration"
    )
    try:
        assert team.rm.post(f"{BASE}/proposals", json={"request": request}).status_code == 403
        assert team.km.post(f"{BASE}/proposals", json={"request": request}).status_code == 403
        proposal = team.ca.post(f"{BASE}/proposals", json={"request": request})
        assert proposal.status_code == 200, proposal.text
        body = proposal.json()
        assert body["status"] == "proposed"
        assert body["exact_change"]["before"]["mode"] == old["mode"]
        assert body["exact_change"]["after"]["mode"] == target_mode
        key = str(uuid.uuid4())
        url = f"{BASE}/proposals/{body['proposal_id']}/confirm"
        assert team.rm.post(url, json={"idempotency_key": key}).status_code == 403
        first = team.ca.post(url, json={"idempotency_key": key})
        assert first.status_code == 200, first.text
        assert first.json()["result"]["mode"] == target_mode
        repeat = team.ca.post(url, json={"idempotency_key": key})
        assert repeat.status_code == 200, repeat.text
        assert repeat.json() == first.json()
        assert team.ca.post(url, json={"idempotency_key": str(uuid.uuid4())}).status_code == 409
        audit = world.db.execute(
            "SELECT count(*) FROM audit.events WHERE action = 'management.ai.action.confirmed' "
            "AND target_id = %s",
            (body["proposal_id"],),
        ).fetchone()
        assert audit is not None and audit[0] == 1

        stale = team.ca.post(
            f"{BASE}/proposals",
            json={
                "request": (
                    f"Set kitchen {kitchen_id} to PAUSED with normal capacity "
                    f"{old['normal_capacity']['value']} and busy capacity {old['busy_capacity']['value']}."
                    " Reason: stale check"
                )
            },
        )
        assert stale.status_code == 200, stale.text
        assert stale.json()["status"] == "proposed"
        reused = team.ca.post(
            f"{BASE}/proposals/{stale.json()['proposal_id']}/confirm",
            json={"idempotency_key": key},
        )
        assert reused.status_code == 409, reused.text
        changed = team.ca.put(
            settings_url,
            json={
                "mode": old["mode"],
                "normal_capacity": old["normal_capacity"]["value"],
                "busy_capacity": old["busy_capacity"]["value"],
                "reason": "Change after proposal",
            },
        )
        assert changed.status_code == 200, changed.text
        rejected = team.ca.post(
            f"{BASE}/proposals/{stale.json()['proposal_id']}/confirm",
            json={"idempotency_key": str(uuid.uuid4())},
        )
        assert rejected.status_code == 409, rejected.text
    finally:
        team.ca.put(
            settings_url,
            json={
                "mode": old["mode"],
                "normal_capacity": old["normal_capacity"]["value"],
                "busy_capacity": old["busy_capacity"]["value"],
                "reason": "Restore integration fixture",
            },
        )


def test_unavailable_and_excluded_requests_never_create_proposals(team: Team) -> None:
    for prompt, expected in (
        ("Create a promotion", "unavailable"),
        ("Moderate this review", "unavailable"),
        ("Change regional settings", "unavailable"),
        ("Approve an exceptional refund", "unavailable"),
        ("Change AI model routing", "refused"),
    ):
        response = team.ca.post(f"{BASE}/proposals", json={"request": prompt})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == expected
        assert response.json()["proposal_id"] is None


def test_ca_can_confirm_agent_assignment_through_delivery_service(team: Team, world: World) -> None:
    mobile = world.user("DELIVERY_AGENT", region=world.region_a)
    agent_id = user_id(world, mobile)
    agent = login(mobile, "delivery")
    online = agent.put("/api/v1/delivery/me/availability", json={"online": True})
    assert online.status_code == 200, online.text
    order_id = prepaid_order(world, team)
    accepted = team.km.post(f"/api/v1/kitchen/orders/{order_id}/accept")
    assert accepted.status_code == 200, accepted.text
    prompt = f"Assign order {order_id} to agent {agent_id}. Reason: Manual dispatch test"
    proposed = team.ca.post(f"{BASE}/proposals", json={"request": prompt})
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()["action"] == "agent_assign"
    confirmed = team.ca.post(
        f"{BASE}/proposals/{proposed.json()['proposal_id']}/confirm",
        json={"idempotency_key": str(uuid.uuid4())},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["result"]["order_id"] == order_id
    assigned = world.db.execute(
        "SELECT agent_user_id FROM app.delivery_assignments WHERE order_id = %s "
        "AND status IN ('OFFERED', 'ACCEPTED')",
        (order_id,),
    ).fetchone()
    assert assigned is not None and assigned[0] == agent_id


def test_ca_can_confirm_dish_unavailability_approval(team: Team, world: World) -> None:
    row = world.db.execute("SELECT id FROM app.menu_items WHERE name = 'TEST – Synthetic Dish A'").fetchone()
    assert row is not None
    item_id = str(row[0])
    request = team.ks.post(
        "/api/v1/menu/availability/requests",
        json={"menu_item_id": item_id, "kind": "MAKE_UNAVAILABLE", "reason": "Integration test"},
    )
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]
    try:
        proposed = team.ca.post(
            f"{BASE}/proposals",
            json={"request": (f"Approve dish availability request {request_id}. Reason: Confirm shortage")},
        )
        assert proposed.status_code == 200, proposed.text
        assert proposed.json()["action"] == "dish_availability"
        confirmed = team.ca.post(
            f"{BASE}/proposals/{proposed.json()['proposal_id']}/confirm",
            json={"idempotency_key": str(uuid.uuid4())},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["result"]["status"] == "APPROVED"
        item_state = world.db.execute(
            "SELECT publication_status FROM app.menu_items WHERE id = %s", (item_id,)
        ).fetchone()
        assert item_state is not None and item_state[0] == "TEMPORARILY_UNAVAILABLE"
    finally:
        restore = team.ks.post(
            "/api/v1/menu/availability/requests",
            json={"menu_item_id": item_id, "kind": "MAKE_AVAILABLE", "reason": "Restore fixture"},
        )
        ids = [uuid.UUID(request_id)]
        if restore.status_code == 201:
            ids.append(uuid.UUID(restore.json()["id"]))
            team.ca.post(
                f"/api/v1/menu/availability/requests/{restore.json()['id']}/decision",
                json={"approve": True, "reason": "Restore fixture"},
            )
        world.db.execute("DELETE FROM app.dish_availability_requests WHERE id = ANY(%s)", (ids,))


def test_ca_publishes_only_a_ready_test_menu_item(world: World) -> None:
    accounts = {
        "KITCHEN_MANAGER": login(MOBILE["KITCHEN_MANAGER"], "kitchen"),
        "CENTRAL_ADMIN": login(MOBILE["CENTRAL_ADMIN"], "management"),
    }
    try:
        item = new_test_item(world)
        walk_to_validated(accounts, item)
        sign_all(accounts, item)
        assert act(accounts["KITCHEN_MANAGER"], item.version, "activate").status_code == 200
        ready = accounts["CENTRAL_ADMIN"].post(
            f"/api/v1/menu/manage/items/{item.menu_item}/transitions",
            json={"action": "mark_ready", "reason": "TEST readiness"},
        )
        assert ready.status_code == 200, ready.text
        proposed = accounts["CENTRAL_ADMIN"].post(
            f"{BASE}/proposals",
            json={"request": f"Publish TEST menu item {item.menu_item}. Reason: Demo approval"},
        )
        assert proposed.status_code == 200, proposed.text
        assert proposed.json()["action"] == "menu_publish"
        confirmed = accounts["CENTRAL_ADMIN"].post(
            f"{BASE}/proposals/{proposed.json()['proposal_id']}/confirm",
            json={"idempotency_key": str(uuid.uuid4())},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["result"]["publication_status"] == "PUBLISHED"
        record = world.db.execute(
            "SELECT actor_role FROM audit.menu_publications WHERE menu_item_id = %s "
            "AND to_status = 'PUBLISHED'",
            (item.menu_item,),
        ).fetchone()
        assert record is not None and record[0] == "CENTRAL_ADMIN"
        real = world.db.execute(
            "SELECT id FROM app.menu_items WHERE is_test_fixture = false LIMIT 1"
        ).fetchone()
        if real is not None:
            denied = accounts["CENTRAL_ADMIN"].post(
                f"{BASE}/proposals",
                json={"request": f"Publish TEST menu item {real[0]}. Reason: Must refuse"},
            )
            assert denied.status_code == 422
    finally:
        for account in accounts.values():
            account.close()
