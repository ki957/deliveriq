"""Pure checks for the DDR-124 forecast calculation."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.modules.reports.forecasting import DailyConsumption, evaluate, forecast

pytestmark = pytest.mark.unit


def rows(start: date, quantities: list[float]) -> list[DailyConsumption]:
    return [
        DailyConsumption(start + timedelta(days=i), "ingredient-1", "Rice", "g", q)
        for i, q in enumerate(quantities)
    ]


def test_forecast_uses_prior_same_weekday_mean_for_seven_days() -> None:
    start = date(2026, 1, 1)
    observations = rows(start, [float(i + 1) for i in range(28)])
    result = forecast(observations, start, start + timedelta(days=27))
    assert len(result) == 1
    assert len(result[0].daily) == 7
    assert result[0].daily[0][0] == start + timedelta(days=28)
    # Same weekday observations before the forecast date are 1, 8, 15, 22.
    assert result[0].daily[0][1] == pytest.approx(11.5)


def test_backtest_uses_two_final_week_windows_and_requires_strict_improvement() -> None:
    start = date(2026, 1, 1)
    # Identical weekly seasonality ties the previous-week baseline, so it does not pass.
    observations = rows(start, [float(i % 7) for i in range(90)])
    result = evaluate(observations, start, start + timedelta(days=89))
    assert result.model_mae == pytest.approx(result.baseline_mae)
    assert result.passed is False


def test_backtest_excludes_the_test_window_from_each_weekly_origin() -> None:
    start = date(2026, 1, 1)
    values = [10.0] * 76 + [100.0] * 14
    result = evaluate(rows(start, values), start, start + timedelta(days=89))
    assert result.model_mae > 0
    assert result.baseline_mae > 0
    assert result.passed is False
