"""Least-privilege grants: fixture flags, append-only tables and per-pipeline write scopes."""

from __future__ import annotations

from collections.abc import Callable

import psycopg
import pytest

from .conftest import INTEGRATION, Conn, act_as, make_test_recipe_version, make_user, one, seed_ids

pytestmark = INTEGRATION

FIXTURE_TABLES = ("menu_items", "recipe_versions", "orders", "order_items", "payments")
RUNTIME_ROLES = ("app_api", "p1_sop", "p2_elt", "p3_synth", "rag_customer", "rag_kitchen", "rag_management")

# Tables each role must NOT be able to INSERT into (its non-targets).
FORBIDDEN_INSERTS = {
    "app_api": ["raw.events", "synthetic.events", "app.status_history", "audit.menu_publications"],
    "p1_sop": [
        "raw.events",
        "synthetic.events",
        "app.orders",
        "app.menu_items",
        "audit.events",
        "app.outbox",
    ],
    "p2_elt": ["app.recipes", "app.orders", "synthetic.events", "app.outbox", "audit.events"],
    "p3_synth": ["raw.events", "app.orders", "app.menu_items", "app.recipes", "audit.events"],
    "rag_customer": ["app.orders", "raw.events", "synthetic.events", "app.recipes"],
    "rag_kitchen": ["app.orders", "raw.events", "synthetic.events", "app.recipes"],
    "rag_management": ["app.orders", "raw.events", "synthetic.events", "app.recipes"],
}
ALLOWED_INSERTS = {
    "p1_sop": ["app.recipes", "app.ingredients", "app.recipe_ingredients", "ops.source_registry"],
    "p2_elt": ["raw.events"],
    "p3_synth": ["synthetic.events"],
}
RAG_SCHEMAS = {
    "rag_customer": "customer_rag",
    "rag_kitchen": "kitchen_rag",
    "rag_management": "management_rag",
}


def _has(conn: Conn, role: str, table: str, privilege: str) -> bool:
    return bool(one(conn, "SELECT has_table_privilege(%s, %s, %s)", (role, table, privilege)))


@pytest.mark.parametrize("table", FIXTURE_TABLES)
@pytest.mark.parametrize("role", RUNTIME_ROLES)
def test_no_runtime_role_can_write_is_test_fixture(migrator: Conn, role: str, table: str) -> None:
    for privilege in ("INSERT", "UPDATE"):
        allowed = one(
            migrator,
            "SELECT has_column_privilege(%s, %s, 'is_test_fixture', %s)",
            (role, f"app.{table}", privilege),
        )
        assert allowed is False, f"{role} has {privilege} on app.{table}.is_test_fixture"


def test_api_update_of_fixture_flag_is_denied(migrator: Conn, api: Conn) -> None:
    del migrator
    act_as(api, "SYSTEM")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        api.execute("UPDATE app.orders SET is_test_fixture = true WHERE false")


def test_api_can_insert_ordinary_rows(api: Conn) -> None:
    user = make_user(api, "Grant check customer", "CUSTOMER")
    ids = seed_ids(api)
    act_as(api, "CUSTOMER", user)
    order = one(
        api,
        """INSERT INTO app.orders (customer_user_id, kitchen_id, region_id, fulfilment_status)
           VALUES (%s, %s, %s, 'PLACED') RETURNING is_test_fixture""",
        (user, ids.kitchen, ids.region),
    )
    assert order is False


@pytest.mark.parametrize(("role", "tables"), sorted(FORBIDDEN_INSERTS.items()))
def test_roles_cannot_write_outside_their_targets(migrator: Conn, role: str, tables: list[str]) -> None:
    for table in tables:
        assert not _has(migrator, role, table, "INSERT"), f"{role} can INSERT into {table}"


@pytest.mark.parametrize(("role", "tables"), sorted(ALLOWED_INSERTS.items()))
def test_pipeline_roles_can_write_their_targets(migrator: Conn, role: str, tables: list[str]) -> None:
    for table in tables:
        assert _has(migrator, role, table, "INSERT"), f"{role} cannot INSERT into {table}"


def test_p1_cannot_create_fixture_or_active_recipes(role_conn: Callable[[str], Conn]) -> None:
    p1 = role_conn("p1_sop")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        p1.execute(
            "INSERT INTO app.recipe_versions (recipe_id, version, status, is_test_fixture) "
            "VALUES (gen_random_uuid(), 1, 'DRAFT', true)"
        )


@pytest.mark.parametrize("role", sorted(RAG_SCHEMAS))
def test_rag_roles_reach_only_their_own_schema(migrator: Conn, role: str) -> None:
    for other_role, schema in RAG_SCHEMAS.items():
        usage = one(migrator, "SELECT has_schema_privilege(%s, %s, 'USAGE')", (role, schema))
        assert usage is (other_role == role), f"{role} USAGE on {schema}"
    assert one(migrator, "SELECT has_schema_privilege('app_api', 'kitchen_rag', 'USAGE')") is False


def test_future_rag_tables_are_granted_to_their_role_only(migrator: Conn) -> None:
    migrator.execute("CREATE TABLE kitchen_rag.grant_probe (id int)")
    assert _has(migrator, "rag_kitchen", "kitchen_rag.grant_probe", "INSERT")
    assert not _has(migrator, "rag_customer", "kitchen_rag.grant_probe", "SELECT")
    assert not _has(migrator, "app_api", "kitchen_rag.grant_probe", "SELECT")


def _make_row(conn: Conn, table: str) -> None:
    """Create at least one real row in an append-only table."""
    if table == "audit.events":
        conn.execute(
            "INSERT INTO audit.events (actor_role, action, target_type, outcome) "
            "VALUES ('SYSTEM', 'probe', 'probe', 'SUCCESS')"
        )
    elif table == "raw.events":
        conn.execute(
            """INSERT INTO raw.events (event_id, event_type, event_version, occurred_at, aggregate_type,
                                       aggregate_id, idempotency_key, is_test_fixture)
               VALUES (gen_random_uuid(), 'order.placed', 1, now(), 'order', gen_random_uuid(), 'probe', true)"""
        )
    elif table == "app.status_history":
        make_test_recipe_version(conn)  # the transition trigger writes a history row
    elif table == "audit.menu_publications":
        version = make_test_recipe_version(conn)
        recipe = one(conn, "SELECT recipe_id FROM app.recipe_versions WHERE id = %s", (version,))
        conn.execute(
            """INSERT INTO app.menu_items (kitchen_id, recipe_id, name, publication_status, is_test_fixture)
               VALUES (%s, %s, 'TEST – Audit probe', 'DRAFT', true)""",
            (seed_ids(conn).kitchen, recipe),
        )


APPEND_ONLY = {
    "audit.events": "action = 'changed'",
    "audit.menu_publications": "reason = 'changed'",
    "app.status_history": "reason = 'changed'",
    "raw.events": "parse_error = 'changed'",
    "app.recipe_signoffs": "note = 'changed'",
}


@pytest.mark.parametrize("table", sorted(set(APPEND_ONLY) - {"app.recipe_signoffs"}))
def test_append_only_tables_reject_update_and_delete(migrator: Conn, table: str) -> None:
    # Enforced by trigger, so even the owner cannot rewrite history; corrections are new rows.
    _make_row(migrator, table)
    assert one(migrator, f"SELECT count(*) FROM {table}") > 0
    for statement in (f"UPDATE {table} SET {APPEND_ONLY[table]}", f"DELETE FROM {table}"):
        migrator.execute("SAVEPOINT probe")
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="append-only"):
            migrator.execute(statement)
        migrator.execute("ROLLBACK TO SAVEPOINT probe")


def test_api_cannot_forge_status_history(api: Conn) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        api.execute(
            "INSERT INTO app.status_history (machine, entity_id, to_status, actor_role) "
            "VALUES ('fulfilment', gen_random_uuid(), 'DELIVERED', 'SYSTEM')"
        )


def test_signoffs_need_a_real_version(migrator: Conn) -> None:
    version = make_test_recipe_version(migrator)
    signer = make_user(migrator, "Signer", "KITCHEN_MANAGER")
    migrator.execute(
        "INSERT INTO app.recipe_signoffs (recipe_version_id, signoff_type, signed_by) VALUES (%s, 'CHEF', %s)",
        (version, signer),
    )
    migrator.execute("SAVEPOINT dup")
    with pytest.raises(psycopg.errors.UniqueViolation):
        migrator.execute(
            "INSERT INTO app.recipe_signoffs (recipe_version_id, signoff_type, signed_by) VALUES (%s, 'CHEF', %s)",
            (version, signer),
        )
    migrator.execute("ROLLBACK TO SAVEPOINT dup")
    # Sign-offs are append-only too.
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="append-only"):
        migrator.execute(f"UPDATE app.recipe_signoffs SET {APPEND_ONLY['app.recipe_signoffs']}")
