"""`/api/v1/management/reports`: scoped management reports and their CSV export (DDR-117)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.modules.identity.dependencies import CurrentPrincipal, csrf_protect
from app.modules.reports import domain as d
from app.modules.reports import service
from app.modules.reports.schemas import (
    DailyOut,
    IngredientOut,
    KitchenRefOut,
    KpiOut,
    NotAvailableOut,
    ReportOut,
)

router = APIRouter(prefix="/api/v1/management", tags=["reports"], dependencies=[Depends(csrf_protect)])
Dataset = Annotated[Literal["analytics", "analytics_synthetic"], Query()]


def _call[T](fn: Callable[[], T]) -> T:
    try:
        return fn()
    except service.Forbidden:
        raise HTTPException(status_code=403, detail="Forbidden") from None
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Not found") from None
    except service.Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _out(r: service.Report) -> ReportOut:
    return ReportOut(
        dataset=r.dataset,
        dataset_label=d.DATASETS[r.dataset],
        available=r.available,
        unavailable_reason=None if r.available else "Not built yet (Task 14)",
        fresh_as_of=r.fresh_as_of,
        freshness_warn_hours=d.FRESHNESS_WARN_HOURS,
        stale=r.fresh_as_of is None
        or datetime.now(UTC) - r.fresh_as_of > timedelta(hours=d.FRESHNESS_WARN_HOURS),
        date_from=r.start,
        date_to=r.end,
        previous_from=r.previous_start,
        previous_to=r.previous_end,
        kitchens=[KitchenRefOut(id=k.id, name=k.name) for k in r.kitchens],
        kitchen_id=r.kitchen_id,
        kpis=[
            KpiOut(
                key=v.kpi.key,
                label=v.kpi.label,
                unit=v.kpi.unit,
                value=v.value,
                previous=v.previous,
                formula=v.kpi.formula,
                source=v.kpi.source,
                definition_status=d.DEFINITION_STATUS,
                denominator_note=d.DENOMINATOR_NOTE if v.kpi.chosen_denominator else None,
            )
            for v in r.kpis
        ],
        daily=[DailyOut.model_validate(x, from_attributes=True) for x in r.daily],
        ingredients=[IngredientOut.model_validate(x, from_attributes=True) for x in r.ingredients],
        not_available=[NotAvailableOut(area=a, reason=why) for a, why in d.NOT_AVAILABLE],
        kpis_are_business_truth=d.KPIS_AS_BUSINESS_TRUTH,
    )


@router.get("/reports", response_model=ReportOut)
def report(
    principal: CurrentPrincipal,
    dataset: Dataset = "analytics",
    date_from: date | None = None,
    date_to: date | None = None,
    kitchen_id: uuid.UUID | None = None,
) -> ReportOut:
    """KPIs with definition status and previous-period values, daily rows and ingredient consumption."""
    return _out(
        _call(
            lambda: service.report(
                principal, dataset=dataset, date_from=date_from, date_to=date_to, kitchen_id=kitchen_id
            )
        )
    )


@router.get("/reports.csv", response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def report_csv(
    principal: CurrentPrincipal,
    dataset: Dataset = "analytics",
    date_from: date | None = None,
    date_to: date | None = None,
    kitchen_id: uuid.UUID | None = None,
) -> Response:
    """The current daily report view as CSV, same scope; the export is audited."""
    body = _call(
        lambda: service.report_csv(
            principal, dataset=dataset, date_from=date_from, date_to=date_to, kitchen_id=kitchen_id
        )
    )
    return Response(
        body, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="report.csv"'}
    )
