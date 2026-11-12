"""Data & Pipelines: list, inspect, trigger, cancel and retry runs (DATA_PIPELINE §11–12; DDR-64, DDR-105).

Deny by default. CA views and operates every run; RM views runs of their own region only and has no
action rights; every other role is refused. Out-of-scope runs are reported as not found, so their
existence is not revealed. The worker executes runs; this module only records requests.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.permissions import Permission, Principal, can
from app.core.request_context import current_request_id
from app.modules.pipelines import repository as repo

# Pipelines that can be queued now, with the inputs each accepts. Later tasks add their pipelines
# here when their code lands (P2 Task 7, P3 Task 8, K1–K3 Task 12).
TRIGGERABLE: dict[str, frozenset[str]] = {"p1_sop": frozenset({"sop", "fault:records", "fault:structural"})}
DEFAULT_INPUT: dict[str, str] = {"p1_sop": "sop"}
# TEST fault-injection inputs (DDR-65, DDR-104): local/test only, always flagged as test runs.
FAULT_INPUTS = frozenset({"fault:records", "fault:structural"})
# Runs carry the region of the kitchen they load into (DDR-105).
RUN_KITCHEN: dict[str, str] = {"p1_sop": "KIT-CHN-001"}
ERROR_PAGE = 500
TERMINAL = frozenset({"succeeded", "completed_with_quarantine", "failed", "cancelled"})
RETRYABLE = frozenset({"failed", "cancelled"})


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class FaultInputRefused(Exception):
    """Fault-injection inputs are refused outside local/test (DDR-65)."""


@dataclass(frozen=True)
class RunDetail:
    run: repo.RunRow
    stages: list[dict[str, object]]
    errors: list[dict[str, object]]
    errors_total: int
    dq_results: list[dict[str, object]]


@dataclass(frozen=True)
class PipelineSummary:
    pipeline: repo.PipelineRow
    implemented: bool
    last_run: repo.RunRow | None


def view_scope(principal: Principal) -> frozenset[uuid.UUID] | None:
    """None = all runs (a global grant); else the regions this principal may view; Forbidden if none."""
    if can(principal, Permission.PIPELINES_VIEW):  # only a global (CA) grant passes without a region
        return None
    regions = frozenset(
        g.region_id
        for g in principal.grants
        if g.region_id is not None and can(principal, Permission.PIPELINES_VIEW, region_id=g.region_id)
    )
    if not regions:
        raise Forbidden
    return regions


def _actor_role(principal: Principal, permission: Permission, region_id: uuid.UUID | None) -> str:
    for grant in principal.grants:
        if can(Principal(principal.user_id, (grant,)), permission, region_id=region_id):
            return grant.role.value
    raise Forbidden


def _visible(conn: Connection, principal: Principal, run_id: uuid.UUID) -> repo.RunRow:
    regions = view_scope(principal)
    run = repo.find_run(conn, run_id)
    if run is None or (regions is not None and run.region_id not in regions):
        raise NotFound
    return run


# ---------------------------------------------------------------- reads
def list_pipelines(principal: Principal) -> list[PipelineSummary]:
    regions = view_scope(principal)
    with get_engine().connect() as conn:
        last = repo.last_runs(conn, regions)
        return [
            PipelineSummary(p, p.name in TRIGGERABLE, last.get(p.name)) for p in repo.list_pipelines(conn)
        ]


def list_runs(principal: Principal, pipeline: str | None, limit: int) -> list[repo.RunRow]:
    regions = view_scope(principal)
    with get_engine().connect() as conn:
        return repo.list_runs(conn, regions, pipeline, limit)


def run_detail(principal: Principal, run_id: uuid.UUID) -> RunDetail:
    with get_engine().connect() as conn:
        run = _visible(conn, principal, run_id)
        errors, total = repo.errors(conn, run_id, ERROR_PAGE)
        return RunDetail(
            run=run,
            stages=[dict(r._mapping) for r in repo.stages(conn, run_id)],
            errors=[dict(r._mapping) for r in errors],
            errors_total=total,
            dq_results=[dict(r._mapping) for r in repo.dq_results(conn, run_id)],
        )


def run_report(principal: Principal, run_id: uuid.UUID) -> str:
    with get_engine().connect() as conn:
        _visible(conn, principal, run_id)
        markdown = repo.report(conn, run_id)
    if markdown is None:
        raise NotFound
    return markdown


# ---------------------------------------------------------------- actions (CA only, audited)
def _queue(
    conn: Connection,
    *,
    pipeline: str,
    input_ref: str | None,
    trigger: str,
    actor_user_id: uuid.UUID | None,
    retry_of: uuid.UUID | None = None,
    is_test: bool = False,
) -> tuple[uuid.UUID, uuid.UUID | None]:
    if repo.find_pipeline(conn, pipeline) is None:
        raise NotFound
    allowed = TRIGGERABLE.get(pipeline)
    if allowed is None:
        raise Conflict(f"{pipeline} is not available yet")
    ref = input_ref or DEFAULT_INPUT[pipeline]
    if ref not in allowed:
        raise Conflict(f"{pipeline} does not accept input {ref}")
    if ref in FAULT_INPUTS:
        if not get_settings().is_local_or_test:
            raise FaultInputRefused
        is_test = True
    region_id = repo.kitchen_region(conn, RUN_KITCHEN[pipeline]) if pipeline in RUN_KITCHEN else None
    try:
        with conn.begin_nested():
            run_id = repo.insert_run(
                conn,
                pipeline=pipeline,
                trigger=trigger,
                actor_user_id=actor_user_id,
                is_test=is_test,
                region_id=region_id,
                input_ref=ref,
                retry_of=retry_of,
            )
    except IntegrityError as exc:
        if "pipeline_runs_one_active_uq" in str(exc.orig):
            raise Conflict(f"{pipeline} already has a queued or running run") from None
        raise
    return run_id, region_id


def trigger(principal: Principal, pipeline: str, input_ref: str | None) -> repo.RunRow:
    with get_engine().begin() as conn:
        region = (
            repo.kitchen_region(conn, RUN_KITCHEN[pipeline])
            if pipeline in RUN_KITCHEN and repo.find_pipeline(conn, pipeline)
            else None
        )
        role = _actor_role(principal, Permission.PIPELINES_OPERATE, region)
        run_id, region_id = _queue(
            conn, pipeline=pipeline, input_ref=input_ref, trigger="ui", actor_user_id=principal.user_id
        )
        repo.write_audit(
            conn,
            action="pipeline.run",
            outcome="SUCCESS",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_id=str(run_id),
            region_id=region_id,
            correlation_id=current_request_id(),
            after={"pipeline": pipeline, "input_ref": input_ref},
        )
        run = repo.find_run(conn, run_id)
    if run is None:
        raise NotFound
    return run


def cancel(principal: Principal, run_id: uuid.UUID) -> str:
    with get_engine().begin() as conn:
        run = _visible(conn, principal, run_id)
        role = _actor_role(principal, Permission.PIPELINES_OPERATE, run.region_id)
        outcome = repo.cancel(conn, run_id)
        if outcome == "not_active":
            raise Conflict("Only queued or running runs can be cancelled")
        repo.write_audit(
            conn,
            action="pipeline.cancel",
            outcome="SUCCESS",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_id=str(run_id),
            region_id=run.region_id,
            correlation_id=current_request_id(),
            after={"outcome": outcome},
        )
    return outcome


def retry(principal: Principal, run_id: uuid.UUID) -> repo.RunRow:
    with get_engine().begin() as conn:
        original = _visible(conn, principal, run_id)
        role = _actor_role(principal, Permission.PIPELINES_OPERATE, original.region_id)
        if original.status not in RETRYABLE:
            raise Conflict("Only failed or cancelled runs can be retried")
        new_id, region_id = _queue(
            conn,
            pipeline=original.pipeline,
            input_ref=original.input_ref,
            trigger="ui",
            actor_user_id=principal.user_id,
            retry_of=run_id,
            is_test=original.is_test,
        )
        repo.write_audit(
            conn,
            action="pipeline.retry",
            outcome="SUCCESS",
            actor_user_id=principal.user_id,
            actor_role=role,
            target_id=str(new_id),
            region_id=region_id,
            correlation_id=current_request_id(),
            after={"retry_of": str(run_id)},
        )
        run = repo.find_run(conn, new_id)
    if run is None:
        raise NotFound
    return run


# ---------------------------------------------------------------- CLI (host operator, same entry point)
def trigger_from_cli(pipeline: str, input_ref: str | None) -> uuid.UUID:
    with get_engine().begin() as conn:
        run_id, region_id = _queue(
            conn, pipeline=pipeline, input_ref=input_ref, trigger="cli", actor_user_id=None
        )
        repo.write_audit(
            conn,
            action="pipeline.run",
            outcome="SUCCESS",
            actor_user_id=None,
            actor_role="SYSTEM",
            target_id=str(run_id),
            region_id=region_id,
            correlation_id=None,
            reason="CLI",
            after={"pipeline": pipeline, "input_ref": input_ref},
        )
    return run_id


def run_status(run_id: uuid.UUID) -> repo.RunRow:
    with get_engine().connect() as conn:
        run = repo.find_run(conn, run_id)
    if run is None:
        raise NotFound
    return run
