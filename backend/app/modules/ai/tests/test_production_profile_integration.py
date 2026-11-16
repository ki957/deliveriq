"""Production-profile fixture isolation against a migrated Compose database."""

from __future__ import annotations

import hashlib
import os
import uuid
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import URL, create_engine
from sqlalchemy.pool import NullPool

from app.core.permissions import Grant, Principal, Role
from app.modules.ai import kitchen_rag
from app.modules.identity.tests.test_auth_integration import API, World
from app.shared.fixture_guard import fixture_counts

pytest_plugins = ("app.modules.identity.tests.test_auth_integration",)
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("DELIVERIQ_INTEGRATION") != "1", reason="needs the running stack"),
]


def test_production_profile_serves_no_fixtures_and_kitchen_rag_hides_test_chunks(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production starts clean, public menu is empty of TEST rows, and RAG excludes a canary."""
    url = URL.create(
        "postgresql+psycopg",
        username="app_api",
        password=os.environ["APP_API_PASSWORD"],
        host="127.0.0.1",
        port=int(os.environ.get("INTEGRATION_DB_PORT", "5433")),
        database=os.environ["POSTGRES_DB"],
    )
    engine = create_engine(url, poolclass=NullPool)
    if os.environ.get("DELIVERIQ_PRODUCTION_PROFILE") == "1":
        assert os.environ.get("APP_ENV") == "production"
        with engine.connect() as conn:
            counts = fixture_counts(conn)
            assert not {table: count for table, count in counts.items() if count}

        response = httpx.get(f"{API}/api/v1/menu/items", timeout=10)
        assert response.status_code == 200
        assert all(not item["name"].startswith("TEST ") for item in response.json())
        assert all(not item["name"].startswith("TEST –") for item in response.json())

    doc_id = f"TEST-PRODUCTION-{uuid.uuid4().hex}"
    canary = f"production profile fixture canary {uuid.uuid4().hex}"
    digest = hashlib.sha256(canary.encode()).hexdigest()
    world.db.execute(
        """INSERT INTO kitchen_rag.chunks
           (kitchen_id, doc_id, doc_version, section_path, source_ref, audience, visibility,
            status, is_test_fixture, content, content_sha256)
           VALUES (%s, %s, 1, 'production-check', 'Task 22 production-profile check',
                   'KITCHEN', 'ALL', 'PUBLISHED', true, %s, %s)""",
        (world.kitchen_a, doc_id, canary, digest),
    )

    monkeypatch.setattr(kitchen_rag, "get_engine", lambda: engine)
    monkeypatch.setattr(kitchen_rag, "get_settings", lambda: SimpleNamespace(app_env="production"))
    principal = Principal(uuid.uuid4(), (Grant(role=Role.KITCHEN_STAFF, kitchen_id=world.kitchen_a),))
    try:
        evidence = kitchen_rag.retrieve(canary, principal)
        assert all(canary not in chunk.content for chunk in evidence)
        assert not any(chunk.source_ref == "Task 22 production-profile check" for chunk in evidence)
    finally:
        world.db.execute("DELETE FROM kitchen_rag.chunks WHERE doc_id = %s", (doc_id,))
        engine.dispose()
