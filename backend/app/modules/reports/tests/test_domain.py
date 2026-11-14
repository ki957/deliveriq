"""Report KPI rules (ETL spec §9; DDR-44, DDR-117 (1)–(3), (12))."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.reports import domain as d


def test_kpis_are_never_business_truth_and_all_carry_a_source() -> None:
    assert d.KPIS_AS_BUSINESS_TRUTH is False  # class A (DDR-44): changing this needs an approved DDR
    assert d.DEFINITION_STATUS == "Definition pending approval (DDR-44)"
    assert all(k.source.startswith("ETL spec §") and k.formula for k in d.KPIS)
    assert {k.key for k in d.KPIS if k.chosen_denominator} == {
        "average_order_value", "rejection_rate", "delivery_completion_rate",
    }  # fmt: skip
    assert set(d.compute(d.Totals())) == {k.key for k in d.KPIS}


def test_formulas_follow_the_etl_spec() -> None:
    t = d.Totals(
        orders_placed=10, orders_delivered=4, orders_rejected_or_cancelled=2, discount_paise=500,
        delivered_payable_paise=200_000, gross_food_sales=300_000, orders_accepted=8, orders_rejected=2,
        orders_decided=9, orders_ready=6, accept_seconds_total=480.0, prepare_seconds_total=3_600.0,
        deliveries_completed=4, deliveries_failed=1, delivery_seconds_total=4_800.0,
        payments_succeeded=5, payments_failed=1,
    )  # fmt: skip
    v = d.compute(t)
    assert v["average_order_value"] == 50_000  # payable of delivered ÷ delivered
    assert v["acceptance_latency"] == 60  # seconds, over accepted orders
    assert v["preparation_duration"] == 600
    assert v["rejection_rate"] == pytest.approx(2 / 9)  # ÷ orders the kitchen accepted or rejected
    assert v["delivery_duration"] == 1_200
    assert v["delivery_completion_rate"] == pytest.approx(4 / 5)
    assert (v["gross_food_sales"], v["discounts"], v["payments_failed"]) == (300_000, 500, 1)


def test_an_empty_period_has_no_invented_ratios() -> None:
    v = d.compute(d.Totals())
    ratios = {"average_order_value", "acceptance_latency", "preparation_duration", "rejection_rate",
              "delivery_duration", "delivery_completion_rate"}  # fmt: skip
    assert all(v[k] is None for k in ratios)
    assert all(v[k] == 0 for k in set(v) - ratios)


def test_periods_default_to_seven_days_and_compare_with_the_one_before() -> None:
    today = date(2026, 11, 12)
    assert d.period(today, None, None) == (date(2026, 11, 6), today)
    assert d.previous_period(date(2026, 11, 6), today) == (date(2026, 10, 30), date(2026, 11, 5))
    assert d.period(today, date(2026, 10, 13), today) == (date(2026, 10, 13), today)  # 31 days
    with pytest.raises(d.InvalidRange):
        d.period(today, date(2026, 10, 12), today)  # 32 days
    with pytest.raises(d.InvalidRange):
        d.period(today, today, date(2026, 11, 1))
