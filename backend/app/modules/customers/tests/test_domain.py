"""Serviceability (CU-03): both rules required; road distance through the adapter (DDR-55, DDR-110)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.customers.domain import evaluate
from app.shared import geo

pytestmark = pytest.mark.unit
D = Decimal


@pytest.mark.parametrize(
    ("straight", "road", "serviceable", "straight_ok", "road_ok"),
    [
        ("4.00", "6.00", True, True, True),  # both limits inclusive
        ("4.01", "5.00", False, False, True),  # straight-line fails alone
        ("3.50", "6.01", False, True, False),  # road fails alone (fixed stub value, DDR-110 (6))
        ("4.50", "7.00", False, False, False),
    ],
)
def test_both_rules_must_pass(
    straight: str, road: str, serviceable: bool, straight_ok: bool, road_ok: bool
) -> None:
    s = evaluate(D(straight), D(road), road_estimated=True, straight_line_max_km=D(4), road_max_km=D(6))
    assert (s.serviceable, s.straight_line_ok, s.road_ok, s.road_km_estimated) == (
        serviceable,
        straight_ok,
        road_ok,
        True,
    )


def test_stub_road_distance_is_labelled_an_estimate() -> None:
    r = geo.StubRoadDistance().road_distance(geo.Point(13.0827, 80.2707), geo.Point(13.1, 80.3), D("3.00"))
    assert (r.km, r.estimated) == (D("4.20"), True)
    assert isinstance(geo.road_adapter(), geo.StubRoadDistance)  # OSRM arrives with Task 9
