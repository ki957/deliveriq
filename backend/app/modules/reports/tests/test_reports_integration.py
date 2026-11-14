"""Management reports over the real stack (plan Task 13; MG-07, MG-08; DDR-117).

Needs the core stack and fixtures; the real marts exist once a P2 run has built them (the worker runs P2 in
`test_p2_run_integration.py`; this module builds them itself when missing). Real marts are empty in this POC
(every order is TEST), so values are checked through their definitions and scope, not amounts.
"""

from __future__ import annotations

import csv
import io
import os
import uuid

import psycopg
import pytest

from app.modules.identity.tests.test_auth_integration import World
from app.modules.management.tests.test_management_integration import Team
from app.modules.pipelines.tests.test_p2_run_integration import run_p2

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

R = "/api/v1/management/reports"


@pytest.fixture(scope="module", autouse=True)
def built_marts(team: Team) -> None:
    if not team.ca.get(R).json().get("fresh_as_of"):
        assert run_p2(team.ca)["run"]["status"] == "succeeded"


def test_every_kpi_shows_its_definition_status_and_none_is_business_truth(team: Team) -> None:
    body = team.ca.get(R).json()
    assert body["available"] is True and body["dataset_label"] == "Real"
    assert body["kpis_are_business_truth"] is False
    assert body["fresh_as_of"] is not None and body["freshness_warn_hours"] == 24
    assert len(body["kpis"]) == 13
    for k in body["kpis"]:
        assert k["definition_status"] == "Definition pending approval (DDR-44)"
        assert k["source"].startswith("ETL spec §") and k["formula"]
    chosen = {k["key"] for k in body["kpis"] if k["denominator_note"]}
    assert chosen == {"average_order_value", "rejection_rate", "delivery_completion_rate"}
    # Real marts exclude TEST rows, so counts are 0 and ratios have no value (never invented).
    values = {k["key"]: k["value"] for k in body["kpis"]}
    assert values["orders_placed"] == 0 and values["rejection_rate"] is None
    assert {a["area"].split(" ")[0] for a in body["not_available"]} == {"Customers", "Staff", "Promotions"}
    assert (body["date_to"] > body["date_from"]) and body["previous_to"] < body["date_from"]
    assert len(body["daily"]) == 7


def test_scope_rm_sees_own_kitchens_ca_all_others_denied(world: World, team: Team) -> None:
    ca = {k["id"] for k in team.ca.get(R).json()["kitchens"]}
    rm = {k["id"] for k in team.rm.get(R).json()["kitchens"]}
    other = {k["id"] for k in team.other_rm.get(R).json()["kitchens"]}
    assert str(world.kitchen_a) in rm and str(world.kitchen_b) not in rm
    assert str(world.kitchen_b) in other and str(world.kitchen_a) not in other
    assert {str(world.kitchen_a), str(world.kitchen_b)} <= ca
    assert team.rm.get(R, params={"kitchen_id": str(world.kitchen_b)}).status_code == 404
    assert team.rm.get(f"{R}.csv", params={"kitchen_id": str(world.kitchen_b)}).status_code == 404
    assert team.rm.get(R, params={"kitchen_id": str(uuid.uuid4())}).status_code == 404
    for denied in (team.km, team.ks, team.customer):
        assert denied.get(R).status_code == 403


def test_ranges_are_bounded_and_the_synthetic_dataset_is_labelled_not_built(team: Team) -> None:
    long = team.ca.get(R, params={"date_from": "2026-01-01", "date_to": "2026-03-01"})
    assert long.status_code == 422 and "31 days" in long.text
    assert team.ca.get(R, params={"dataset": "staging"}).status_code == 422  # whitelist only
    synthetic = team.ca.get(R, params={"dataset": "analytics_synthetic"}).json()
    assert (synthetic["available"], synthetic["unavailable_reason"]) == (False, "Not built yet (Task 14)")
    assert synthetic["kpis"] == [] and synthetic["dataset_label"] == "Simulated"
    assert team.ca.get(f"{R}.csv", params={"dataset": "analytics_synthetic"}).status_code == 422


def test_csv_export_is_scoped_labelled_and_audited(world: World, team: Team) -> None:
    r = team.rm.get(f"{R}.csv", params={"date_from": "2026-11-01", "date_to": "2026-11-03"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == ["# dataset", "Real", "definition status", "Definition pending approval (DDR-44)"]
    assert rows[1][0] == "date" and [x[0] for x in rows[2:]] == ["2026-11-01", "2026-11-02", "2026-11-03"]
    audited = world.db.execute(
        "SELECT count(*) FROM audit.events WHERE action = 'management.export.report' "
        "AND actor_role = 'REGIONAL_MANAGER' AND occurred_at > now() - interval '1 minute'"
    ).fetchone()
    assert audited is not None and isinstance(audited[0], int) and audited[0] >= 1


def test_the_api_role_reads_marts_and_dimensions_only() -> None:
    with psycopg.connect(
        host="127.0.0.1", port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")), dbname=os.environ["POSTGRES_DB"],
        user="app_api", password=os.environ["APP_API_PASSWORD"], autocommit=True,
    ) as api:  # fmt: skip
        api.execute("SELECT count(*) FROM analytics.mart_daily_sales").fetchone()
        api.execute("SELECT count(*) FROM analytics.dim_kitchen").fetchone()
        for denied in ("analytics.fact_orders", "staging.stg_events", "raw.events"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                api.execute(f"SELECT 1 FROM {denied} LIMIT 1")  # noqa: S608 - fixed test table names
