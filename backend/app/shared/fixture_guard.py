"""Production startup check: refuse to start if any TEST fixture row exists (plan §5.2 control 3, DDR-106)."""

from __future__ import annotations

from sqlalchemy import Connection, text

FIXTURE_TABLES = (
    "menu_items",
    "recipe_versions",
    "orders",
    "order_items",
    "payments",
    "coupons",
    # TEST opening stock and everything derived from it (DDR-37, DDR-111 (8)).
    "ingredient_stock",
    "stock_reservations",
    "stock_movements",
    # Requests about TEST dishes (DDR-111 (7)).
    "dish_availability_requests",
    # Delivery codes and GPS points of TEST orders (DDR-113).
    "delivery_otps",
    "delivery_locations",
)


class FixtureRowsPresent(RuntimeError):
    """Raised at startup in production; names tables and counts only, never row content."""


def fixture_counts(conn: Connection) -> dict[str, int]:
    counts = {
        table: int(
            conn.execute(
                text(f"SELECT count(*) FROM app.{table} WHERE is_test_fixture")  # noqa: S608 - fixed names
            ).scalar_one()
        )
        for table in FIXTURE_TABLES
    }
    counts["ingredients"] = int(
        conn.execute(text("SELECT count(*) FROM app.ingredients WHERE origin = 'TEST_FIXTURE'")).scalar_one()
    )
    return counts


def assert_no_fixtures(conn: Connection) -> None:
    present = {table: n for table, n in fixture_counts(conn).items() if n}
    if present:
        detail = ", ".join(f"{table}={n}" for table, n in sorted(present.items()))
        raise FixtureRowsPresent(f"Refusing to start in production: TEST fixture rows present ({detail})")
