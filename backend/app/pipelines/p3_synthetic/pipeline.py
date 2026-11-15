"""P3: generate, validate and build separate synthetic dbt relations (DDR-118)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.config import get_settings
from app.pipelines.framework.context import DataError, RunContext
from app.pipelines.framework.registry import register
from app.pipelines.p2_elt.pipeline import run_dbt
from app.pipelines.p3_synthetic import generator as g


def _manifest(ctx: RunContext, profile: str) -> tuple[date, dict[str, Any], bool]:
    existing = ctx.data.execute(
        text(
            "SELECT date_to, reference_data, build_status FROM synthetic.manifests "
            "WHERE profile = :p FOR UPDATE"
        ),
        {"p": profile},
    ).first()
    if existing:
        return existing.date_to, existing.reference_data, existing.build_status == "ready"
    reference = g.snapshot(ctx.data)
    end = datetime.now(ZoneInfo("Asia/Kolkata")).date() - timedelta(days=1)
    days, _ = g.DAY_COUNTS[profile]
    ctx.data.execute(
        text(
            "INSERT INTO synthetic.manifests "
            "(profile, generator_seed, generator_version, date_from, date_to, "
            "region_id, kitchen_id, reference_data, pipeline_run_id) "
            "VALUES (:p, :seed, :version, :start, :end, :region, :kitchen, CAST(:ref AS jsonb), :run)"
        ),
        {
            "p": profile,
            "seed": g.SEED,
            "version": g.VERSION,
            "start": end - timedelta(days=days - 1),
            "end": end,
            "region": reference["region_id"],
            "kitchen": reference["kitchen_id"],
            "ref": json.dumps(reference, sort_keys=True),
            "run": ctx.run_id,
        },
    )
    return end, reference, False


def _tracks(ctx: RunContext, events: list[g.Event], reference: dict[str, Any]) -> None:
    selected: list[g.Event] = []
    for event in events:
        gps = event.data.get("gps")
        if event.kind == "delivery.completed" and isinstance(gps, dict) and gps.get("points") == 61:
            selected.append(event)
    for completed in selected:
        key = str(completed.data["rider_key"])
        ctx.data.execute(
            text(
                "INSERT INTO synthetic.gps_tracks (order_id, profile, region_id, kitchen_id, rider_key) "
                "VALUES (:o, 'demo', :r, :k, :key) ON CONFLICT (order_id) DO NOTHING"
            ),
            {"o": completed.order_id, "r": completed.region_id, "k": completed.kitchen_id, "key": key},
        )
        for i in range(61):
            fraction = i / 60
            ctx.data.execute(
                text(
                    "INSERT INTO synthetic.gps_points "
                    "(order_id, sequence, occurred_at, latitude, longitude) "
                    "VALUES (:o, :i, :at, :lat, :lon) ON CONFLICT (order_id, sequence) DO NOTHING"
                ),
                {
                    "o": completed.order_id,
                    "i": i,
                    "at": completed.when - timedelta(seconds=300 - 5 * i),
                    "lat": float(reference["kitchen_lat"])
                    + fraction * (float(reference["address_lat"]) - float(reference["kitchen_lat"])),
                    "lon": float(reference["kitchen_lon"])
                    + fraction * (float(reference["address_lon"]) - float(reference["kitchen_lon"])),
                },
            )


@register("p3_synthetic")
def run(ctx: RunContext) -> None:
    if not get_settings().is_local_or_test:
        raise DataError("P3 synthetic generation is local/test only")
    profile = "ml" if ctx.input_ref == "ml" else "demo"
    if ctx.input_ref not in ("demo", "ml"):
        raise DataError("unknown P3 profile")
    if profile == "ml" and ctx.input_ref != "ml":
        raise DataError("ML requires explicit CLI input")
    with ctx.stage("generate") as counts, ctx.data.begin():
        end, reference, completed = _manifest(ctx, profile)
        events, digest = g.generate(profile, end, reference)
        counts.rows_out = len(events)
        if completed and profile == "ml":
            counts.detail = {"reused": True, "sha256": digest}
            return
    with ctx.stage("validate") as counts:
        expected = g.DAY_COUNTS[profile][0] * g.DAY_COUNTS[profile][1]
        placed = [e for e in events if e.kind == "order.placed"]
        if len(placed) != expected or any(e.profile != profile for e in events):
            raise DataError("P3 profile count or flag mismatch")
        counts.rows_in = len(events)
        counts.detail = {"orders": len(placed), "sha256": digest}
    with ctx.stage("write synthetic") as counts, ctx.data.begin():
        counts.rows_out = g.write(ctx.data, events, ctx.run_id)
        if profile == "demo":
            _tracks(ctx, events, reference)
        ctx.data.execute(
            text(
                "UPDATE synthetic.manifests SET content_sha256 = :digest, generated_at = now(), "
                "build_status = 'building', pipeline_run_id = :run WHERE profile = :p"
            ),
            {"digest": digest, "run": ctx.run_id, "p": profile},
        )
    if profile == "demo":
        with ctx.data.begin():
            ctx.data.execute(text("SELECT ops.invalidate_synthetic_freshness()"))
    dbt_vars = {"dataset": "analytics_synthetic", "profile": profile}
    try:
        for stage, select in (("dbt staging", "staging"), ("dbt core", "core"), ("dbt marts", "marts")):
            with ctx.stage(stage) as counts:
                counts.rows_out = len(run_dbt("run", select, dbt_vars, role="p3_synth"))
        with ctx.stage("dbt tests") as counts:
            results = run_dbt("test", None, dbt_vars, role="p3_synth")
            failed = 0
            for result in results:
                passed = result["status"] == "pass"
                failed += not passed
                ctx.dq(
                    str(result["unique_id"]).split(".")[-1],
                    "critical",
                    passed,
                    int(result.get("failures") or 0),
                    {"status": result["status"]},
                )
            counts.rows_in, counts.rows_rejected = len(results), failed
            if failed:
                raise DataError(f"{failed} synthetic dbt checks failed")
    except DataError:
        with ctx.data.begin():
            ctx.data.execute(
                text("UPDATE synthetic.manifests SET build_status = 'failed' WHERE profile = :p"),
                {"p": profile},
            )
        raise
    with ctx.stage("publish freshness"), ctx.data.begin():
        ctx.data.execute(
            text("UPDATE synthetic.manifests SET build_status = 'ready' WHERE profile = :p"), {"p": profile}
        )
        if profile == "demo":
            ctx.data.execute(text("SELECT ops.publish_synthetic_freshness(:r)"), {"r": ctx.run_id})
    ctx.counts.update({"profile": profile, "orders": len(placed), "events": len(events), "sha256": digest})
