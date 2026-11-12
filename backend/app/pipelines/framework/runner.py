"""Execute one claimed run as its pipeline's own DB role (DDR-63) and record the outcome (DDR-67)."""

from __future__ import annotations

import json
import logging
import uuid
from functools import lru_cache
from typing import Any

from sqlalchemy import Connection, Engine, create_engine, pool, text
from sqlalchemy.exc import DBAPIError, OperationalError

from app.core.config import get_pipeline_roles, get_settings
from app.core.db import get_engine
from app.pipelines.framework import registry
from app.pipelines.framework.context import (
    CancelledError,
    DataError,
    RunContext,
    StructuralError,
    TransientError,
)

_log = logging.getLogger("app.pipelines")
CODE_VERSION = "0.1.0"


@lru_cache(maxsize=16)
def role_engine(role: str) -> Engine:
    url = get_pipeline_roles().url_for(get_settings(), role)
    return create_engine(url, poolclass=pool.NullPool, connect_args={"connect_timeout": 5})


def _finish(
    records: Connection,
    run_id: uuid.UUID,
    status: str,
    *,
    failure_class: str | None = None,
    error: str | None = None,
    counts: dict[str, Any] | None = None,
) -> None:
    records.execute(
        text(
            "UPDATE ops.pipeline_runs SET status = :st, finished_at = now(), failure_class = :fc, "
            "error_summary = :err, counts = coalesce(CAST(:c AS jsonb), counts), code_version = :v "
            "WHERE id = :id"
        ),
        {
            "st": status,
            "fc": failure_class,
            "err": error,
            "c": json.dumps(counts, default=str) if counts is not None else None,
            "v": CODE_VERSION,
            "id": run_id,
        },
    )


def execute(run_id: uuid.UUID) -> str:
    """Run a claimed job. Returns the final status; raises TransientError to request a retry."""
    with get_engine().connect() as lookup:  # the worker's own role: read-only run metadata
        pipeline, is_test, input_ref, db_role = lookup.execute(
            text(
                "SELECT r.pipeline, r.is_test, r.input_ref, p.db_role FROM ops.pipeline_runs r "
                "JOIN ops.pipelines p ON p.name = r.pipeline WHERE r.id = :id"
            ),
            {"id": run_id},
        ).one()
    try:
        fn = registry.get(pipeline)
    except KeyError:
        # The worker role may close a run it cannot execute (status columns only, migration 0007).
        with get_engine().begin() as conn:
            conn.execute(
                text(
                    "UPDATE ops.pipeline_runs SET status = 'failed', failure_class = 'structural', "
                    "finished_at = now(), error_summary = :e WHERE id = :id"
                ),
                {"e": f"Pipeline {pipeline} has no implementation", "id": run_id},
            )
        return "failed"

    try:
        engine = role_engine(db_role)
        records = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        data = engine.connect()
    except (OperationalError, KeyError) as exc:
        raise TransientError(f"cannot connect as {db_role}: {exc.__class__.__name__}") from exc

    try:
        ctx = RunContext(run_id, pipeline, is_test, input_ref, records, data)
        ctx._seq = records.execute(  # retries continue the stage numbering
            text("SELECT coalesce(max(seq), 0) FROM ops.pipeline_stage_runs WHERE run_id = :id"),
            {"id": run_id},
        ).scalar_one()
        try:
            fn(ctx)
        except CancelledError:
            data.rollback()
            _finish(records, run_id, "cancelled", error="Cancelled by request", counts=ctx.counts)
            return "cancelled"
        except StructuralError as exc:
            data.rollback()
            _finish(records, run_id, "failed", failure_class="structural", error=str(exc), counts=ctx.counts)
            return "failed"
        except DataError as exc:
            data.rollback()
            _finish(records, run_id, "failed", failure_class="data", error=str(exc), counts=ctx.counts)
            return "failed"
        except (TransientError, OperationalError) as exc:
            data.rollback()
            raise TransientError(str(exc)) from exc
        except DBAPIError as exc:
            data.rollback()
            _log.exception("pipeline database error", extra={"run_id": str(run_id)})
            reason = f"Database error: {exc.orig.__class__.__name__}" if exc.orig else "Database error"
            _finish(records, run_id, "failed", failure_class="data", error=reason, counts=ctx.counts)
            return "failed"
        except Exception:
            data.rollback()
            _log.exception("pipeline crashed", extra={"run_id": str(run_id)})
            _finish(
                records,
                run_id,
                "failed",
                failure_class="data",
                error="Internal error (see worker logs)",
                counts=ctx.counts,
            )
            return "failed"
        status = "completed_with_quarantine" if ctx.quarantined else "succeeded"
        _finish(records, run_id, status, counts=ctx.counts)
        return status
    finally:
        data.close()
        records.close()
