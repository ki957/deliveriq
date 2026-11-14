"""Management report KPIs (ETL spec §9; #10 §10; MG-07, MG-08; DDR-44, DDR-117 (1)–(5), (12)). Pure: no I/O.

Every KPI is an ETL spec §9 formula over the DDR-75 marts' base measures and carries its definition status.
DDR-44 (KPI formulas and accounting definitions) is open, so nothing here is business truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

# DDR-117 (12), class A (DDR-44): KPIs are never presented as business truth. A test asserts this stays off.
KPIS_AS_BUSINESS_TRUTH: Literal[False] = False
Dataset = Literal["analytics", "analytics_synthetic"]
DEFINITION_STATUS = "Definition pending approval (DDR-44)"
DENOMINATOR_NOTE = "Denominator chosen for the POC, pending approval (DDR-117 (2))"

# Dataset → label (DDR-74: never mixed). Values are schema names, used only from this whitelist.
DATASETS: dict[Dataset, str] = {"analytics": "Real", "analytics_synthetic": "Simulated"}
DEFAULT_DAYS = 7  # DDR-117 (3)
MAX_DAYS = 31
FRESHNESS_WARN_HOURS = 24  # labelled test default (DDR-116 (12))

# DDR-117 (5): #10 §10 areas with no source model.
NOT_AVAILABLE: tuple[tuple[str, str], ...] = (
    (
        "Customers (new, repeat, ratings)",
        "No customer-experience mart (deferred, DDR-75) and no rating model",
    ),
    ("Staff (active agents, workload)", "No staff mart in the POC marts (DDR-75)"),
    ("Promotions (usage, discount, resulting orders)", "No promotion model (DDR-114 (2))"),
)


@dataclass(frozen=True)
class Kpi:
    key: str
    label: str
    unit: Literal["count", "paise", "seconds", "ratio"]
    formula: str
    source: str
    chosen_denominator: bool = False


KPIS: tuple[Kpi, ...] = (
    Kpi(
        "orders_placed", "Orders placed", "count", "Distinct eligible order IDs", "ETL spec §9.6 order count"
    ),
    Kpi("orders_delivered", "Orders delivered", "count", "Orders with a delivered time", "ETL spec §9.1"),
    Kpi(
        "orders_rejected_or_cancelled",
        "Orders rejected or cancelled",
        "count",
        "Orders with a rejected or cancelled time",
        "ETL spec §9.1",
    ),
    Kpi(
        "gross_food_sales",
        "Gross food sales",
        "paise",
        "Sum of order item line amounts before discounts",
        "ETL spec §9.6",
    ),
    Kpi("discounts", "Discounts", "paise", "Sum of recorded discount amounts", "ETL spec §9.6"),
    Kpi(
        "average_order_value",
        "Average order value",
        "paise",
        "Payable of delivered orders ÷ delivered orders",
        "ETL spec §9.6",
        chosen_denominator=True,
    ),
    Kpi(
        "acceptance_latency",
        "Average acceptance latency",
        "seconds",
        "Accepted time minus placed time, averaged over accepted orders",
        "ETL spec §9.4",
    ),
    Kpi(
        "preparation_duration",
        "Average preparation duration",
        "seconds",
        "Ready time minus accepted time, averaged over ready orders",
        "ETL spec §9.4",
    ),
    Kpi(
        "rejection_rate",
        "Rejection rate",
        "ratio",
        "Rejected orders ÷ orders the kitchen accepted or rejected",
        "ETL spec §9.4",
        chosen_denominator=True,
    ),
    Kpi(
        "delivery_duration",
        "Average delivery duration",
        "seconds",
        "Delivered time minus picked-up time, averaged over completed deliveries",
        "ETL spec §9.5",
    ),
    Kpi(
        "delivery_completion_rate",
        "Delivery completion rate",
        "ratio",
        "Delivered ÷ (delivered + failed)",
        "ETL spec §9.5",
        chosen_denominator=True,
    ),
    Kpi("payments_succeeded", "Payments succeeded", "count", "Succeeded payment attempts", "ETL spec §8.3"),
    Kpi(
        "payments_failed", "Payments failed", "count", "Failed or timed-out payment attempts", "ETL spec §8.3"
    ),
)


@dataclass(frozen=True)
class Totals:
    """Base measures summed over a period and the kitchens in scope (from the marts)."""

    orders_placed: int = 0
    orders_delivered: int = 0
    orders_rejected_or_cancelled: int = 0
    payable_paise: int = 0
    discount_paise: int = 0
    delivered_payable_paise: int = 0
    gross_food_sales: int = 0
    orders_accepted: int = 0
    orders_rejected: int = 0
    orders_decided: int = 0
    orders_ready: int = 0
    accept_seconds_total: float = 0.0
    prepare_seconds_total: float = 0.0
    deliveries_completed: int = 0
    deliveries_failed: int = 0
    delivery_seconds_total: float = 0.0
    payments_succeeded: int = 0
    payments_failed: int = 0


def _ratio(numerator: float, denominator: float) -> float | None:
    """None when the denominator is 0: no value is invented (MG-08)."""
    return numerator / denominator if denominator else None


def compute(t: Totals) -> dict[str, float | None]:
    return {
        "orders_placed": t.orders_placed,
        "orders_delivered": t.orders_delivered,
        "orders_rejected_or_cancelled": t.orders_rejected_or_cancelled,
        "gross_food_sales": t.gross_food_sales,
        "discounts": t.discount_paise,
        "average_order_value": _ratio(t.delivered_payable_paise, t.orders_delivered),
        "acceptance_latency": _ratio(t.accept_seconds_total, t.orders_accepted),
        "preparation_duration": _ratio(t.prepare_seconds_total, t.orders_ready),
        "rejection_rate": _ratio(t.orders_rejected, t.orders_decided),
        "delivery_duration": _ratio(t.delivery_seconds_total, t.deliveries_completed),
        "delivery_completion_rate": _ratio(
            t.deliveries_completed, t.deliveries_completed + t.deliveries_failed
        ),
        "payments_succeeded": t.payments_succeeded,
        "payments_failed": t.payments_failed,
    }


class InvalidRange(ValueError):
    pass


def period(today: date, date_from: date | None, date_to: date | None) -> tuple[date, date]:
    """Inclusive IST dates; 7 days ending today by default; at most 31 days (DDR-117 (3))."""
    end = date_to or today
    start = date_from or end - timedelta(days=DEFAULT_DAYS - 1)
    if start > end:
        raise InvalidRange("The start must not be after the end")
    if (end - start).days + 1 > MAX_DAYS:
        raise InvalidRange(f"Choose a range of at most {MAX_DAYS} days")
    return start, end


def previous_period(start: date, end: date) -> tuple[date, date]:
    """The period of the same length just before (#10 §10 period comparison)."""
    length = (end - start).days + 1
    return start - timedelta(days=length), start - timedelta(days=1)
