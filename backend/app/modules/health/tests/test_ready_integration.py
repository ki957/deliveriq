"""Integration tests against the running core stack (`make up`, then `make test-integration`).

They check the real API, PostgreSQL extensions and DB roles. Skipped unless DELIVERIQ_INTEGRATION=1.
"""

from __future__ import annotations

import os

import httpx
import psycopg
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running core stack"),
]

EXPECTED_ROLES = {
    "app_migrator",
    "app_api",
    "p1_sop",
    "p2_elt",
    "p3_synth",
    "rag_customer",
    "rag_kitchen",
    "rag_management",
}


def _api_url() -> str:
    return os.environ.get("INTEGRATION_API_URL", "http://127.0.0.1:8000")


def _connect() -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        dbname=os.environ["POSTGRES_DB"],
        user="app_api",
        password=os.environ["APP_API_PASSWORD"],
        connect_timeout=5,
    )


def test_api_ready_against_real_postgres_and_redis() -> None:
    response = httpx.get(f"{_api_url()}/health/ready", timeout=5)
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}
    assert len(response.headers["X-Request-ID"]) == 32


def test_postgis_and_pgvector_are_installed() -> None:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'vector')"
        ).fetchall()
        assert {row[0] for row in rows} == {"postgis", "vector"}
        # Both extensions actually work, not just registered.
        distance = conn.execute(
            "SELECT ST_Distance('POINT(0 0)'::geometry, 'POINT(3 4)'::geometry)"
        ).fetchone()
        assert distance is not None and distance[0] == 5
        cosine = conn.execute("SELECT '[1,0]'::vector <=> '[0,1]'::vector").fetchone()
        assert cosine is not None and cosine[0] == 1


def test_all_db_roles_exist_without_superuser_rights() -> None:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = ANY(%s)",
            (list(EXPECTED_ROLES),),
        ).fetchall()
    assert {row[0] for row in rows} == EXPECTED_ROLES
    assert all(row[1:] == (False, False, False) for row in rows)


def test_memory_settings_match_ddr_62() -> None:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT name, current_setting(name) FROM pg_settings WHERE name = ANY(%s)",
            (["shared_buffers", "work_mem", "maintenance_work_mem", "max_connections"],),
        ).fetchall()
    settings = {str(name): str(value) for name, value in rows}
    assert settings == {
        "shared_buffers": "256MB",
        "work_mem": "4MB",
        "maintenance_work_mem": "64MB",
        "max_connections": "20",
    }


def test_api_role_cannot_create_objects_in_public() -> None:
    with _connect() as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("CREATE TABLE public.should_fail (id int)")
