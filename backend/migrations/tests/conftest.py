"""Fixtures for database tests against the migrated core stack (`make up`, `make test-integration`).

Every test runs inside a transaction that is rolled back, so nothing persists. Rows that only the
fixture loader may create (is_test_fixture = true) are inserted as app_migrator, the stand-in for the
local/test-only fixture loader.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg
import pytest

# Imported by each test module (conftest-level pytestmark does not apply to other files).
INTEGRATION = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running core stack"),
]

ROLE_PASSWORD_ENV = {
    "app_migrator": "APP_MIGRATOR_PASSWORD",
    "app_api": "APP_API_PASSWORD",
    "p1_sop": "P1_SOP_PASSWORD",
    "p2_elt": "P2_ELT_PASSWORD",
    "p3_synth": "P3_SYNTH_PASSWORD",
    "rag_customer": "RAG_CUSTOMER_PASSWORD",
    "rag_kitchen": "RAG_KITCHEN_PASSWORD",
    "rag_management": "RAG_MANAGEMENT_PASSWORD",
}

Conn = psycopg.Connection[tuple[object, ...]]


def connect(role: str) -> Conn:
    return psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        dbname=os.environ["POSTGRES_DB"],
        user=role,
        password=os.environ[ROLE_PASSWORD_ENV[role]],
        connect_timeout=5,
    )


@contextmanager
def rolled_back(role: str) -> Iterator[Conn]:
    """A connection whose transaction is always rolled back."""
    conn = connect(role)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


def act_as(conn: Conn, role: str, user_id: uuid.UUID | None = None, reason: str | None = None) -> None:
    """Set the transaction-local actor context the status triggers require."""
    conn.execute("SELECT set_config('app.actor_role', %s, true)", (role,))
    conn.execute("SELECT set_config('app.actor_user_id', %s, true)", (str(user_id) if user_id else "",))
    conn.execute("SELECT set_config('app.reason', %s, true)", (reason or "",))


def one(conn: Conn, sql: str, params: tuple[object, ...] = ()) -> object:
    row = conn.execute(sql, params).fetchone()
    assert row is not None
    return row[0]


@dataclass(frozen=True)
class Ids:
    kitchen: uuid.UUID
    region: uuid.UUID


@pytest.fixture
def migrator() -> Iterator[Conn]:
    with rolled_back("app_migrator") as conn:
        yield conn


@pytest.fixture
def api() -> Iterator[Conn]:
    with rolled_back("app_api") as conn:
        yield conn


@pytest.fixture
def role_conn() -> Callable[[str], Conn]:
    opened: list[Conn] = []

    def _open(role: str) -> Conn:
        conn = connect(role)
        opened.append(conn)
        return conn

    yield _open  # type: ignore[misc]
    for conn in opened:
        conn.rollback()
        conn.close()


def seed_ids(conn: Conn) -> Ids:
    row = conn.execute("SELECT id, region_id FROM app.kitchens WHERE code = 'KIT-CHN-001'").fetchone()
    assert row is not None
    return Ids(kitchen=row[0], region=row[1])  # type: ignore[arg-type]


def make_user(conn: Conn, name: str, role: str | None = None) -> uuid.UUID:
    """Create a throwaway user (and optional role grant) inside the current transaction."""
    ids = seed_ids(conn)
    mobile = "+9100000" + str(uuid.uuid4().int)[:7]
    user_id = one(
        conn, "INSERT INTO app.users (display_name, mobile_e164) VALUES (%s, %s) RETURNING id", (name, mobile)
    )
    if role is not None:
        region = None if role in ("CUSTOMER", "CENTRAL_ADMIN") else ids.region
        kitchen = ids.kitchen if role in ("KITCHEN_STAFF", "KITCHEN_MANAGER") else None
        conn.execute(
            "INSERT INTO app.role_assignments (user_id, role, region_id, kitchen_id) VALUES (%s, %s, %s, %s)",
            (user_id, role, region, kitchen),
        )
    return user_id  # type: ignore[return-value]


def make_test_recipe_version(conn: Conn, status: str = "DRAFT", *, fixture: bool = True) -> uuid.UUID:
    """A TEST recipe (fixture) or a lineage-bearing SOP-style recipe, inserted as SYSTEM."""
    ids = seed_ids(conn)
    act_as(conn, "SYSTEM")
    recipe_id = one(
        conn,
        "INSERT INTO app.recipes (kitchen_id, name) VALUES (%s, %s) RETURNING id",
        (ids.kitchen, "TEST – Recipe " + uuid.uuid4().hex[:6] if fixture else "Sample real recipe"),
    )
    return one(  # type: ignore[return-value]
        conn,
        """INSERT INTO app.recipe_versions (recipe_id, version, status, is_test_fixture, source_sha256)
           VALUES (%s, 1, %s, %s, %s) RETURNING id""",
        (recipe_id, status, fixture, None if fixture else "0" * 64),
    )


def sign_all(conn: Conn, version_id: uuid.UUID, signer: uuid.UUID) -> None:
    for kind in ("CHEF", "FOOD_SAFETY_LEAD", "INVENTORY_OWNER", "KITCHEN_MANAGER", "PRODUCT_OWNER"):
        conn.execute(
            "INSERT INTO app.recipe_signoffs (recipe_version_id, signoff_type, signed_by) VALUES (%s, %s, %s)",
            (version_id, kind, signer),
        )


def walk_recipe_to(conn: Conn, version_id: uuid.UUID, target: str, actor: uuid.UUID, km: uuid.UUID) -> None:
    """Move a recipe version along DRAFT → PENDING_VALIDATION → VALIDATED [→ ACTIVE]."""
    path = ["PENDING_VALIDATION", "VALIDATED", "ACTIVE"]
    for status in path[: path.index(target) + 1]:
        if status == "ACTIVE":
            sign_all(conn, version_id, km)
            act_as(conn, "KITCHEN_MANAGER", km, reason="all sign-offs recorded")
        else:
            act_as(conn, "KITCHEN_MANAGER", actor, reason=f"move to {status}")
        conn.execute("UPDATE app.recipe_versions SET status = %s WHERE id = %s", (status, version_id))
