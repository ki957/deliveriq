"""The P2 dbt run over the real stack (plan Task 12; DATA_PIPELINE §5, §7, §12, §13; DDR-116).

Needs the core stack, fixtures and the worker (dbt runs inside it). Runs are heavy and one at a time, so this
module waits for each run. Every run here is ended; the schedule is left off as found.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import pytest

from app.modules.identity.tests.test_auth_integration import World
from app.modules.management.tests.test_management_integration import Team

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

P = "/api/v1/pipelines"
STAGES = ["land", "dbt staging", "dbt core", "dbt marts", "dbt tests", "publish freshness"]


def run_p2(c: httpx.Client, input_ref: str | None = None, timeout: float = 240.0) -> dict[str, Any]:
    end = time.monotonic() + timeout
    while True:  # another heavy run (or a previous P2 run) may still be active
        r = c.post(
            f"{P}/runs", json={"pipeline": "p2_elt", **({"input_ref": input_ref} if input_ref else {})}
        )
        if r.status_code == 202:
            break
        assert r.status_code == 409 and time.monotonic() < end, r.text
        time.sleep(3)
    run_id = r.json()["id"]
    while time.monotonic() < end:
        detail: dict[str, Any] = c.get(f"{P}/runs/{run_id}").json()
        if detail["run"]["status"] not in ("queued", "running"):
            return detail
        time.sleep(2)
    raise AssertionError("the P2 run did not finish (is `make worker` running?)")


def test_a_ca_run_builds_tests_and_publishes_freshness(team: Team) -> None:
    detail = run_p2(team.ca)
    run = detail["run"]
    assert (run["status"], run["trigger"], run["region_id"]) == ("succeeded", "ui", None)
    assert [s["stage"] for s in detail["stages"]] == STAGES
    assert all(s["status"] == "succeeded" for s in detail["stages"])
    critical = [d for d in detail["dq_results"] if d["severity"] == "critical"]
    assert critical and all(d["status"] == "pass" for d in critical)
    names = {d["check_name"] for d in critical}
    assert {"reconcile_orders", "zero_fixture_rows", "reconcile_inventory"} <= names
    assert {
        "reconcile_operational_orders",
        "reconcile_operational_order_payable",
        "reconcile_operational_payments_succeeded",
        "reconcile_operational_payments_failed",
        "reconcile_operational_consumption",
        "reconcile_operational_deliveries",
    } <= names  # persisted checks from DDR-117 (8)
    warnings = {d["check_name"] for d in detail["dq_results"] if d["severity"] == "warning"}
    assert warnings == {"raw_freshness", "outbox_backlog_age"}  # recorded only, never failing the run
    counts = run["counts"]
    # DDR-116 (7): every order in this POC is TEST, so real marts hold no TEST row; the exclusion is counted.
    assert counts["test_events_excluded"] > 0 and counts["dbt_tests_failed"] == 0
    status = team.ca.get(f"{P}/p2/status").json()
    assert status["freshness"]["run_id"] == run["id"]


def test_a_failed_critical_test_fails_the_run_and_leaves_the_marts_not_fresh(
    world: World, team: Team
) -> None:
    before = team.ca.get(f"{P}/p2/status").json()["freshness"]
    raw_before = {row[0] for row in world.db.execute("SELECT event_id FROM raw.events").fetchall()}
    detail = run_p2(team.ca, "fault:reconciliation")
    run = detail["run"]
    assert (run["status"], run["failure_class"], run["is_test"]) == ("failed", "data", True)
    assert "critical check" in run["error_summary"]
    failed = [
        d["check_name"] for d in detail["dq_results"] if d["status"] == "fail" and d["severity"] == "critical"
    ]
    # The dbt reconciliation and the operational one (DDR-117 (8)) both catch the offset.
    assert sorted(failed) == ["reconcile_operational_orders", "reconcile_orders"]
    assert "publish freshness" not in [s["stage"] for s in detail["stages"]]
    assert team.ca.get(f"{P}/p2/status").json()["freshness"] == before  # not marked fresh
    raw_after_failure = {row[0] for row in world.db.execute("SELECT event_id FROM raw.events").fetchall()}
    assert raw_after_failure >= raw_before

    retried = team.ca.post(f"{P}/runs/{run['id']}/retry")
    assert retried.status_code == 202, retried.text
    retry_id = retried.json()["id"]
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        retry_detail = team.ca.get(f"{P}/runs/{retry_id}").json()
        if retry_detail["run"]["status"] not in ("queued", "running"):
            break
        time.sleep(2)
    assert retry_detail["run"]["status"] == "failed"
    assert retry_detail["run"]["retry_of"] == run["id"]
    raw_after_retry = {row[0] for row in world.db.execute("SELECT event_id FROM raw.events").fetchall()}
    assert raw_after_retry >= raw_after_failure
    unique_raw = world.db.execute("SELECT count(*) = count(DISTINCT event_id) FROM raw.events").fetchone()
    assert unique_raw is not None and unique_raw[0] is True


def test_an_rm_sees_freshness_but_no_p2_runs_or_controls(team: Team) -> None:
    assert team.rm.get(f"{P}/p2/status").status_code == 200
    assert team.rm.post(f"{P}/runs", json={"pipeline": "p2_elt"}).status_code == 403
    assert team.rm.get(f"{P}/runs", params={"pipeline": "p2_elt"}).json() == []  # runs have no region
    run_id = team.ca.get(f"{P}/runs", params={"pipeline": "p2_elt"}).json()[0]["id"]
    assert team.rm.get(f"{P}/runs/{run_id}").status_code == 404
    assert (
        team.rm.put(
            f"{P}/p2/schedule", json={"enabled": True, "interval_minutes": 60, "reason": "Test"}
        ).status_code
        == 403
    )
    assert team.customer.get(f"{P}/p2/status").status_code == 403


def test_the_schedule_is_ca_only_audited_and_queues_a_due_timer_run(world: World, team: Team) -> None:
    assert team.ca.get(f"{P}/p2/status").json()["schedule"]["enabled"] is False  # off by default
    active_deadline = time.monotonic() + 300
    active_count = 0
    while time.monotonic() < active_deadline:
        active = world.db.execute(
            "SELECT count(*) FROM ops.pipeline_runs WHERE pipeline = 'p2_elt' AND status IN ('queued', 'running')"
        ).fetchone()
        assert active is not None and isinstance(active[0], int)
        active_count = active[0]
        if active_count == 0:
            break
        time.sleep(2)
    assert active_count == 0, "an earlier P2 run remained active before the schedule test"
    bad = team.ca.put(f"{P}/p2/schedule", json={"enabled": True, "interval_minutes": 7, "reason": "Test"})
    assert bad.status_code == 422
    on = team.ca.put(
        f"{P}/p2/schedule", json={"enabled": True, "interval_minutes": 15, "reason": "Test timer"}
    )
    assert on.status_code == 200, on.text
    assert on.json()["schedule"] == {**on.json()["schedule"], "enabled": True, "interval_minutes": 15,
                                     "interval_is_test_default": False}  # fmt: skip
    audited = world.db.execute(
        "SELECT count(*) FROM audit.events WHERE action = 'pipeline.schedule_changed' AND reason = 'Test timer'"
    ).fetchone()
    assert audited is not None and isinstance(audited[0], int) and audited[0] >= 1
    timer_ids_before = {
        str(row[0])
        for row in world.db.execute(
            "SELECT id FROM ops.pipeline_runs WHERE pipeline = 'p2_elt' AND trigger = 'timer'"
        ).fetchall()
    }
    timer_id: str | None = None
    try:
        # Make every recent P2 run old enough, then observe the worker's timer loop queue the schedule.
        world.db.execute(
            "UPDATE ops.pipeline_runs SET queued_at = queued_at - interval '20 minutes' "
            "WHERE pipeline = 'p2_elt' AND queued_at > now() - interval '15 minutes'"
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            timer_rows = world.db.execute(
                "SELECT id FROM ops.pipeline_runs WHERE pipeline = 'p2_elt' AND trigger = 'timer'"
            ).fetchall()
            timer_id = next((str(row[0]) for row in timer_rows if str(row[0]) not in timer_ids_before), None)
            if timer_id is not None:
                break
            time.sleep(1)
        if timer_id is None:
            schedule_state = world.db.execute(
                "SELECT enabled, interval_minutes FROM ops.pipeline_schedules WHERE pipeline = 'p2_elt'"
            ).fetchone()
            active_runs = world.db.execute(
                "SELECT status, trigger, queued_at FROM ops.pipeline_runs "
                "WHERE pipeline = 'p2_elt' AND status IN ('queued', 'running') ORDER BY queued_at"
            ).fetchall()
            latest_run = world.db.execute(
                "SELECT status, trigger, queued_at FROM ops.pipeline_runs "
                "WHERE pipeline = 'p2_elt' ORDER BY queued_at DESC LIMIT 1"
            ).fetchone()
            pytest.fail(
                f"worker timer did not queue due P2 schedule; schedule={schedule_state}, "
                f"active_runs={active_runs}, latest_run={latest_run}"
            )
        timer = team.ca.get(f"{P}/runs/{timer_id}").json()["run"]
        assert timer["trigger"] == "timer"
        assert timer["status"] in {"queued", "running", "succeeded", "failed"}
        timer_count = world.db.execute(
            "SELECT count(*) FROM ops.pipeline_runs WHERE pipeline = 'p2_elt' AND trigger = 'timer'"
        ).fetchone()
        assert timer_count is not None and timer_count[0] == len(timer_ids_before) + 1
        time.sleep(11)  # keep the schedule enabled through another worker timer tick
        timer_count = world.db.execute(
            "SELECT count(*) FROM ops.pipeline_runs WHERE pipeline = 'p2_elt' AND trigger = 'timer'"
        ).fetchone()
        assert timer_count is not None and timer_count[0] == len(timer_ids_before) + 1
    finally:
        off = team.ca.put(
            f"{P}/p2/schedule", json={"enabled": False, "interval_minutes": 60, "reason": "Test cleanup"}
        )
        assert off.status_code == 200
    if timer_id is not None:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            timer_detail = team.ca.get(f"{P}/runs/{timer_id}").json()
            if timer_detail["run"]["status"] not in ("queued", "running"):
                break
            time.sleep(2)
        assert timer_detail["run"]["status"] not in ("queued", "running")
