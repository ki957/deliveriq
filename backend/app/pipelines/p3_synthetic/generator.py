"""Deterministic, offline TEST event generation; no operational order writes (DDR-118)."""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from app.modules.pricing.domain import bill
from app.pipelines.framework.context import DataError

SEED = 56
VERSION = 1
IST = ZoneInfo("Asia/Kolkata")
NAMESPACE = uuid.UUID("fd6f9aea-2eb9-465f-8637-b15e64c4e028")
OUTCOMES = ("delivered",) * 6 + ("delivery_failed", "rejected", "cancelled", "payment_failed")
DAY_COUNTS = {"demo": (7, 10), "ml": (90, 30)}


@dataclass(frozen=True)
class Event:
    event_id: uuid.UUID
    order_id: uuid.UUID
    kind: str
    when: datetime
    data: dict[str, object]
    region_id: uuid.UUID
    kitchen_id: uuid.UUID
    profile: str


def _id(*parts: object) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, "|".join(map(str, parts)))


def snapshot(conn: Connection) -> dict[str, Any]:
    kitchen = conn.execute(
        text(
            "SELECT k.id, k.code, k.name, k.status, k.region_id, "
            "r.code AS region_code, r.name AS region_name, r.status AS region_status "
            "FROM app.kitchens k JOIN app.regions r ON r.id = k.region_id "
            "WHERE k.code = 'KIT-CHN-001' AND k.status = 'ACTIVE'"
        )
    ).one_or_none()
    if kitchen is None:
        raise DataError("P3 TEST kitchen missing")
    dishes = conn.execute(
        text(
            "SELECT m.id, m.name, m.price_paise, m.publication_status, c.name AS category "
            "FROM app.menu_items m LEFT JOIN app.menu_categories c ON c.id = m.category_id "
            "WHERE m.kitchen_id = :k AND m.is_test_fixture AND m.publication_status = 'PUBLISHED' "
            "AND m.name IN ('TEST – Synthetic Dish A', 'TEST – Synthetic Dish B', 'TEST – Synthetic Dish C') "
            "ORDER BY m.name"
        ),
        {"k": kitchen.id},
    ).all()
    if len(dishes) != 3:
        raise DataError("P3 requires exactly the approved TEST A–C dishes")
    ingredients = conn.execute(
        text(
            "SELECT id, name, unit, origin FROM app.ingredients WHERE origin = 'TEST_FIXTURE' "
            "AND name LIKE 'TEST – Ingredient %' ORDER BY name"
        )
    ).all()
    if len(ingredients) != 6:
        raise DataError("P3 requires exactly the approved TEST ingredients")
    settings: dict[str, str] = dict(
        conn.execute(
            text("SELECT key, value FROM synthetic.pricing_inputs WHERE kitchen_id = :k"), {"k": kitchen.id}
        ).all()
    )
    if set(settings) != {"MINIMUM_FOOD_SUBTOTAL", "DELIVERY_FEE_FLAT"}:
        raise DataError("P3 pricing settings missing")
    return {
        "kitchen_id": str(kitchen.id),
        "region_id": str(kitchen.region_id),
        "kitchen": {"code": kitchen.code, "name": kitchen.name, "status": kitchen.status},
        "region": {"code": kitchen.region_code, "name": kitchen.region_name, "status": kitchen.region_status},
        "dishes": [
            {
                "id": str(d.id),
                "name": d.name,
                "price_paise": d.price_paise,
                "publication_status": d.publication_status,
                "category": d.category,
            }
            for d in dishes
        ],
        "ingredients": {i.name: str(i.id) for i in ingredients},
        "ingredient_details": [
            {"id": str(i.id), "name": i.name, "unit": i.unit, "origin": i.origin} for i in ingredients
        ],
        "minimum_paise": int(settings["MINIMUM_FOOD_SUBTOTAL"]),
        "delivery_fee_paise": int(settings["DELIVERY_FEE_FLAT"]),
        "kitchen_lat": 13.0827,
        "kitchen_lon": 80.2707,
        "address_lat": 13.0835,
        "address_lon": 80.2710,
    }


def generate(profile: str, end: date, reference: dict[str, Any]) -> tuple[list[Event], str]:
    days, daily = DAY_COUNTS[profile]
    rng = random.Random(SEED + (0 if profile == "demo" else 1))  # noqa: S311 - reproducible simulation
    dishes = reference["dishes"]
    if not isinstance(dishes, list):
        raise DataError("P3 manifest dishes malformed")
    region, kitchen = uuid.UUID(str(reference["region_id"])), uuid.UUID(str(reference["kitchen_id"]))
    ingredient_ids = reference["ingredients"]
    if not isinstance(ingredient_ids, dict):
        raise DataError("P3 manifest ingredients malformed")
    result: list[Event] = []
    tracks_assigned = 0
    for day_index in range(days):
        day = end - timedelta(days=days - day_index - 1)
        outcomes = list(OUTCOMES) * (daily // 10)
        rng.shuffle(outcomes)
        for slot, outcome in enumerate(outcomes):
            order = _id(profile, day.isoformat(), slot)
            for _ in range(100):
                chosen = rng.sample(dishes, rng.randint(1, 3))
                items = [
                    {
                        "menu_item_id": d["id"],
                        "quantity": rng.randint(1, 3),
                        "unit_price_paise": d["price_paise"],
                    }
                    for d in chosen
                ]
                subtotal = sum(int(i["quantity"]) * int(i["unit_price_paise"]) for i in items)
                priced = bill(
                    food_subtotal_paise=subtotal,
                    minimum_paise=int(reference["minimum_paise"]),
                    delivery_fee_paise=int(reference["delivery_fee_paise"]),
                    discount_paise=0,
                )
                if priced.minimum_met:
                    break
            else:
                raise DataError("P3 could not draw an eligible TEST cart")
            seconds = rng.randrange(11 * 3600, 21 * 3600)
            placed = datetime.combine(day, time.min, IST) + timedelta(seconds=seconds)
            customer_key = str(_id("customer", slot % 10))
            rider_key = str(_id("rider", slot % 3))

            def add(
                kind: str,
                offset: int,
                data: dict[str, object],
                *,
                current_day: date = day,
                current_slot: int = slot,
                current_order: uuid.UUID = order,
                current_placed: datetime = placed,
            ) -> None:
                result.append(
                    Event(
                        _id(profile, current_day, current_slot, kind),
                        current_order,
                        kind,
                        (current_placed + timedelta(seconds=offset)).astimezone(UTC),
                        data,
                        region,
                        kitchen,
                        profile,
                    )
                )

            add(
                "order.placed",
                0,
                {
                    "order_id": str(order),
                    "customer_key": customer_key,
                    "payment_method": "UPI",
                    "payable_paise": priced.payable_paise,
                    "discount_paise": 0,
                    "lines": len(items),
                    "items": items,
                },
            )
            if outcome == "payment_failed":
                add("payment.failed", 10, {"payment_id": str(_id(order, "payment")), "status": "FAILED"})
                add("order.cancelled", 10, {"cause": "payment_failed"})
                continue
            add(
                "payment.succeeded",
                10,
                {"payment_id": str(_id(order, "payment")), "amount_paise": priced.payable_paise},
            )
            if outcome == "cancelled":
                add("order.cancelled", 30, {"cause": "customer"})
                continue
            if outcome == "rejected":
                add("order.rejected", 60, {"cause": "synthetic_test"})
                continue
            lines = []
            for item in items:
                name = next(d["name"] for d in dishes if d["id"] == item["menu_item_id"])
                number = ord(str(name)[-1]) - ord("A")
                for ingredient in ((1, 2), (3, 4), (5, 6))[number]:
                    lines.append(
                        {
                            "ingredient_id": ingredient_ids[f"TEST – Ingredient {ingredient}"],
                            "quantity": int(item["quantity"]) * 100,
                        }
                    )
            add("order.accepted", 60, {})
            add("inventory.reserved", 60, {"lines": lines})
            add("order.preparing", 61, {})
            add("order.ready_for_pickup", 660, {})
            add("delivery.assigned", 60, {"rider_key": rider_key})
            add("delivery.picked_up", 780, {"rider_key": rider_key})
            add("inventory.consumed", 780, {"lines": lines})
            has_track = profile == "demo" and tracks_assigned < 3 and outcome == "delivered"
            if has_track:
                tracks_assigned += 1
            add(
                "delivery.completed" if outcome == "delivered" else "delivery.failed",
                1080,
                {
                    "rider_key": rider_key,
                    "gps": {
                        "km": 0.1 if has_track else 0,
                        "points": 61 if has_track else 0,
                        "duration_seconds": 300 if has_track else 0,
                        "simulated_points": 61 if has_track else 0,
                    },
                },
            )
    payload = [
        {"id": str(e.event_id), "kind": e.kind, "time": e.when.isoformat(), "data": e.data} for e in result
    ]
    return result, hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def write(conn: Connection, events: list[Event], run_id: uuid.UUID) -> int:
    inserted = 0
    for event in events:
        inserted += conn.execute(
            text(
                "INSERT INTO synthetic.events "
                "(event_id, event_type, event_version, occurred_at, aggregate_type, "
                "aggregate_id, region_id, kitchen_id, idempotency_key, data, generator_seed, "
                "pipeline_run_id, profile) "
                "VALUES (:id, :kind, 1, :at, 'order', :order, :region, :kitchen, :key, CAST(:data AS jsonb), "
                ":seed, :run, :profile) ON CONFLICT (event_id) DO NOTHING"
            ),
            {
                "id": event.event_id,
                "kind": event.kind,
                "at": event.when,
                "order": event.order_id,
                "region": event.region_id,
                "kitchen": event.kitchen_id,
                "key": f"{event.kind}:{event.order_id}",
                "data": json.dumps(event.data, sort_keys=True),
                "seed": SEED,
                "run": run_id,
                "profile": event.profile,
            },
        ).rowcount
    return inserted
