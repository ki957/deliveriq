"""Schemas, seeds and fixture-flag presence after `alembic upgrade head`."""

from __future__ import annotations

from .conftest import INTEGRATION, Conn, one

pytestmark = INTEGRATION

SCHEMAS = {
    "app",
    "raw",
    "staging",
    "analytics",
    "synthetic",
    "analytics_synthetic",
    "ops",
    "audit",
    "customer_rag",
    "kitchen_rag",
    "management_rag",
}
FIXTURE_TABLES = ("menu_items", "recipe_versions", "orders", "order_items", "payments")
EXPECTED_CONFIG = {
    "SERVICEABILITY_STRAIGHT_LINE_MAX": ("4", "km"),
    "SERVICEABILITY_ROAD_DISTANCE_MAX": ("6", "km"),
    "MINIMUM_FOOD_SUBTOTAL": ("50000", "paise"),
    "DELIVERY_FEE_FLAT": ("3000", "paise"),
    "MAX_CONCURRENT_ORDERS": ("10", "orders"),
    "CUSTOMER_UNAVAILABLE_WAIT": ("5", "minutes"),
    "AGENT_ASSIGNMENT_RESPONSE_TIMEOUT": ("60", "seconds"),
    "GPS_UPDATE_INTERVAL_MIN": ("3", "seconds"),
    "GPS_UPDATE_INTERVAL_MAX": ("5", "seconds"),
    "SPECIAL_INSTRUCTIONS_MAX_CHARS": ("250", "characters"),
    "GPS_RETENTION_DAYS": ("30", "days"),
    "PRICE_PROTECTION_MINUTES": ("30", "minutes"),
}


def test_all_approved_schemas_exist(api: Conn) -> None:
    rows = api.execute("SELECT nspname FROM pg_namespace").fetchall()
    assert {r[0] for r in rows} >= SCHEMAS


def test_migrations_at_head(migrator: Conn) -> None:
    assert one(migrator, "SELECT version_num FROM public.alembic_version") == "0009"


def test_is_test_fixture_on_all_five_tables(api: Conn) -> None:
    rows = api.execute(
        """SELECT table_name, is_nullable, column_default FROM information_schema.columns
           WHERE table_schema = 'app' AND column_name = 'is_test_fixture'"""
    ).fetchall()
    found = {r[0]: (r[1], r[2]) for r in rows}
    for table in FIXTURE_TABLES:
        assert found[table] == ("NO", "false"), table


def test_seeded_region_and_synthetic_kitchen(api: Conn) -> None:
    region = api.execute(
        "SELECT name, timezone, status FROM app.regions WHERE code = 'REG-CHN-001'"
    ).fetchone()
    assert region == ("Chennai", "Asia/Kolkata", "ACTIVE")
    kitchen = api.execute(
        """SELECT k.location_is_synthetic, k.mode, r.code,
                  round(ST_Y(k.location::geometry)::numeric, 4), round(ST_X(k.location::geometry)::numeric, 4)
           FROM app.kitchens k JOIN app.regions r ON r.id = k.region_id WHERE k.code = 'KIT-CHN-001'"""
    ).fetchone()
    assert kitchen is not None
    assert kitchen[:3] == (True, "NORMAL", "REG-CHN-001")
    assert (str(kitchen[3]), str(kitchen[4])) == ("13.0827", "80.2707")


def test_config_seeds_match_sources(api: Conn) -> None:
    rows = api.execute("SELECT key, value::text, unit, is_test_default FROM app.config_settings").fetchall()
    seeded = {r[0]: (r[1], r[2]) for r in rows}
    assert seeded == EXPECTED_CONFIG
    test_defaults = {r[0] for r in rows if r[3]}
    assert test_defaults == {"MAX_CONCURRENT_ORDERS"}


def test_no_free_delivery_threshold_setting(api: Conn) -> None:
    assert one(api, "SELECT count(*) FROM app.config_settings WHERE key ILIKE %s", ("%FREE%",)) == 0


def test_pipeline_registry(api: Conn) -> None:
    rows = api.execute("SELECT name, pipeline_group, db_role FROM ops.pipelines ORDER BY name").fetchall()
    assert rows == [
        ("k1_customer", "KNOWLEDGE", "rag_customer"),
        ("k2_kitchen", "KNOWLEDGE", "rag_kitchen"),
        ("k3_management", "KNOWLEDGE", "rag_management"),
        ("p1_sop", "DATA", "p1_sop"),
        ("p2_elt", "DATA", "p2_elt"),
        ("p3_synthetic", "DATA", "p3_synth"),
    ]
