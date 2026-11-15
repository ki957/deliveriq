"""P3 worker, isolation, GPS and region scope (DDR-118)."""

from __future__ import annotations

import os
import time
from typing import Any, cast

import pytest

from app.modules.identity.tests.test_auth_integration import World
from app.modules.management.tests.test_management_integration import Team

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]


def _count(world: World, sql: str) -> int:
    row = world.db.execute(sql).fetchone()
    assert row is not None
    return cast(int, row[0])


def _run(team: Team) -> dict[str, Any]:
    response = team.ca.post("/api/v1/pipelines/runs", json={"pipeline": "p3_synthetic", "input_ref": "demo"})
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    for _ in range(150):
        detail = team.ca.get(f"/api/v1/pipelines/runs/{run_id}").json()
        if detail["run"]["status"] not in ("queued", "running"):
            return cast(dict[str, Any], detail)
        time.sleep(2)
    raise AssertionError("P3 did not finish")


def test_p3_run_builds_and_records_all_stages(team: Team, world: World) -> None:
    before = _count(world, "SELECT count(*) FROM raw.events")
    detail = _run(team)
    assert detail["run"]["status"] == "succeeded", detail["run"]["error_summary"]
    assert detail["run"]["counts"]["orders"] == 70
    assert all(d["status"] == "pass" for d in detail["dq_results"])
    assert [s["stage"] for s in detail["stages"]] == [
        "generate",
        "validate",
        "write synthetic",
        "dbt staging",
        "dbt core",
        "dbt marts",
        "dbt tests",
        "publish freshness",
    ]
    assert _count(world, "SELECT count(*) FROM raw.events") == before
    real = team.ca.get("/api/v1/management/reports").json()
    assert next(k["value"] for k in real["kpis"] if k["key"] == "orders_placed") == 0
    assert (
        _count(world, "SELECT count(*) FROM synthetic.events WHERE NOT is_synthetic OR NOT is_test_fixture")
        == 0
    )
    assert _count(world, "SELECT count(*) FROM synthetic.gps_tracks") == 3
    assert _count(world, "SELECT count(*) FROM synthetic.gps_points") == 183
    simulated = team.ca.get("/api/v1/management/reports", params={"dataset": "analytics_synthetic"}).json()
    assert simulated["available"] is True
    period = {
        "dataset": "analytics_synthetic",
        "date_from": simulated["generated_from"],
        "date_to": simulated["generated_to"],
    }
    built = team.ca.get("/api/v1/management/reports", params=period).json()
    assert next(k["value"] for k in built["kpis"] if k["key"] == "orders_placed") == 70


def test_p3_scope_and_cli_only_ml(team: Team, world: World) -> None:
    assert team.rm.get("/api/v1/pipelines/p3/status").status_code == 200
    statuses = team.rm.get("/api/v1/pipelines/p3/status").json()
    assert "demo" in {x["profile"] for x in statuses}
    assert all(x["region_id"] == str(world.region_a) for x in statuses)
    assert team.other_rm.get("/api/v1/pipelines/p3/status").json() == []
    tracks = team.ca.get("/api/v1/pipelines/p3/tracks").json()
    assert len(tracks) == 3
    assert len(team.ca.get(f"/api/v1/pipelines/p3/tracks/{tracks[0]['order_id']}").json()) == 61
    assert len(team.rm.get(f"/api/v1/pipelines/p3/tracks/{tracks[0]['order_id']}").json()) == 61
    assert team.other_rm.get(f"/api/v1/pipelines/p3/tracks/{tracks[0]['order_id']}").status_code == 404
    assert team.rm.post("/api/v1/pipelines/runs", json={"pipeline": "p3_synthetic"}).status_code == 403
    assert (
        team.ca.post(
            "/api/v1/pipelines/runs", json={"pipeline": "p3_synthetic", "input_ref": "ml"}
        ).status_code
        == 409
    )
