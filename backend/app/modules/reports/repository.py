"""Report reads on the analytics marts and dimensions (DDR-117 (6)). The API role can read nothing else there.

The schema name always comes from `domain.DATASETS` (a fixed whitelist), never from the request text.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Connection, text

from app.modules.reports.domain import DATASETS, Totals


@dataclass(frozen=True)
class KitchenRef:
    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class DailyRow:
    day: date
    orders_placed: int
    orders_delivered: int
    payable_paise: int
    discount_paise: int


@dataclass(frozen=True)
class IngredientRow:
    ingredient_id: uuid.UUID
    name: str
    unit: str
    consumed_quantity: Decimal


def _schema(dataset: str) -> str:
    if dataset not in DATASETS:  # pragma: no cover - the service validates first
        raise ValueError(dataset)
    return dataset


def kitchens(conn: Connection, regions: list[uuid.UUID] | None) -> list[KitchenRef]:
    rows = conn.execute(
        text(
            "SELECT id, name FROM app.kitchens WHERE status = 'ACTIVE' "
            "AND (CAST(:all AS boolean) OR region_id = ANY(:r)) ORDER BY name"
        ),
        {"all": regions is None, "r": regions or []},
    ).all()
    return [KitchenRef(*r) for r in rows]


def built(conn: Connection, dataset: str) -> bool:
    found = conn.execute(
        text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"{_schema(dataset)}.mart_daily_sales"}
    ).scalar_one()
    return bool(found)


def freshness(conn: Connection, dataset: str) -> datetime | None:
    value: datetime | None = conn.execute(
        text("SELECT fresh_as_of FROM ops.dataset_freshness WHERE dataset = :d"), {"d": dataset}
    ).scalar_one_or_none()
    return value


def totals(conn: Connection, dataset: str, kitchen_ids: list[uuid.UUID], start: date, end: date) -> Totals:
    s = _schema(dataset)
    p = {"k": kitchen_ids, "s": start, "e": end}

    def one(sql: str) -> tuple[object, ...]:
        row = conn.execute(text(sql), p).one()
        return tuple(row)

    sales = one(
        "SELECT coalesce(sum(orders_placed), 0), coalesce(sum(orders_delivered), 0), "  # noqa: S608 - whitelisted schema, values bound
        "coalesce(sum(orders_rejected_or_cancelled), 0), coalesce(sum(payable_paise), 0), "
        "coalesce(sum(discount_paise), 0), coalesce(sum(delivered_payable_paise), 0) "
        f"FROM {s}.mart_daily_sales WHERE kitchen_id = ANY(:k) AND sales_date BETWEEN :s AND :e"
    )
    (gross,) = one(
        f"SELECT coalesce(sum(line_paise), 0) FROM {s}.mart_menu_performance "  # noqa: S608 - whitelisted schema, values bound
        "WHERE kitchen_id = ANY(:k) AND sales_date BETWEEN :s AND :e"
    )
    kitchen = one(
        "SELECT coalesce(sum(orders_accepted), 0), coalesce(sum(orders_rejected), 0), "  # noqa: S608 - whitelisted schema, values bound
        "coalesce(sum(orders_decided), 0), coalesce(sum(orders_ready), 0), "
        "coalesce(sum(accept_seconds_total), 0), coalesce(sum(prepare_seconds_total), 0) "
        f"FROM {s}.mart_kitchen_performance WHERE kitchen_id = ANY(:k) AND service_date BETWEEN :s AND :e"
    )
    delivery = one(
        "SELECT coalesce(sum(deliveries_completed), 0), coalesce(sum(deliveries_failed), 0), "  # noqa: S608 - whitelisted schema, values bound
        "coalesce(sum(delivery_seconds_total), 0) "
        f"FROM {s}.mart_delivery_performance WHERE kitchen_id = ANY(:k) AND delivery_date BETWEEN :s AND :e"
    )
    payment = one(
        "SELECT coalesce(sum(payments_succeeded), 0), coalesce(sum(payments_failed), 0) "  # noqa: S608 - whitelisted schema, values bound
        f"FROM {s}.mart_payment_performance WHERE kitchen_id = ANY(:k) AND payment_date BETWEEN :s AND :e"
    )
    ints = [int(str(v)) for v in (*sales, gross, *kitchen[:4], *delivery[:2], *payment)]
    floats = [float(str(v)) for v in (kitchen[4], kitchen[5], delivery[2])]
    return Totals(
        orders_placed=ints[0],
        orders_delivered=ints[1],
        orders_rejected_or_cancelled=ints[2],
        payable_paise=ints[3],
        discount_paise=ints[4],
        delivered_payable_paise=ints[5],
        gross_food_sales=ints[6],
        orders_accepted=ints[7],
        orders_rejected=ints[8],
        orders_decided=ints[9],
        orders_ready=ints[10],
        accept_seconds_total=floats[0],
        prepare_seconds_total=floats[1],
        deliveries_completed=ints[11],
        deliveries_failed=ints[12],
        delivery_seconds_total=floats[2],
        payments_succeeded=ints[13],
        payments_failed=ints[14],
    )


def daily(
    conn: Connection, dataset: str, kitchen_ids: list[uuid.UUID], start: date, end: date
) -> list[DailyRow]:
    rows = conn.execute(
        text(
            "SELECT d.day::date, coalesce(sum(m.orders_placed), 0), coalesce(sum(m.orders_delivered), 0), "  # noqa: S608 - whitelisted schema, values bound
            "coalesce(sum(m.payable_paise), 0), coalesce(sum(m.discount_paise), 0) "
            "FROM generate_series(CAST(:s AS date), CAST(:e AS date), interval '1 day') AS d(day) "
            f"LEFT JOIN {_schema(dataset)}.mart_daily_sales m "
            "ON m.sales_date = d.day::date AND m.kitchen_id = ANY(:k) "
            "GROUP BY d.day ORDER BY d.day"
        ),
        {"k": kitchen_ids, "s": start, "e": end},
    ).all()
    return [DailyRow(r[0], int(r[1]), int(r[2]), int(r[3]), int(r[4])) for r in rows]


def ingredients(
    conn: Connection, dataset: str, kitchen_ids: list[uuid.UUID], start: date, end: date
) -> list[IngredientRow]:
    s = _schema(dataset)
    rows = conn.execute(
        text(
            "SELECT m.ingredient_id, coalesce(i.name, 'Unknown ingredient'), coalesce(i.unit, ''), "  # noqa: S608 - whitelisted schema, values bound
            "sum(coalesce(m.consumed_quantity, 0)) "
            f"FROM {s}.mart_inventory_consumption m LEFT JOIN {s}.dim_ingredient i USING (ingredient_id) "
            "WHERE m.kitchen_id = ANY(:k) AND m.movement_date BETWEEN :s AND :e "
            "GROUP BY m.ingredient_id, i.name, i.unit HAVING sum(coalesce(m.consumed_quantity, 0)) > 0 "
            "ORDER BY 4 DESC, 2 LIMIT 20"
        ),
        {"k": kitchen_ids, "s": start, "e": end},
    ).all()
    return [IngredientRow(r[0], r[1], r[2], Decimal(r[3])) for r in rows]
