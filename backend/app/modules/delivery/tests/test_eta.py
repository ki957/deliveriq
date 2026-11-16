"""Named Task 19A ETA profile and model checks (DDR-125)."""

from dataclasses import fields
from datetime import date

from app.modules.delivery import eta
from app.modules.orders.api import _eta_label


def test_ml_eta_v2_is_reproducible_and_contains_no_customer_or_gps_fields() -> None:
    end = date(2026, 11, 15)
    first = eta.generate_profile(end)
    second = eta.generate_profile(end)

    assert first == second
    assert eta.same_profile_samples(first, tuple(reversed(first)))
    assert len(first) > eta.PROFILE_DAYS * 20
    assert {field.name for field in fields(eta.Sample)} == {"day", "road_km", "duration_seconds"}
    assert all(eta.MIN_TRIP_KM <= row.road_km / 1.4 <= eta.MAX_TRIP_KM for row in first)
    assert all(row.road_km <= eta.MAX_ROAD_KM for row in first)


def test_eta_model_must_beat_rule_baseline_and_meet_labelled_coverage_default() -> None:
    end = date(2026, 11, 15)
    rows = eta.generate_profile(end)
    result = eta.evaluate(rows, rows[0].day, end)

    assert result.model_mae < result.baseline_mae
    assert result.coverage >= eta.TARGET_COVERAGE
    assert result.passed


def test_rule_fallback_uses_held_out_residual_range_at_80_percent_target() -> None:
    end = date(2026, 11, 15)
    rows = eta.generate_profile(end)
    evaluation = eta.evaluate(rows, min(r.day for r in rows), end)
    result = eta.estimate(1.5, rows, simulated=True, model_passed=False)

    assert result is not None
    assert result.source == "estimated_range"
    assert result.simulated is True
    assert result.lower_seconds < result.upper_seconds
    assert evaluation.rule_interval_coverage >= eta.TARGET_COVERAGE
    assert _eta_label(result) == "Simulated · estimated range"


def test_without_ready_profile_returns_labelled_point_without_range() -> None:
    result = eta.estimate(1.5, None, simulated=False)

    assert result is not None
    assert result.source == "rough_estimate"
    assert result.simulated is False
    assert result.lower_seconds == result.upper_seconds == 500
    assert _eta_label(result) == "Trained on simulated data · rough estimate, no range available"
