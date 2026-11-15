"""Deterministic ingredient-demand forecast and rolling-origin evaluation (DDR-124)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import fmean


@dataclass(frozen=True)
class DailyConsumption:
    day: date
    ingredient_id: str
    name: str
    unit: str
    quantity: float


@dataclass(frozen=True)
class IngredientForecast:
    ingredient_id: str
    name: str
    unit: str
    daily: tuple[tuple[date, float], ...]


@dataclass(frozen=True)
class Backtest:
    model_mae: float
    baseline_mae: float
    passed: bool


def _series(
    rows: Iterable[DailyConsumption],
) -> tuple[dict[str, dict[date, float]], dict[str, tuple[str, str]]]:
    values: dict[str, dict[date, float]] = defaultdict(dict)
    labels: dict[str, tuple[str, str]] = {}
    for row in rows:
        values[row.ingredient_id][row.day] = row.quantity
        labels[row.ingredient_id] = (row.name, row.unit)
    return values, labels


def _weekday_mean(values: dict[date, float], target: date, *, before: date | None = None) -> float:
    cutoff = before or target
    history = [
        quantity for day, quantity in values.items() if day < cutoff and day.weekday() == target.weekday()
    ]
    return fmean(history) if history else 0.0


def evaluate(rows: Iterable[DailyConsumption], start: date, end: date) -> Backtest:
    """Two seven-day test windows over the final 14 days; absent mart rows mean zero consumption."""
    values, _ = _series(rows)
    model_errors: list[float] = []
    baseline_errors: list[float] = []
    for origin in (end - timedelta(days=13), end - timedelta(days=6)):
        window_errors: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for ingredient_id, observed in values.items():
            for offset in range(7):
                target = origin + timedelta(days=offset)
                if target < start or target > end:
                    continue
                actual = observed.get(target, 0.0)
                model = _weekday_mean(observed, target, before=origin)
                baseline = observed.get(target - timedelta(days=7), 0.0)
                window_errors[ingredient_id].append((abs(model - actual), abs(baseline - actual)))
        for errors in window_errors.values():
            model_errors.append(fmean(pair[0] for pair in errors))
            baseline_errors.append(fmean(pair[1] for pair in errors))
    model_mae = fmean(model_errors) if model_errors else 0.0
    baseline_mae = fmean(baseline_errors) if baseline_errors else 0.0
    return Backtest(model_mae, baseline_mae, bool(model_errors) and model_mae < baseline_mae)


def forecast(
    rows: Iterable[DailyConsumption], start: date, end: date, horizon: int = 7
) -> tuple[IngredientForecast, ...]:
    values, labels = _series(rows)
    output: list[IngredientForecast] = []
    for ingredient_id in sorted(values):
        name, unit = labels[ingredient_id]
        predictions = tuple(
            (target, _weekday_mean(values[ingredient_id], target))
            for target in (end + timedelta(days=offset) for offset in range(1, horizon + 1))
        )
        output.append(IngredientForecast(ingredient_id, name, unit, predictions))
    return tuple(output)
