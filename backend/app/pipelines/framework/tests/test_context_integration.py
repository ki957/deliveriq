"""Stage-boundary cancel and P1 restaging as the real DB roles (DDR-67 rule 6, DDR-105).

Needs the core stack (`make up`). Uses test-flagged runs with no queue row, so the worker never
touches them; each run is closed afterwards.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import URL, Connection, create_engine, pool, text

from app.pipelines.framework.context import CancelledError, RunContext
from app.pipelines.p1_sop import pipeline as p1
from app.pipelines.p1_sop.checks import run_checks
from app.pipelines.p1_sop.parser import parse

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]

SOP = Path(__file__).resolve().parents[5] / "data" / "source" / p1.SOP_RELATIVE_PATH


def _connect(user: str, password_key: str) -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        dbname=os.environ["POSTGRES_DB"],
        user=user,
        password=os.environ[password_key],
        autocommit=True,
    )


@pytest.fixture()
def run_id() -> Iterator[uuid.UUID]:
    with _connect("app_migrator", "APP_MIGRATOR_PASSWORD") as db:
        row = db.execute(
            "INSERT INTO ops.pipeline_runs (pipeline, trigger, is_test, status, started_at) "
            "VALUES ('p2_elt', 'cli', true, 'running', now()) RETURNING id"
        ).fetchone()
        assert row is not None
        value = uuid.UUID(str(row[0]))
        try:
            yield value
        finally:
            db.execute("DELETE FROM staging.sop_ingredient_lines WHERE run_id = %s", (value,))
            db.execute("DELETE FROM staging.sop_cards WHERE run_id = %s", (value,))
            db.execute(
                "UPDATE ops.pipeline_runs SET status = 'cancelled', finished_at = now(), "
                "error_summary = 'test cleanup' WHERE id = %s AND status = 'running'",
                (value,),
            )


@pytest.fixture()
def p1_conns() -> Iterator[tuple[Connection, Connection]]:
    url = URL.create(
        "postgresql+psycopg",
        username="p1_sop",
        password=os.environ["P1_SOP_PASSWORD"],
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        database=os.environ["POSTGRES_DB"],
    )
    engine = create_engine(url, poolclass=pool.NullPool)
    records = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    data = engine.connect()
    try:
        yield records, data
    finally:
        data.close()
        records.close()
        engine.dispose()


def test_running_run_stops_at_the_next_stage_boundary(
    run_id: uuid.UUID, p1_conns: tuple[Connection, Connection]
) -> None:
    records, data = p1_conns
    ctx = RunContext(run_id, "p2_elt", True, None, records, data)
    with ctx.stage("first"):
        pass
    with _connect("app_api", "APP_API_PASSWORD") as api:
        row = api.execute("SELECT ops.cancel_run(%s)", (run_id,)).fetchone()
    assert row == ("cancel_requested",)
    with pytest.raises(CancelledError), ctx.stage("second"):
        pytest.fail("a stage must not start after a cancel request")
    stages = records.execute(
        text("SELECT stage, status FROM ops.pipeline_stage_runs WHERE run_id = :r ORDER BY seq"),
        {"r": run_id},
    ).all()
    assert [tuple(s) for s in stages] == [("first", "succeeded")]


def test_restaging_a_retried_run_replaces_its_rows(
    run_id: uuid.UUID, p1_conns: tuple[Connection, Connection]
) -> None:
    records, data = p1_conns
    parsed = parse(SOP.read_text(encoding="utf-8"))
    outcome = run_checks(parsed, is_sop=True)
    ctx = RunContext(run_id, "p1_sop", True, "sop", records, data)
    p1._stage(ctx, parsed, outcome)
    p1._stage(ctx, parsed, outcome)  # second attempt of the same run
    cards = records.execute(text("SELECT count(*) FROM staging.sop_cards WHERE run_id = :r"), {"r": run_id})
    lines = records.execute(
        text("SELECT count(*) FROM staging.sop_ingredient_lines WHERE run_id = :r"), {"r": run_id}
    )
    assert (cards.scalar_one(), lines.scalar_one()) == (104, 616)
