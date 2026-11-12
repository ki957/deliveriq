"""PostgreSQL job queue, used by the worker's own `worker` role (DDR-63, DDR-105).

Claims use `FOR UPDATE SKIP LOCKED`; one heavy job at a time (DDR-67 rule 5); stale jobs (no
heartbeat for 60 s) and transient failures are retried after 5 s, 30 s, 2 min, then fail.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Connection, text

BACKOFF_SECONDS = (5, 30, 120)
STALE_AFTER_SECONDS = 60


@dataclass(frozen=True)
class ClaimedJob:
    run_id: uuid.UUID
    attempts: int
    max_attempts: int


def register_worker(conn: Connection, worker_id: str) -> None:
    conn.execute(
        text(
            "INSERT INTO ops.workers (worker_id) VALUES (:w) "
            "ON CONFLICT (worker_id) DO UPDATE SET started_at = now(), heartbeat_at = now(), "
            "current_run_id = NULL"
        ),
        {"w": worker_id},
    )


def heartbeat(conn: Connection, worker_id: str, run_id: uuid.UUID | None) -> None:
    conn.execute(
        text("UPDATE ops.workers SET heartbeat_at = now(), current_run_id = :r WHERE worker_id = :w"),
        {"w": worker_id, "r": run_id},
    )
    if run_id is not None:
        conn.execute(text("UPDATE ops.job_queue SET heartbeat_at = now() WHERE run_id = :r"), {"r": run_id})


def recent_heartbeat(conn: Connection, host: str, within_seconds: int) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM ops.workers WHERE worker_id LIKE :h "
                "AND heartbeat_at > now() - make_interval(secs => :s))"
            ),
            {"h": f"{host}-%", "s": within_seconds},
        ).scalar_one()
    )


def claim(conn: Connection, worker_id: str) -> ClaimedJob | None:
    row = conn.execute(
        text(
            """
            WITH next AS (
                SELECT q.id FROM ops.job_queue q
                  JOIN ops.pipeline_runs r ON r.id = q.run_id
                  JOIN ops.pipelines p ON p.name = r.pipeline
                 WHERE q.claimed_at IS NULL AND q.available_at <= now() AND r.status = 'queued'
                   AND (NOT p.is_heavy OR NOT EXISTS (
                        SELECT 1 FROM ops.pipeline_runs r2 JOIN ops.pipelines p2 ON p2.name = r2.pipeline
                         WHERE r2.status = 'running' AND p2.is_heavy))
                 ORDER BY q.available_at, q.id
                 FOR UPDATE OF q SKIP LOCKED
                 LIMIT 1)
            UPDATE ops.job_queue q
               SET claimed_by = :w, claimed_at = now(), heartbeat_at = now(), attempts = q.attempts + 1
              FROM next WHERE q.id = next.id
            RETURNING q.run_id, q.attempts, q.max_attempts
            """
        ),
        {"w": worker_id},
    ).first()
    if row is None:
        return None
    conn.execute(
        text(
            "UPDATE ops.pipeline_runs SET status = 'running', started_at = coalesce(started_at, "
            "now()) WHERE id = :r"
        ),
        {"r": row.run_id},
    )
    return ClaimedJob(row.run_id, row.attempts, row.max_attempts)


def retry_or_fail(conn: Connection, job: ClaimedJob, error: str) -> str:
    """Transient failure: requeue with backoff, or fail after the last attempt (DDR-67 rule 1)."""
    if job.attempts < job.max_attempts:
        delay = BACKOFF_SECONDS[min(job.attempts - 1, len(BACKOFF_SECONDS) - 1)]
        conn.execute(
            text(
                "UPDATE ops.job_queue SET claimed_by = NULL, claimed_at = NULL, heartbeat_at = NULL, "
                "available_at = now() + make_interval(secs => :d), last_error = :e WHERE run_id = :r"
            ),
            {"d": delay, "e": error[:1000], "r": job.run_id},
        )
        conn.execute(text("UPDATE ops.pipeline_runs SET status = 'queued' WHERE id = :r"), {"r": job.run_id})
        return "retry_scheduled"
    conn.execute(
        text("UPDATE ops.job_queue SET last_error = :e WHERE run_id = :r"),
        {"e": error[:1000], "r": job.run_id},
    )
    conn.execute(
        text(
            "UPDATE ops.pipeline_runs SET status = 'failed', failure_class = 'transient', "
            "finished_at = now(), "
            "error_summary = :e WHERE id = :r"
        ),
        {"e": f"Failed after {job.attempts} attempts: {error}"[:2000], "r": job.run_id},
    )
    return "failed"


def release_stale(conn: Connection) -> list[str]:
    """Jobs whose worker stopped heartbeating are treated as a transient failure (DOCKER §12)."""
    stale = conn.execute(
        text(
            "SELECT q.run_id, q.attempts, q.max_attempts FROM ops.job_queue q "
            "JOIN ops.pipeline_runs r ON r.id = q.run_id "
            "WHERE r.status = 'running' AND q.claimed_at IS NOT NULL "
            "AND q.heartbeat_at < now() - make_interval(secs => :s) FOR UPDATE OF q SKIP LOCKED"
        ),
        {"s": STALE_AFTER_SECONDS},
    ).all()
    return [retry_or_fail(conn, ClaimedJob(*row), "worker heartbeat lost") for row in stale]
