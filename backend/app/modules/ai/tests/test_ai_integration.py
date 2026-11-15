"""Management Copilot scope and routing checks (DDR-119)."""

from __future__ import annotations

import os
from typing import cast

import pytest

from app.modules.identity.tests.test_auth_integration import World, login
from app.modules.management.tests.test_management_integration import Team

pytest_plugins = (
    "app.modules.identity.tests.test_auth_integration",
    "app.modules.management.tests.test_management_integration",
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

A = "/api/v1/management/ai"


def test_status_is_labelled_and_settings_are_ca_only(team: Team) -> None:
    status = team.ca.get(f"{A}/status")
    assert status.status_code == 200
    body = status.json()
    assert body["enabled"] is True
    assert body["knowledge_status"] == "pending approval"
    assert body["conversation_turn_limit"] == 6
    assert body["request_metadata_retention_days"] == 90
    assert team.rm.get(f"{A}/settings").status_code == 403
    assert (
        team.rm.put(f"{A}/settings", json={"logical_model": "strong", "reason": "Task 15 test"}).status_code
        == 403
    )


def test_copilot_is_read_only_and_conversation_is_deletable(team: Team, world: World) -> None:
    response = team.ca.post(f"{A}/copilot", json={"question": "show operational status"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["simulated"] is True
    assert body["read_only"] is True
    assert body["knowledge_status"] == "pending approval"
    assert "show operational status" in body["answer"]
    assert team.ca.delete(f"{A}/conversations/{body['conversation_id']}").status_code == 204
    row = world.db.execute(
        "SELECT count(*) FROM ops.ai_requests WHERE harness = 'management_copilot'"
    ).fetchone()
    assert row is not None and cast(int, row[0]) >= 1


def test_kitchen_copilot_is_available_to_kitchen_roles_only(world: World) -> None:
    kitchen_staff = login(
        world.user("KITCHEN_STAFF", region=world.region_a, kitchen=world.kitchen_a), "kitchen"
    )
    kitchen_manager = login(
        world.user("KITCHEN_MANAGER", region=world.region_a, kitchen=world.kitchen_a), "kitchen"
    )
    regional_manager = login(world.user("REGIONAL_MANAGER", region=world.region_a), "management")
    for session in (kitchen_staff, kitchen_manager):
        response = session.post(
            "/api/v1/kitchen/ai/copilot", json={"question": "How do I prepare this dish?"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["retrieval_mode"] == "reduced retrieval"
        assert response.json()["simulated"] is True
    denied = regional_manager.post("/api/v1/kitchen/ai/copilot", json={"question": "Kitchen guidance"})
    assert denied.status_code == 403
