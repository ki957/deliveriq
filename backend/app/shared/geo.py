"""Road-distance adapter (DDR-55, DDR-110).

Straight-line distance is computed by PostGIS. Road distance goes through this adapter: the labelled
stub (straight-line times 1.4, always marked estimated) is used until the optional OSRM adapter is added
with the `osrm` profile in Task 9. Callers must show "road distance: estimated" when `estimated` is
true (DOCKER_DEPLOYMENT_DESIGN §15).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

STUB_ROAD_FACTOR = Decimal("1.4")  # DDR-110 (6); not a measured value
_KM = Decimal("0.01")


@dataclass(frozen=True)
class Point:
    lat: float
    lng: float


@dataclass(frozen=True)
class RoadDistance:
    km: Decimal
    estimated: bool


class RoadDistanceAdapter(Protocol):
    def road_distance(self, origin: Point, destination: Point, straight_line_km: Decimal) -> RoadDistance: ...


class StubRoadDistance:
    """Labelled estimate: never presented as a measured road distance."""

    def road_distance(self, origin: Point, destination: Point, straight_line_km: Decimal) -> RoadDistance:
        return RoadDistance((straight_line_km * STUB_ROAD_FACTOR).quantize(_KM, rounding=ROUND_HALF_UP), True)


_adapter: RoadDistanceAdapter = StubRoadDistance()


def road_adapter() -> RoadDistanceAdapter:
    return _adapter


def km(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(_KM, rounding=ROUND_HALF_UP)
