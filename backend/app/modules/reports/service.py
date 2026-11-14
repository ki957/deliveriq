"""Management reports (#10 §10; MG-07, MG-08; DDR-117). RM: kitchens of assigned regions; CA: all.

Sync like every service (DDR-82). Values come from the analytics marts only (persisted, MG-08); a KPI whose
denominator is 0 has no value, never an invented one.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.db import get_engine
from app.core.permissions import Grant, Permission, Principal, can
from app.core.request_context import current_request_id
from app.modules.reports import domain as d
from app.modules.reports import repository as repo
from app.shared.audit import write_event

P = Permission.MGMT_REPORTS_VIEW
IST = ZoneInfo("Asia/Kolkata")
EXPORT_MAX = 5_000  # DDR-117 (10), as DDR-114 (8)


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Invalid(Exception):
    pass


def _regions(principal: Principal) -> list[uuid.UUID] | None:
    """None = every region (a global grant); else the regions the permission is granted in."""
    if can(principal, P):
        return None
    regions = sorted(
        {g.region_id for g in principal.grants if g.region_id and can(principal, P, region_id=g.region_id)}
    )
    if not regions:
        raise Forbidden
    return regions


def _role(principal: Principal) -> str:
    for g in principal.grants:
        alone = Principal(principal.user_id, (Grant(g.role, g.region_id, g.kitchen_id),))
        if can(alone, P) or (g.region_id and can(alone, P, region_id=g.region_id)):
            return g.role.value
    raise Forbidden


@dataclass(frozen=True)
class KpiValue:
    kpi: d.Kpi
    value: float | None
    previous: float | None


@dataclass(frozen=True)
class Report:
    dataset: d.Dataset
    available: bool
    fresh_as_of: datetime | None
    start: date
    end: date
    previous_start: date
    previous_end: date
    kitchens: list[repo.KitchenRef]
    kitchen_id: uuid.UUID | None
    kpis: list[KpiValue]
    daily: list[repo.DailyRow]
    ingredients: list[repo.IngredientRow]


def report(
    principal: Principal,
    *,
    dataset: d.Dataset,
    date_from: date | None,
    date_to: date | None,
    kitchen_id: uuid.UUID | None,
) -> Report:
    if dataset not in d.DATASETS:
        raise Invalid("Unknown dataset")
    regions = _regions(principal)
    try:
        start, end = d.period(datetime.now(IST).date(), date_from, date_to)
    except d.InvalidRange as exc:
        raise Invalid(str(exc)) from None
    prev_start, prev_end = d.previous_period(start, end)
    with get_engine().connect() as conn:
        in_scope = repo.kitchens(conn, regions)
        if kitchen_id is not None and kitchen_id not in {k.id for k in in_scope}:
            raise NotFound  # outside scope reads as not found
        ids = [kitchen_id] if kitchen_id else [k.id for k in in_scope]
        fresh = repo.freshness(conn, dataset)
        if not repo.built(conn, dataset):
            return Report(
                dataset, False, fresh, start, end, prev_start, prev_end, in_scope, kitchen_id, [], [], []
            )
        now, before = (
            d.compute(repo.totals(conn, dataset, ids, start, end)),
            d.compute(repo.totals(conn, dataset, ids, prev_start, prev_end)),
        )
        return Report(
            dataset,
            True,
            fresh,
            start,
            end,
            prev_start,
            prev_end,
            in_scope,
            kitchen_id,
            [KpiValue(k, now[k.key], before[k.key]) for k in d.KPIS],
            repo.daily(conn, dataset, ids, start, end),
            repo.ingredients(conn, dataset, ids, start, end),
        )


def _cell(value: object) -> object:
    # Neutralise spreadsheet formulas in exported text (CSV injection).
    return f"'{value}" if isinstance(value, str) and value[:1] in "=+-@" else value


def report_csv(principal: Principal, **kwargs: object) -> str:
    r = report(principal, **kwargs)  # type: ignore[arg-type]
    if not r.available:
        raise Invalid(f"The {d.DATASETS[r.dataset].lower()} dataset is not built yet")
    if len(r.daily) > EXPORT_MAX:  # pragma: no cover - at most 31 daily rows
        raise Invalid(f"The export is limited to {EXPORT_MAX} rows")
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["# dataset", d.DATASETS[r.dataset], "definition status", d.DEFINITION_STATUS])
    writer.writerow(["date", "orders_placed", "orders_delivered", "payable_paise", "discount_paise"])
    for row in r.daily:
        writer.writerow([_cell(v) for v in (row.day.isoformat(), row.orders_placed, row.orders_delivered,
                                            row.payable_paise, row.discount_paise)])  # fmt: skip
    with get_engine().begin() as conn:
        write_event(
            conn,
            action="management.export.report",
            actor_user_id=principal.user_id,
            actor_role=_role(principal),
            target_type="export",
            target_id="report",
            kitchen_id=r.kitchen_id,
            correlation_id=current_request_id(),
            after={
                "rows": len(r.daily),
                "dataset": r.dataset,
                "from": r.start.isoformat(),
                "to": r.end.isoformat(),
            },
        )
    return out.getvalue()
