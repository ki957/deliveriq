"""Job queue as the real `worker` role: backoff, final failure, stale release (DDR-67 rule 1, DDR-105).

Needs the core stack and the worker (`make up`, `make worker`). Queue transitions are checked inside
rolled-back transactions, so the running worker never sees them. Runs that are committed are
flagged as test runs and use `p3_synthetic`, which has no implementation until Task 14 (P2 is implemented in Task 12).
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from sqlalchemy import URL, Connection, create_engine, pool, text

from app.pipelines.framework import queue

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]


def _url(user: str, password_key: str) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=user,
        password=os.environ[password_key],
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        database=os.environ["POSTGRES_DB"],
    )


@pytest.fixture(scope="module")
def migrator() -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    with psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        dbname=os.environ["POSTGRES_DB"],
        user="app_migrator",
        password=os.environ["APP_MIGRATOR_PASSWORD"],
        autocommit=True,
    ) as conn:
        yield conn


@pytest.fixture()
def worker() -> Iterator[Connection]:
    engine = create_engine(_url("worker", "WORKER_PASSWORD"), poolclass=pool.NullPool)
    with engine.connect() as conn:
        yield conn
        conn.rollback()
    engine.dispose()


def claimed_run(migrator: psycopg.Connection[tuple[object, ...]], *, attempts: int) -> uuid.UUID:
    """A running test run whose job is claimed by a fake worker (the real worker skips claimed jobs)."""
    row = migrator.execute(
        "INSERT INTO ops.pipeline_runs (pipeline, trigger, is_test, status, started_at) "
        "VALUES ('p3_synthetic', 'cli', true, 'running', now()) RETURNING id"
    ).fetchone()
    assert row is not None
    run_id = row[0]
    migrator.execute(
        "INSERT INTO ops.job_queue (run_id, claimed_by, claimed_at, heartbeat_at, attempts) "
        "VALUES (%s, 'test-worker', now(), now(), %s)",
        (run_id, attempts),
    )
    return run_id  # type: ignore[return-value]


def close(migrator: psycopg.Connection[tuple[object, ...]], run_id: uuid.UUID) -> None:
    migrator.execute(
        "UPDATE ops.pipeline_runs SET status = 'failed', started_at = coalesce(started_at, now()), "
        "finished_at = now(), error_summary = 'test cleanup' "
        "WHERE id = %s AND status IN ('queued', 'running')",
        (run_id,),
    )


def test_transient_failure_is_requeued_with_backoff(
    migrator: psycopg.Connection[tuple[object, ...]], worker: Connection
) -> None:
    run_id = claimed_run(migrator, attempts=1)
    try:
        outcome = queue.retry_or_fail(worker, queue.ClaimedJob(run_id, 1, 3), "connection reset")
        assert outcome == "retry_scheduled"
        row = worker.execute(
            text(
                "SELECT r.status, q.claimed_by, q.last_error, "
                "extract(epoch FROM q.available_at - now()) FROM ops.job_queue q "
                "JOIN ops.pipeline_runs r ON r.id = q.run_id WHERE q.run_id = :r"
            ),
            {"r": run_id},
        ).one()
        assert (row[0], row[1], row[2]) == ("queued", None, "connection reset")
        assert 4 <= float(row[3]) <= 5  # first backoff is 5 s
        worker.rollback()
    finally:
        close(migrator, run_id)


def test_last_attempt_fails_the_run_as_transient(
    migrator: psycopg.Connection[tuple[object, ...]], worker: Connection
) -> None:
    run_id = claimed_run(migrator, attempts=3)
    try:
        assert queue.retry_or_fail(worker, queue.ClaimedJob(run_id, 3, 3), "connection reset") == "failed"
        status, failure_class, summary = worker.execute(
            text("SELECT status, failure_class, error_summary FROM ops.pipeline_runs WHERE id = :r"),
            {"r": run_id},
        ).one()
        assert (status, failure_class) == ("failed", "transient")
        assert summary.startswith("Failed after 3 attempts")
        worker.rollback()
    finally:
        close(migrator, run_id)


def test_backoff_schedule_matches_ddr_105() -> None:
    assert queue.BACKOFF_SECONDS == (5, 30, 120)
    assert queue.STALE_AFTER_SECONDS == 60


def test_stale_job_is_released_for_retry(
    migrator: psycopg.Connection[tuple[object, ...]], worker: Connection
) -> None:
    run_id = claimed_run(migrator, attempts=1)
    try:
        # Aged inside this uncommitted transaction, so the live worker's own sweep cannot race it.
        worker.execute(
            text("UPDATE ops.job_queue SET heartbeat_at = now() - interval '2 minutes' WHERE run_id = :r"),
            {"r": run_id},
        )
        assert "retry_scheduled" in queue.release_stale(worker)
        status = worker.execute(
            text("SELECT status FROM ops.pipeline_runs WHERE id = :r"), {"r": run_id}
        ).scalar_one()
        assert status == "queued"
        worker.rollback()
    finally:
        close(migrator, run_id)


def test_worker_fails_a_run_it_has_no_implementation_for(
    migrator: psycopg.Connection[tuple[object, ...]],
) -> None:
    row = migrator.execute(
        "INSERT INTO ops.pipeline_runs (pipeline, trigger, is_test) VALUES ('p3_synthetic', 'cli', true) RETURNING id"
    ).fetchone()
    assert row is not None
    run_id = uuid.UUID(str(row[0]))
    migrator.execute("INSERT INTO ops.job_queue (run_id) VALUES (%s)", (run_id,))
    deadline = time.monotonic() + 30
    status = failure = summary = None
    while time.monotonic() < deadline:
        status, failure, summary = migrator.execute(  # type: ignore[misc]
            "SELECT status, failure_class, error_summary FROM ops.pipeline_runs WHERE id = %s", (run_id,)
        ).fetchone()
        if status not in ("queued", "running"):
            break
        time.sleep(1)
    close(migrator, run_id)
    assert (status, failure) == ("failed", "structural")
    assert summary == "Pipeline p3_synthetic has no implementation"
