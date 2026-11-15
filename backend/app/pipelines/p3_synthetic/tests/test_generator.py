"""P3 reproducibility and exact approved profile sizes (DDR-118)."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date
from typing import Any, cast

import pytest

from app.pipelines.p3_synthetic import generator as g

pytestmark = pytest.mark.unit


def reference() -> dict[str, Any]:
    return {
        "kitchen_id": str(uuid.uuid5(g.NAMESPACE, "kitchen")),
        "region_id": str(uuid.uuid5(g.NAMESPACE, "region")),
        "dishes": [
            {
                "id": str(uuid.uuid5(g.NAMESPACE, name)),
                "name": f"TEST – Synthetic Dish {name}",
                "price_paise": price,
            }
            for name, price in (("A", 11100), ("B", 22200), ("C", 33300))
        ],
        "ingredients": {f"TEST – Ingredient {i}": str(uuid.uuid5(g.NAMESPACE, str(i))) for i in range(1, 7)},
        "minimum_paise": 50000,
        "delivery_fee_paise": 3000,
        "kitchen_lat": 13.0827,
        "kitchen_lon": 80.2707,
        "address_lat": 13.0835,
        "address_lon": 80.2710,
    }


@pytest.mark.parametrize(("profile", "days", "daily"), [("demo", 7, 10), ("ml", 90, 30)])
def test_profile_counts_and_orders_per_day(profile: str, days: int, daily: int) -> None:
    events, _ = g.generate(profile, date(2026, 11, 13), reference())
    placed = [e for e in events if e.kind == "order.placed"]
    counts = Counter(e.when.astimezone(g.IST).date() for e in placed)
    assert len(placed) == days * daily
    assert len(counts) == days and set(counts.values()) == {daily}
    assert all(
        str(i["menu_item_id"]) in {d["id"] for d in reference()["dishes"]}
        for e in placed
        for i in cast(list[dict[str, Any]], e.data["items"])
    )


def test_fixed_inputs_are_deterministic_and_outcomes_are_balanced() -> None:
    first, digest = g.generate("demo", date(2026, 11, 13), reference())
    again, same_digest = g.generate("demo", date(2026, 11, 13), reference())
    assert first == again and digest == same_digest
    assert len({e.event_id for e in first}) == len(first)
    outcomes = Counter(e.kind for e in first)
    assert outcomes["delivery.completed"] == 42
    assert outcomes["delivery.failed"] == 7
    assert outcomes["order.rejected"] == 7
