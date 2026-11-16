"""ETA model and deterministic synthetic evaluation (DDR-125)."""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import fmean

from sqlalchemy import Connection, text

from app.shared import geo

SIMULATION_SEED = 56
PROFILE = "ml_eta_v2"
PROFILE_VERSION = 2
PROFILE_NAMESPACE = uuid.UUID("a654a681-4cf7-4f44-9ff1-dd7bc402d3f9")
ORDERS_PER_DAY = 30
PROFILE_DAYS = 90
MIN_TRIP_KM = 0.1
MAX_TRIP_KM = 4.0
MAX_ROAD_KM = 6.0
SPEED_METERS_PER_FIVE_SECONDS = 15.0
SPEED_MPS = SPEED_METERS_PER_FIVE_SECONDS / 5.0
MAX_DELAY_SECONDS = 300.0
TARGET_COVERAGE = 0.8


@dataclass(frozen=True)
class Sample:
    day: date
    road_km: float
    duration_seconds: float


@dataclass(frozen=True)
class Evaluation:
    model_mae: float
    baseline_mae: float
    coverage: float
    passed: bool


@dataclass(frozen=True)
class Estimate:
    lower_seconds: int
    upper_seconds: int
    source: str
    simulated: bool


def generate_profile(end: date) -> tuple[Sample, ...]:
    """Build the versioned simulation profile. It contains no identity or GPS fields."""
    rng = random.Random(SIMULATION_SEED)  # noqa: S311 - reproducible simulation, not cryptography
    rows: list[Sample] = []
    for offset in range(PROFILE_DAYS):
        day = end - timedelta(days=PROFILE_DAYS - offset - 1)
        for _ in range(ORDERS_PER_DAY):
            # The values and distributions are approved labelled simulation defaults (DDR-125).
            straight_km = rng.uniform(MIN_TRIP_KM, MAX_TRIP_KM)
            destination = geo.Point(0.0, straight_km / 111.0)
            road = geo.road_adapter().road_distance(geo.Point(0.0, 0.0), destination, geo.km(straight_km))
            road_km = float(road.km)
            if road_km > MAX_ROAD_KM:
                continue
            delay = rng.uniform(0.0, MAX_DELAY_SECONDS)
            duration = road_km * 1000.0 / SPEED_MPS + delay
            rows.append(Sample(day, road_km, duration))
    return tuple(rows)


def profile_digest(rows: tuple[Sample, ...]) -> str:
    payload = [(r.day.isoformat(), round(r.road_km, 3), round(r.duration_seconds, 2)) for r in rows]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def same_profile_samples(left: tuple[Sample, ...], right: tuple[Sample, ...]) -> bool:
    """Compare the immutable row set independent of SQL's within-day UUID ordering."""

    def key(row: Sample) -> tuple[date, float, float]:
        return row.day, round(row.road_km, 3), round(row.duration_seconds, 2)

    return sorted(map(key, left)) == sorted(map(key, right))


def persist_profile(conn: Connection, rows: tuple[Sample, ...], end: date) -> tuple[int, str]:
    """Insert the versioned sample set once; an existing profile is only accepted if byte-equivalent."""
    if not rows:
        raise ValueError("ETA profile contains no samples")
    start, digest = min(r.day for r in rows), profile_digest(rows)
    conn.execute(
        text(
            "INSERT INTO synthetic.eta_profiles "
            "(profile, generator_seed, generator_version, date_from, date_to, content_sha256, sample_count) "
            "VALUES (:profile, :seed, :version, :start, :end, :digest, :count) "
            "ON CONFLICT (profile) DO NOTHING"
        ),
        {
            "profile": PROFILE,
            "seed": SIMULATION_SEED,
            "version": PROFILE_VERSION,
            "start": start,
            "end": end,
            "digest": digest,
            "count": len(rows),
        },
    )
    stored = conn.execute(
        text(
            "SELECT content_sha256, sample_count, date_from, date_to "
            "FROM synthetic.eta_profiles WHERE profile = :p"
        ),
        {"p": PROFILE},
    ).one()
    if (
        stored.content_sha256 != digest
        or stored.sample_count != len(rows)
        or stored.date_from != start
        or stored.date_to != end
    ):
        raise ValueError("The immutable ml_eta_v2 profile already exists with different content")
    for index, row in enumerate(rows):
        conn.execute(
            text(
                "INSERT INTO synthetic.eta_training_samples "
                "(profile, sample_id, sample_day, road_km, duration_seconds) "
                "VALUES (:profile, :id, :day, :distance, :duration) "
                "ON CONFLICT (profile, sample_id) DO NOTHING"
            ),
            {
                "profile": PROFILE,
                "id": uuid.uuid5(PROFILE_NAMESPACE, f"{row.day}|{index}"),
                "day": row.day,
                "distance": row.road_km,
                "duration": row.duration_seconds,
            },
        )
    actual = conn.execute(
        text("SELECT count(*) FROM synthetic.eta_training_samples WHERE profile = :p"), {"p": PROFILE}
    ).scalar_one()
    if actual != len(rows):
        raise ValueError("Stored ml_eta_v2 sample count does not match its immutable manifest")
    conn.execute(text("SELECT ops.publish_eta_profile(:p)"), {"p": PROFILE})
    return len(rows), digest


def _residuals(rows: tuple[Sample, ...] | list[Sample]) -> list[float]:
    return [r.duration_seconds - r.road_km * 1000.0 / SPEED_MPS for r in rows]


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * probability)
    return ordered[index]


def evaluate(rows: tuple[Sample, ...], start: date, end: date) -> Evaluation:
    """Two chronological seven-day origins over the final 14 days (DDR-124 pattern)."""
    errors: list[float] = []
    baseline_errors: list[float] = []
    covered: list[bool] = []
    for origin in (end - timedelta(days=13), end - timedelta(days=6)):
        train = [r for r in rows if start <= r.day < origin]
        test = [r for r in rows if origin <= r.day < origin + timedelta(days=7)]
        residuals = _residuals(train)
        center = fmean(residuals) if residuals else 0.0
        low, high = _quantile(residuals, 0.1), _quantile(residuals, 0.9)
        for sample in test:
            baseline = sample.road_km * 1000.0 / SPEED_MPS
            prediction = baseline + center
            errors.append(abs(prediction - sample.duration_seconds))
            baseline_errors.append(abs(baseline - sample.duration_seconds))
            if low is not None and high is not None:
                actual_residual = sample.duration_seconds - baseline
                covered.append(low <= actual_residual <= high)
    model_mae = fmean(errors) if errors else 0.0
    baseline_mae = fmean(baseline_errors) if baseline_errors else 0.0
    coverage = sum(covered) / len(covered) if covered else 0.0
    return Evaluation(
        model_mae,
        baseline_mae,
        coverage,
        bool(errors) and model_mae < baseline_mae and coverage >= TARGET_COVERAGE,
    )


def estimate(road_km: float, rows: tuple[Sample, ...] | None, *, simulated: bool) -> Estimate:
    """Use the calibrated model when possible; otherwise return the always-available rule estimate."""
    baseline = road_km * 1000.0 / SPEED_MPS
    if rows:
        residuals = _residuals(rows)
        low, high = _quantile(residuals, 0.1), _quantile(residuals, 0.9)
        if low is not None and high is not None and len(residuals) >= 2:
            return Estimate(max(0, round(baseline + low)), max(0, round(baseline + high)), "model", simulated)
    # The fallback remains explicitly labelled; it reports the exact rule estimate at both bounds
    # rather than inventing a range width that has no approved basis.
    point = max(0, round(baseline))
    return Estimate(point, point, "rule_based", simulated)
