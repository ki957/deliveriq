"""P2 run: land → dbt staging → core → marts → dbt tests → publish freshness (DATA_PIPELINE §5, §7, §9).

Runs as `p2_elt` on the worker (heavy job, one at a time; DDR-67 rule 5). dbt runs as a subprocess with
`threads` 2 (DDR-63, ADR-DATA-002); its connection comes from the environment, so no secret is written to
disk or to a log. Every dbt test result is stored in `ops.dq_results`; a failed critical test fails the run
(data failure, never retried) and freshness is not published, so the marts are not marked fresh
(DDR-67 rule 4, DDR-116 (8), (12)). Warnings (raw freshness, outbox backlog age) are recorded only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.core.config import get_pipeline_roles, get_settings
from app.pipelines.framework.context import DataError, RunContext, StructuralError
from app.pipelines.framework.registry import register
from app.pipelines.p2_elt.landing import BATCH_MAX, land_batch

DBT_TIMEOUT_SECONDS = 600
# DDR-116 (12): labelled test defaults for the warning checks (record only).
FRESHNESS_WARN_HOURS = 24
BACKLOG_WARN_SECONDS = 300
DATASET = "analytics"


def _dbt_env() -> dict[str, str]:
    settings, roles = get_settings(), get_pipeline_roles()
    secret = roles.p2_elt
    if secret is None:
        raise StructuralError("no credentials configured for p2_elt")
    work = Path(tempfile.gettempdir()) / "dbt"
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(work),
        "DB_HOST": settings.db_host,
        "DB_PORT": str(settings.db_port),
        "POSTGRES_DB": settings.db_name,
        "DBT_P2_ELT_PASSWORD": secret.get_secret_value(),
        "DBT_PROFILES_DIR": roles.dbt_project_dir,
        "DBT_TARGET_PATH": str(work / "target"),
        "DBT_LOG_PATH": str(work / "logs"),
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        "DBT_USE_COLORS": "false",
    }


def run_dbt(command: str, select: str | None, dbt_vars: dict[str, Any]) -> list[dict[str, Any]]:
    """Run one dbt command; returns `run_results.json` results. Only node names leave this function."""
    env = _dbt_env()
    args = [sys.executable, "-m", "dbt.cli.main", command, "--vars", json.dumps(dbt_vars)]
    if select:
        args += ["--select", select]
    try:
        done = subprocess.run(  # noqa: S603 - fixed arguments, no shell
            args,
            cwd=get_pipeline_roles().dbt_project_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=DBT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise DataError(f"dbt {command} took longer than {DBT_TIMEOUT_SECONDS} s") from None
    results_file = Path(env["DBT_TARGET_PATH"]) / "run_results.json"
    if not results_file.exists():
        # dbt could not start (project or connection error): never echo its output (it may contain SQL).
        raise DataError(f"dbt {command} did not run (exit {done.returncode}); see the worker logs")
    results: list[dict[str, Any]] = json.loads(results_file.read_text())["results"]
    if command == "run":
        failed = [r["unique_id"].split(".")[-1] for r in results if r["status"] not in ("success", "skipped")]
        if failed or done.returncode != 0:
            raise DataError(f"dbt models failed: {', '.join(failed) or 'see the worker logs'}")
    return results


def _test_name(result: dict[str, Any]) -> str:
    return str(result["unique_id"]).split(".", 2)[-1]


def _count(ctx: RunContext, sql: str) -> int:
    value: int = ctx.data.execute(text(sql)).scalar_one()
    ctx.data.commit()
    return value


@register("p2_elt")
def run(ctx: RunContext) -> None:
    fault = ctx.input_ref == "fault:reconciliation"
    dbt_vars = {"dataset": DATASET, "reconciliation_offset": 1 if fault else 0}

    with ctx.stage("land") as counts:
        accepted = rejected = 0
        while True:
            with ctx.data.begin():
                batch = land_batch(ctx.data)
            accepted, rejected = accepted + batch.accepted, rejected + batch.rejected
            if batch.accepted + batch.rejected + batch.duplicates < BATCH_MAX:
                break
        counts.rows_out, counts.rows_rejected = accepted, rejected

    for stage, select in (("dbt staging", "staging"), ("dbt core", "core"), ("dbt marts", "marts")):
        with ctx.stage(stage) as counts:
            results = run_dbt("run", select, dbt_vars)
            counts.rows_out = len(results)
            counts.detail = {"models": sorted(r["unique_id"].split(".")[-1] for r in results)}

    real = _count(ctx, "SELECT count(*) FROM staging.stg_events")
    excluded = _count(
        ctx, "SELECT count(*) FROM raw.events WHERE parse_status = 'accepted' AND is_test_fixture"
    )
    ctx.counts.update(
        {
            "events_landed": accepted,
            "events_rejected": rejected,
            "real_events": real,
            "test_events_excluded": excluded,
            "fact_orders": _count(ctx, "SELECT count(*) FROM analytics.fact_orders"),
        }
    )

    with ctx.stage("dbt tests") as counts:
        results = run_dbt("test", None, dbt_vars)
        failed = 0
        for r in results:
            passed = r["status"] == "pass"
            failed += 0 if passed else 1
            ctx.dq(
                _test_name(r),
                "critical",
                passed,
                int(r.get("failures") or 0),
                {"status": r["status"]},
            )
        _warnings(ctx)
        counts.rows_in, counts.rows_rejected = len(results), failed
        ctx.counts.update({"dbt_tests": len(results), "dbt_tests_failed": failed})
        if failed:
            raise DataError(f"{failed} critical dbt test(s) failed; the marts are not marked fresh")

    with ctx.stage("publish freshness"), ctx.data.begin():
        ctx.data.execute(
            text(
                "INSERT INTO ops.dataset_freshness (dataset, fresh_as_of, run_id) VALUES (:d, now(), :r) "
                "ON CONFLICT (dataset) DO UPDATE SET fresh_as_of = now(), run_id = :r, updated_at = now()"
            ),
            {"d": DATASET, "r": ctx.run_id},
        )


def _warnings(ctx: RunContext) -> None:
    """Record-only checks (DATA_PIPELINE §7): raw freshness and outbox backlog age."""
    age_hours = ctx.data.execute(
        text(
            "SELECT extract(epoch FROM now() - max(landed_at)) / 3600 FROM raw.events "
            "WHERE parse_status = 'accepted' AND NOT is_test_fixture"
        )
    ).scalar_one()
    backlog_age = ctx.data.execute(
        text("SELECT extract(epoch FROM now() - oldest_waiting_at) FROM ops.outbox_backlog()")
    ).scalar_one()
    ctx.data.commit()
    fresh = age_hours is not None and float(age_hours) <= FRESHNESS_WARN_HOURS
    ctx.dq(
        "raw_freshness",
        "warning",
        fresh,
        0 if fresh else 1,
        {
            "newest_real_event_age_hours": None if age_hours is None else round(float(age_hours), 1),
            "warn_after_hours": FRESHNESS_WARN_HOURS,
            "is_test_default": True,
        },
    )
    calm = backlog_age is None or float(backlog_age) <= BACKLOG_WARN_SECONDS
    ctx.dq(
        "outbox_backlog_age",
        "warning",
        calm,
        0 if calm else 1,
        {
            "oldest_waiting_seconds": None if backlog_age is None else int(backlog_age),
            "warn_after_seconds": BACKLOG_WARN_SECONDS,
            "is_test_default": True,
        },
    )
