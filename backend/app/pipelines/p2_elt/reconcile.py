"""Reconciliation of real operational totals with the analytics facts (ETL spec §11.2; DDR-117 (8)).

The operational side comes from `ops.operational_totals()` (counts only); the analytics side is read by
`p2_elt` from its own facts. Each comparison is a critical check: a mismatch fails the run and is visible on
the P2 page, and operational data is never adjusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection, text

# (check name, operational key, analytics SQL). Every fact here holds real rows only (DDR-48).
CHECKS: tuple[tuple[str, str, str], ...] = (
    ("reconcile_operational_orders", "orders", "SELECT count(*) FROM analytics.fact_orders"),
    (
        "reconcile_operational_order_payable",
        "orders_payable_paise",
        "SELECT coalesce(sum(payable_paise), 0) FROM analytics.fact_orders",
    ),
    (
        "reconcile_operational_payments_succeeded",
        "payments_succeeded",
        "SELECT count(*) FROM analytics.fact_payments WHERE outcome = 'SUCCEEDED'",
    ),
    (
        "reconcile_operational_payments_failed",
        "payments_failed",
        "SELECT count(*) FROM analytics.fact_payments WHERE outcome <> 'SUCCEEDED'",
    ),
    (
        "reconcile_operational_consumption",
        "consumption_lines",
        "SELECT count(*) FROM analytics.fact_inventory_movements WHERE movement = 'consumed'",
    ),
    (
        "reconcile_operational_deliveries",
        "deliveries_completed",
        "SELECT count(*) FROM analytics.fact_deliveries WHERE completed_at IS NOT NULL",
    ),
)


@dataclass(frozen=True)
class Comparison:
    check: str
    operational: int
    analytics: int

    @property
    def passed(self) -> bool:
        return self.operational == self.analytics

    def detail(self) -> dict[str, Any]:
        return {"operational": self.operational, "analytics": self.analytics}


def compare(operational: dict[str, Any], analytics: dict[str, int]) -> list[Comparison]:
    """Pure: one comparison per check; a missing operational figure counts as 0."""
    return [Comparison(name, int(operational.get(key) or 0), analytics[name]) for name, key, _sql in CHECKS]


def run(conn: Connection, *, orders_offset: int = 0) -> list[Comparison]:
    """Both sides in one read. `orders_offset` is set only by the TEST fault input (local/test)."""
    operational: dict[str, Any] = dict(conn.execute(text("SELECT ops.operational_totals()")).scalar_one())
    operational["orders"] = int(operational.get("orders") or 0) + orders_offset
    analytics = {name: int(conn.execute(text(sql)).scalar_one()) for name, _key, sql in CHECKS}
    return compare(operational, analytics)
