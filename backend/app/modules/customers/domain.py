"""Serviceability rule (CU-03, #1 §6): straight-line ≤ 4 km AND road ≤ 6 km. Standard library only.

Limits come from configuration (SERVICEABILITY_* keys, migration 0005); road distance comes from the
adapter and may be an estimate (DDR-55, DDR-110).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Serviceability:
    serviceable: bool
    straight_line_km: Decimal
    straight_line_max_km: Decimal
    straight_line_ok: bool
    road_km: Decimal
    road_max_km: Decimal
    road_ok: bool
    road_km_estimated: bool


def evaluate(
    straight_line_km: Decimal,
    road_km: Decimal,
    *,
    road_estimated: bool,
    straight_line_max_km: Decimal,
    road_max_km: Decimal,
) -> Serviceability:
    straight_ok = straight_line_km <= straight_line_max_km
    road_ok = road_km <= road_max_km
    return Serviceability(
        serviceable=straight_ok and road_ok,
        straight_line_km=straight_line_km,
        straight_line_max_km=straight_line_max_km,
        straight_line_ok=straight_ok,
        road_km=road_km,
        road_max_km=road_max_km,
        road_ok=road_ok,
        road_km_estimated=road_estimated,
    )
