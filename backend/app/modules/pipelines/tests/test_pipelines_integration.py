"""P1 end to end through the API and the worker, plus the Data & Pipelines RBAC matrix (plan Task 5).

Needs the core stack and the worker (`make up`, `make worker`, `make test-integration`). Runs the real
SOP import into the local database: it is idempotent, so repeated test runs add nothing.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import httpx
import psycopg
import pytest

from app.modules.identity.tests.test_auth_integration import World, client, login
from app.pipelines.p1_sop.pipeline import SOP_RELATIVE_PATH
from app.pipelines.p1_sop.report import LIMITATION

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

TERMINAL = {"succeeded", "completed_with_quarantine", "failed", "cancelled"}
STAGES = [
    "register",
    "parse",
    "validate structure",
    "transform",
    "quality checks",
    "stage",
    "load DRAFT",
    "reconcile",
    "report",
]


def scalar(world: World, sql: str, *params: object) -> Any:
    row = world.db.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


def pairs(world: World, sql: str, *params: object) -> dict[Any, Any]:
    return {row[0]: row[1] for row in world.db.execute(sql, params).fetchall()}


def wait_for(c: httpx.Client, run_id: str, timeout: float = 300) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        detail: dict[str, Any] = c.get(f"/api/v1/pipelines/runs/{run_id}").json()
        if detail["run"]["status"] in TERMINAL:
            return detail
        time.sleep(1)
    pytest.fail(f"run {run_id} did not finish in {timeout}s")


@pytest.fixture(scope="module")
def ca(world: World) -> httpx.Client:
    recent = scalar(
        world, "SELECT count(*) FROM ops.workers WHERE heartbeat_at > now() - interval '30 seconds'"
    )
    assert recent, "no worker heartbeat in the last 30 s: start it with `make worker`"
    return login(world.user("CENTRAL_ADMIN"), "management")


@pytest.fixture(scope="module")
def first_run(ca: httpx.Client) -> dict[str, Any]:
    response = ca.post("/api/v1/pipelines/runs", json={"pipeline": "p1_sop"})
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "queued"
    return wait_for(ca, response.json()["id"])


def queue_parked_run(world: World) -> str:
    """A queued P1 run the worker will not claim yet (available in one hour)."""
    run_id = scalar(
        world,
        "INSERT INTO ops.pipeline_runs (pipeline, trigger, region_id, input_ref) "
        "SELECT 'p1_sop', 'cli', region_id, 'sop' FROM app.kitchens WHERE code = 'KIT-CHN-001' RETURNING id",
    )
    world.db.execute(
        "INSERT INTO ops.job_queue (run_id, available_at) VALUES (%s, now() + interval '1 hour')", (run_id,)
    )
    return str(run_id)


# ---------------------------------------------------------------- RBAC (DDR-64, DDR-105)
def test_unauthenticated_and_non_management_roles_are_refused(world: World) -> None:
    with client() as anon:
        assert anon.get("/api/v1/pipelines").status_code == 401
    for role, portal, extra in [
        ("KITCHEN_MANAGER", "kitchen", {"region": world.region_a, "kitchen": world.kitchen_a}),
        ("KITCHEN_STAFF", "kitchen", {"region": world.region_a, "kitchen": world.kitchen_a}),
        ("DELIVERY_AGENT", "delivery", {"region": world.region_a}),
        ("CUSTOMER", "customer", {}),
    ]:
        c = login(world.user(role, **extra), portal)
        assert c.get("/api/v1/pipelines").status_code == 403, role
        assert c.get("/api/v1/pipelines/runs").status_code == 403, role
        assert c.post("/api/v1/pipelines/runs", json={"pipeline": "p1_sop"}).status_code == 403, role
        c.close()


def test_regional_manager_views_own_region_only_and_cannot_act(
    world: World,
    first_run: dict[str, Any],
) -> None:
    run_id = first_run["run"]["id"]
    rm = login(world.user("REGIONAL_MANAGER", region=world.region_a), "management")
    other = login(world.user("REGIONAL_MANAGER", region=world.region_b), "management")
    assert rm.get(f"/api/v1/pipelines/runs/{run_id}").status_code == 200
    assert run_id in [r["id"] for r in rm.get("/api/v1/pipelines/runs").json()]
    # Another region's RM cannot see the run or learn that it exists.
    assert other.get(f"/api/v1/pipelines/runs/{run_id}").status_code == 404
    assert other.get(f"/api/v1/pipelines/runs/{run_id}/report").status_code == 404
    assert other.get("/api/v1/pipelines/runs").json() == []
    # Direct calls to actions are refused (UI hiding is not the boundary).
    assert rm.post("/api/v1/pipelines/runs", json={"pipeline": "p1_sop"}).status_code == 403
    assert rm.post(f"/api/v1/pipelines/runs/{run_id}/cancel").status_code == 403
    assert rm.post(f"/api/v1/pipelines/runs/{run_id}/retry").status_code == 403
    rm.close()
    other.close()


def test_csrf_header_is_required_for_actions(world: World, ca: httpx.Client) -> None:
    response = ca.post(
        "/api/v1/pipelines/runs", json={"pipeline": "p1_sop"}, headers={"X-DeliverIQ-CSRF": ""}
    )
    assert response.status_code == 403


# ---------------------------------------------------------------- P1 import (plan Task 5 import criteria)
def test_p1_imports_every_card_as_draft_with_lineage(world: World, first_run: dict[str, Any]) -> None:
    run = first_run["run"]
    assert run["status"] == "succeeded", run["error_summary"]
    assert [s["stage"] for s in first_run["stages"]] == STAGES
    assert {s["status"] for s in first_run["stages"]} == {"succeeded"}
    assert first_run["errors_total"] == 0
    assert first_run["dq_results"] and all(d["status"] == "pass" for d in first_run["dq_results"])
    assert run["counts"]["cards"] == 104 and run["counts"]["ingredient_lines"] == 616
    assert run["region_id"] == str(world.region_a) and run["is_test"] is False

    sha = scalar(world, "SELECT observed_sha256 FROM ops.source_registry WHERE run_id = %s", run["id"])
    statuses = pairs(
        world,
        "SELECT status, count(*) FROM app.recipe_versions WHERE source_sha256 = %s GROUP BY status",
        sha,
    )
    assert statuses == {"DRAFT": 102, "QUARANTINED_DUPLICATE_CANDIDATE": 2}
    quarantined = world.db.execute(
        "SELECT source_card_id FROM app.recipe_versions WHERE source_sha256 = %s "
        "AND status = 'QUARANTINED_DUPLICATE_CANDIDATE' ORDER BY 1",
        (sha,),
    ).fetchall()
    assert [q[0] for q in quarantined] == ["MENU008", "MENU057"]
    reasons = pairs(
        world,
        "SELECT source_card_id, quarantine_reason FROM app.recipe_versions WHERE source_sha256 = %s "
        "AND status = 'QUARANTINED_DUPLICATE_CANDIDATE'",
        sha,
    )
    assert reasons["MENU008"].startswith("DUPLICATE_BOM:") and reasons["MENU008"].endswith("MENU057")
    assert reasons["MENU057"].endswith("MENU008")
    assert scalar(world, "SELECT count(*) FROM app.recipes WHERE source_menu_id ~ '^MENU'") == 104
    assert scalar(world, "SELECT count(*) FROM app.recipe_ingredients WHERE source_sha256 = %s", sha) == 616
    assert scalar(world, "SELECT count(*) FROM app.ingredients WHERE origin = 'SOP_DERIVED'") == 115

    # Lineage on every row: file, SHA-256, line range, card ID (KITCHEN_SOURCE_VALIDATION §9).
    assert (
        scalar(
            world,
            "SELECT count(*) FROM app.recipe_versions WHERE source_sha256 = %s AND (source_path IS NULL "
            "OR source_card_id IS NULL OR source_line_start IS NULL OR source_line_end IS NULL "
            "OR import_run_id IS NULL)",
            sha,
        )
        == 0
    )
    assert (
        scalar(
            world,
            "SELECT count(*) FROM app.recipe_ingredients WHERE source_sha256 = %s "
            "AND (source_line IS NULL OR original_text IS NULL)",
            sha,
        )
        == 0
    )
    assert scalar(
        world,
        "SELECT bool_and(source_path LIKE %s) FROM app.recipe_versions WHERE source_sha256 = %s",
        f"%{SOP_RELATIVE_PATH}",
        sha,
    )
    # SOP import never marks fixtures and never activates (DDR-50).
    assert (
        scalar(
            world,
            "SELECT count(*) FROM app.recipe_versions WHERE source_sha256 = %s AND is_test_fixture",
            sha,
        )
        == 0
    )
    assert (
        scalar(
            world,
            "SELECT count(*) FROM app.recipe_versions WHERE source_sha256 = %s AND status = 'ACTIVE'",
            sha,
        )
        == 0
    )


def test_review_queue_holds_missing_components_and_ambiguities(
    world: World, first_run: dict[str, Any]
) -> None:
    by_reason = pairs(
        world,
        "SELECT r.reason_code, count(DISTINCT r.subject) FROM app.recipe_review_items r "
        "JOIN app.recipe_versions v ON v.id = r.recipe_version_id WHERE v.source_card_id IS NOT NULL "
        "GROUP BY r.reason_code",
    )
    assert by_reason["MISSING_BATCH_RECIPE"] == 8
    assert by_reason["COMPOSITE_INGREDIENT"] > 0 and by_reason["AMBIGUOUS_INGREDIENT"] > 0
    assert scalar(world, "SELECT count(*) FROM app.recipe_review_items WHERE status <> 'OPEN'") == 0


def test_open_review_items_block_submission(world: World, first_run: dict[str, Any]) -> None:
    version = scalar(
        world,
        "SELECT v.id FROM app.recipe_versions v JOIN app.recipe_review_items r ON r.recipe_version_id = v.id "
        "WHERE v.status = 'DRAFT' AND r.status = 'OPEN' LIMIT 1",
    )
    km_mobile = world.user("KITCHEN_MANAGER", region=world.region_a, kitchen=world.kitchen_a)
    km = scalar(world, "SELECT id FROM app.users WHERE mobile_e164 = %s", km_mobile)
    with pytest.raises(psycopg.errors.CheckViolation, match="open review items"), world.db.transaction():
        world.db.execute("SELECT set_config('app.actor_user_id', %s, true)", (str(km),))
        world.db.execute("SELECT set_config('app.actor_role', 'KITCHEN_MANAGER', true)")
        world.db.execute("SELECT set_config('app.reason', 'integration test', true)")
        world.db.execute(
            "UPDATE app.recipe_versions SET status = 'PENDING_VALIDATION' WHERE id = %s", (version,)
        )


def test_report_download_states_the_limitation(ca: httpx.Client, first_run: dict[str, Any]) -> None:
    response = ca.get(f"/api/v1/pipelines/runs/{first_run['run']['id']}/report")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert LIMITATION in response.text
    assert "104" in response.text and "616" in response.text


def test_rerun_adds_zero_rows_and_yields_an_identical_report(
    world: World,
    ca: httpx.Client,
    first_run: dict[str, Any],
) -> None:
    before = scalar(world, "SELECT count(*) FROM app.recipe_ingredients")
    response = ca.post("/api/v1/pipelines/runs", json={"pipeline": "p1_sop"})
    assert response.status_code == 202, response.text
    second = wait_for(ca, response.json()["id"])
    assert second["run"]["status"] == "succeeded"
    assert set(second["run"]["counts"]["added"].values()) == {0}
    assert scalar(world, "SELECT count(*) FROM app.recipe_ingredients") == before
    first_report = ca.get(f"/api/v1/pipelines/runs/{first_run['run']['id']}/report").text
    assert ca.get(f"/api/v1/pipelines/runs/{second['run']['id']}/report").text == first_report


# ---------------------------------------------------------------- framework: one active run, cancel, retry, audit
def test_one_active_run_cancel_queued_and_retry(
    world: World, ca: httpx.Client, first_run: dict[str, Any]
) -> None:
    parked = queue_parked_run(world)
    try:
        conflict = ca.post("/api/v1/pipelines/runs", json={"pipeline": "p1_sop"})
        assert conflict.status_code == 409 and "already" in conflict.json()["message"]

        cancelled = ca.post(f"/api/v1/pipelines/runs/{parked}/cancel")
        assert cancelled.status_code == 200 and cancelled.json() == {"outcome": "cancelled"}
    finally:
        world.db.execute("SELECT ops.cancel_run(%s)", (parked,))
    detail = ca.get(f"/api/v1/pipelines/runs/{parked}").json()
    assert detail["run"]["status"] == "cancelled" and detail["stages"] == []
    assert ca.post(f"/api/v1/pipelines/runs/{parked}/cancel").status_code == 409  # no longer active
    assert ca.post(f"/api/v1/pipelines/runs/{first_run['run']['id']}/retry").status_code == 409  # succeeded

    retried = ca.post(f"/api/v1/pipelines/runs/{parked}/retry")
    assert retried.status_code == 202, retried.text
    assert retried.json()["retry_of"] == parked
    assert wait_for(ca, retried.json()["id"])["run"]["status"] == "succeeded"

    actions = world.db.execute(
        "SELECT action, actor_role FROM audit.events WHERE target_type = 'pipeline_run' AND target_id = ANY(%s)",
        ([parked, retried.json()["id"]],),
    ).fetchall()
    assert ("pipeline.cancel", "CENTRAL_ADMIN") in actions
    assert ("pipeline.retry", "CENTRAL_ADMIN") in actions


def test_unknown_and_unimplemented_pipelines_are_refused(ca: httpx.Client) -> None:
    assert ca.post("/api/v1/pipelines/runs", json={"pipeline": "no_such"}).status_code == 404
    assert ca.post("/api/v1/pipelines/runs", json={"pipeline": "p2_elt"}).status_code == 409
    assert ca.post("/api/v1/pipelines/runs", json={"pipeline": "p1_sop", "input_ref": "x"}).status_code == 422
    listed = {p["name"]: p["implemented"] for p in ca.get("/api/v1/pipelines").json()}
    assert listed["p1_sop"] is True and listed["p2_elt"] is False
    assert ca.get(f"/api/v1/pipelines/runs/{uuid.uuid4()}").status_code == 404


# ---------------------------------------------------------------- DB roles (DDR-63, DDR-105)
def _connect(role: str, password_key: str) -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        dbname=os.environ["POSTGRES_DB"],
        user=role,
        password=os.environ[password_key],
        autocommit=True,
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1 FROM app.users LIMIT 1",
        "SELECT 1 FROM app.recipes LIMIT 1",
        "UPDATE ops.pipeline_runs SET counts = '{}' WHERE false",
        "DELETE FROM ops.job_queue WHERE false",
    ],
)
def test_worker_role_can_only_claim_and_heartbeat(sql: str) -> None:
    with _connect("worker", "WORKER_PASSWORD") as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(sql)


def test_api_role_cannot_change_run_results() -> None:
    with _connect("app_api", "APP_API_PASSWORD") as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("UPDATE ops.pipeline_runs SET status = 'succeeded' WHERE false")


def test_p1_role_cannot_activate_or_mark_fixtures() -> None:
    with _connect("p1_sop", "P1_SOP_PASSWORD") as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("UPDATE app.recipe_versions SET is_test_fixture = true WHERE false")
