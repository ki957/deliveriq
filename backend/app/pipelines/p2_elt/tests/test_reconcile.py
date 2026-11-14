"""Operational reconciliation comparisons (ETL spec §11.2; DDR-117 (8))."""

from __future__ import annotations

from app.pipelines.p2_elt.reconcile import CHECKS, compare


def test_equal_totals_pass_and_every_check_is_reported() -> None:
    operational = {key: 3 for _name, key, _sql in CHECKS}
    analytics = {name: 3 for name, _key, _sql in CHECKS}
    result = compare(operational, analytics)
    assert [c.check for c in result] == [name for name, _k, _s in CHECKS]
    assert all(c.passed for c in result)


def test_a_mismatch_fails_only_its_check_with_both_figures() -> None:
    operational = {key: 0 for _name, key, _sql in CHECKS} | {"orders": 2}
    analytics = {name: 0 for name, _key, _sql in CHECKS} | {"reconcile_operational_orders": 1}
    [failed] = [c for c in compare(operational, analytics) if not c.passed]
    assert failed.check == "reconcile_operational_orders"
    assert failed.detail() == {"operational": 2, "analytics": 1}


def test_a_missing_operational_figure_counts_as_zero() -> None:
    analytics = {name: 0 for name, _key, _sql in CHECKS} | {"reconcile_operational_deliveries": 4}
    [failed] = [c for c in compare({}, analytics) if not c.passed]
    assert failed.check == "reconcile_operational_deliveries"
