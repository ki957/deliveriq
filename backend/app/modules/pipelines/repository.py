"""SQL for ops.pipeline* run records, as `app_api`. Parameterised queries only; callers own the transaction.

`app_api` may read run records, insert a run and its queue row, and cancel through
`ops.cancel_run()`; it cannot change a run's status or results (migrations 0005, 0007).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, Row, text

_RUN_COLUMNS = (
    "r.id, r.pipeline, r.status, r.trigger, r.is_test, r.input_ref, r.region_id, r.retry_of, "
    "r.failure_class, "
    "r.error_summary, r.cancel_requested, r.counts, r.queued_at, r.started_at, r.finished_at, "
    "r.report_md IS NOT NULL AS has_report"
)


@dataclass(frozen=True)
class RunRow:
    id: uuid.UUID
    pipeline: str
    status: str
    trigger: str
    is_test: bool
    input_ref: str | None
    region_id: uuid.UUID | None
    retry_of: uuid.UUID | None
    failure_class: str | None
    error_summary: str | None
    cancel_requested: bool
    counts: dict[str, Any]
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    has_report: bool


@dataclass(frozen=True)
class PipelineRow:
    name: str
    display_name: str
    pipeline_group: str
    is_heavy: bool


def _run(row: Row[Any]) -> RunRow:
    return RunRow(**row._mapping)


def _scope_sql(regions: frozenset[uuid.UUID] | None) -> tuple[str, dict[str, Any]]:
    """None = every run (CA); otherwise only runs in the given regions (RM own region)."""
    if regions is None:
        return "true", {}
    return "r.region_id = ANY(:regions)", {"regions": list(regions)}


def list_pipelines(conn: Connection) -> list[PipelineRow]:
    rows = conn.execute(
        text(
            "SELECT name, display_name, pipeline_group, is_heavy FROM ops.pipelines ORDER BY "
            "pipeline_group, name"
        )
    ).all()
    return [PipelineRow(*r) for r in rows]


def find_pipeline(conn: Connection, name: str) -> PipelineRow | None:
    row = conn.execute(
        text("SELECT name, display_name, pipeline_group, is_heavy FROM ops.pipelines WHERE name = :n"),
        {"n": name},
    ).first()
    return PipelineRow(*row) if row else None


def last_runs(conn: Connection, regions: frozenset[uuid.UUID] | None) -> dict[str, RunRow]:
    scope, params = _scope_sql(regions)
    rows = conn.execute(
        text(
            f"SELECT DISTINCT ON (r.pipeline) {_RUN_COLUMNS} FROM ops.pipeline_runs r "  # noqa: S608 - fixed SQL
            f"WHERE {scope} ORDER BY r.pipeline, r.queued_at DESC"
        ),
        params,
    ).all()
    return {r.pipeline: _run(r) for r in rows}


def list_runs(
    conn: Connection, regions: frozenset[uuid.UUID] | None, pipeline: str | None, limit: int
) -> list[RunRow]:
    scope, params = _scope_sql(regions)
    rows = conn.execute(
        text(
            f"SELECT {_RUN_COLUMNS} FROM ops.pipeline_runs r "  # noqa: S608 - fixed SQL, values bound
            f"WHERE {scope} AND (CAST(:p AS text) IS NULL OR r.pipeline = :p) "
            "ORDER BY r.queued_at DESC LIMIT :lim"
        ),
        {**params, "p": pipeline, "lim": limit},
    ).all()
    return [_run(r) for r in rows]


def find_run(conn: Connection, run_id: uuid.UUID) -> RunRow | None:
    row = conn.execute(
        text(f"SELECT {_RUN_COLUMNS} FROM ops.pipeline_runs r WHERE r.id = :id"),  # noqa: S608 - fixed SQL
        {"id": run_id},
    ).first()
    return _run(row) if row else None


def stages(conn: Connection, run_id: uuid.UUID) -> list[Row[Any]]:
    return list(
        conn.execute(
            text(
                "SELECT seq, stage, status, rows_in, rows_out, rows_rejected, detail, started_at, "
                "finished_at "
                "FROM ops.pipeline_stage_runs WHERE run_id = :id ORDER BY seq"
            ),
            {"id": run_id},
        ).all()
    )


def errors(conn: Connection, run_id: uuid.UUID, limit: int) -> tuple[list[Row[Any]], int]:
    rows = conn.execute(
        text(
            "SELECT stage, record_ref, reason_code, message FROM ops.ingestion_errors "
            "WHERE run_id = :id ORDER BY id LIMIT :lim"
        ),
        {"id": run_id, "lim": limit},
    ).all()
    total = conn.execute(
        text("SELECT count(*) FROM ops.ingestion_errors WHERE run_id = :id"), {"id": run_id}
    ).scalar_one()
    return list(rows), int(total)


def dq_results(conn: Connection, run_id: uuid.UUID) -> list[Row[Any]]:
    return list(
        conn.execute(
            text(
                "SELECT check_name, severity, status, failures, detail FROM ops.dq_results "
                "WHERE run_id = :id ORDER BY id"
            ),
            {"id": run_id},
        ).all()
    )


def report(conn: Connection, run_id: uuid.UUID) -> str | None:
    value: str | None = conn.execute(
        text("SELECT report_md FROM ops.pipeline_runs WHERE id = :id"), {"id": run_id}
    ).scalar_one_or_none()
    return value


def kitchen_region(conn: Connection, kitchen_code: str) -> uuid.UUID:
    region: uuid.UUID = conn.execute(
        text("SELECT region_id FROM app.kitchens WHERE code = :c"), {"c": kitchen_code}
    ).scalar_one()
    return region


def insert_run(
    conn: Connection,
    *,
    pipeline: str,
    trigger: str,
    actor_user_id: uuid.UUID | None,
    is_test: bool,
    region_id: uuid.UUID | None,
    input_ref: str | None,
    retry_of: uuid.UUID | None,
) -> uuid.UUID:
    """Queue a run and its job row in the caller's transaction. One active run per pipeline (DDR-67)."""
    run_id: uuid.UUID = conn.execute(
        text(
            "INSERT INTO ops.pipeline_runs (pipeline, trigger, actor_user_id, is_test, region_id, "
            "input_ref, retry_of) "
            "VALUES (:p, :t, :a, :test, :reg, :inp, :retry) RETURNING id"
        ),
        {
            "p": pipeline,
            "t": trigger,
            "a": actor_user_id,
            "test": is_test,
            "reg": region_id,
            "inp": input_ref,
            "retry": retry_of,
        },
    ).scalar_one()
    conn.execute(text("INSERT INTO ops.job_queue (run_id) VALUES (:r)"), {"r": run_id})
    return run_id


def cancel(conn: Connection, run_id: uuid.UUID) -> str:
    outcome: str = conn.execute(text("SELECT ops.cancel_run(:id)"), {"id": run_id}).scalar_one()
    return outcome


def write_audit(
    conn: Connection,
    *,
    action: str,
    outcome: str,
    actor_user_id: uuid.UUID | None,
    actor_role: str,
    target_id: str,
    region_id: uuid.UUID | None,
    correlation_id: str | None,
    reason: str | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO audit.events (actor_user_id, actor_role, action, target_type, target_id, region_id, "
            "outcome, reason, correlation_id, after_summary) VALUES (:actor, :role, :action, "
            "'pipeline_run', :tid, "
            ":reg, :outcome, :reason, :cid, CAST(:after AS jsonb))"
        ),
        {
            "actor": actor_user_id,
            "role": actor_role,
            "action": action,
            "tid": target_id,
            "reg": region_id,
            "outcome": outcome,
            "reason": reason,
            "cid": correlation_id,
            "after": None if after is None else json.dumps(after, default=str),
        },
    )


def backlog(conn: Connection) -> tuple[int, datetime | None, int | None, int, int]:
    """(waiting, oldest waiting time, its age in seconds, landed, rejected) from `ops.outbox_backlog()`."""
    waiting, oldest, landed, rejected, age = conn.execute(
        text(
            "SELECT b.waiting, b.oldest_waiting_at, b.landed, b.rejected, "
            "CAST(extract(epoch FROM now() - b.oldest_waiting_at) AS integer) FROM ops.outbox_backlog() b"
        )
    ).one()
    return waiting, oldest, age, landed, rejected
