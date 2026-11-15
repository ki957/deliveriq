from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.ai.embedder import MockEmbedder
from app.core.permissions import Grant, Principal, Role
from app.modules.ai import kitchen_copilot, kitchen_rag
from app.modules.pipelines.service import DEFAULT_INPUT, TRIGGERABLE
from app.pipelines.framework.context import RunContext
from app.pipelines.k2_kitchen import pipeline as k2

KITCHEN = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def principal(role: Role, kitchen_id: uuid.UUID | None = KITCHEN) -> Principal:
    return Principal(uuid.uuid4(), (Grant(role=role, kitchen_id=kitchen_id),))


def test_other_portals_are_denied_before_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fail(*_args: object, **_kwargs: object) -> list[object]:
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(kitchen_copilot, "retrieve", fail)
    with pytest.raises(kitchen_copilot.Forbidden):
        kitchen_copilot.ask(principal(Role.CUSTOMER), "What is the prep method?")
    assert not called


def test_missing_exact_recipe_pin_abstains_for_order_question(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kitchen_copilot, "retrieve", lambda *_args: [])
    answer, citations = kitchen_copilot.ask(
        principal(Role.KITCHEN_STAFF), "What is the recipe for this order?"
    )
    assert "exact recipe version" in answer
    assert citations == []


def test_cooking_time_abstains_when_source_does_not_give_one(monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = [kitchen_rag.Evidence("c1", "Method: mix ingredients.", "#12 §4", None)]
    monkeypatch.setattr(kitchen_copilot, "retrieve", lambda *_args: evidence)
    answer, citations = kitchen_copilot.ask(principal(Role.KITCHEN_STAFF), "How long should I cook this?")
    assert "does not specify" in answer
    assert citations == []


@pytest.mark.parametrize(
    ("question", "source"),
    [
        ("How long should I cook this?", "Cook at 180°C."),
        ("What temperature should I use?", "Cook for 20 minutes."),
    ],
)
def test_cooking_value_guard_requires_the_requested_kind(
    monkeypatch: pytest.MonkeyPatch, question: str, source: str
) -> None:
    evidence = [kitchen_rag.Evidence("c1", source, "#12 §4", None)]
    monkeypatch.setattr(kitchen_copilot, "retrieve", lambda *_args: evidence)
    answer, citations = kitchen_copilot.ask(principal(Role.KITCHEN_STAFF), question)
    assert "does not specify" in answer
    assert citations == []


def test_mixed_recipe_versions_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = [
        kitchen_rag.Evidence("c1", "portion", "#12 §4", "v1"),
        kitchen_rag.Evidence("c2", "method", "#12 §5", "v2"),
    ]
    monkeypatch.setattr(kitchen_copilot, "retrieve", lambda *_args: evidence)
    answer, citations = kitchen_copilot.ask(principal(Role.KITCHEN_MANAGER), "How is this prepared?")
    assert "mixed recipe versions" in answer.lower()
    assert citations == []


def test_retrieval_passes_mandatory_server_scope_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class Result:
        def all(self) -> list[object]:
            return []

    class Connection:
        def execute(self, statement: object, params: dict[str, Any]) -> Result:
            seen["sql"] = str(statement)
            seen["params"] = params
            return Result()

        def __enter__(self) -> Connection:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class Engine:
        def connect(self) -> Connection:
            return Connection()

    monkeypatch.setattr(kitchen_rag, "get_engine", lambda: Engine())
    monkeypatch.setattr(kitchen_rag, "get_settings", lambda: SimpleNamespace(app_env="production"))
    kitchen_rag.retrieve("recipe", principal(Role.KITCHEN_MANAGER), "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    query = str(seen["sql"])
    params = seen["params"]
    assert "retrieve_kitchen_chunks" in query
    assert params["kitchen_ids"] == [str(KITCHEN)]
    assert params["include_fixtures"] is False
    assert params["recipe_version_id"] == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    assert params["roles"] == ["KITCHEN_MANAGER"]


def test_mock_embedder_is_deterministic_and_uses_explicit_dimension() -> None:
    embedder = MockEmbedder(dimension=8)
    first = embedder.embed(["recipe method", "recipe method"])
    assert first[0] == first[1]
    assert len(first[0]) == 8
    assert embedder.embed(["different text"])[0] != first[0]


def test_k2_only_stages_draft_document_content(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source_dir = tmp_path
    (source_dir / "stub.md").write_text(
        "<!-- status: DRAFT -->\nPending Kitchen Manager approval.", encoding="utf-8"
    )
    monkeypatch.setattr(k2, "KNOWLEDGE_DIR", source_dir)
    monkeypatch.setattr(k2, "get_settings", lambda: SimpleNamespace(app_env="test"))
    captured: list[tuple[str, dict[str, Any]]] = []

    class Result:
        def all(self) -> list[object]:
            return []

    class Data:
        def execute(self, statement: object, params: dict[str, Any]) -> Result:
            captured.append((str(statement), params))
            return Result()

    class Counts:
        rows_in = None
        rows_out = None

        def __init__(self) -> None:
            self.rows_in = None
            self.rows_out = None
            self.detail: dict[str, object] = {}

    class Context:
        def __init__(self) -> None:
            self.data = Data()
            self.counts: dict[str, object] = {}

        @contextmanager
        def stage(self, _name: str) -> Iterator[Counts]:
            yield Counts()

    k2.run_k2(cast(RunContext, Context()))
    assert len(captured) == 2
    sql, params = captured[0]
    assert "'DRAFT'" in sql
    assert "kitchen_rag.kitchen_scope" in sql
    assert "PUBLISHED" not in sql
    assert "status: DRAFT" in str(params["content"])
    assert captured[1][1]["allow_fixtures"] is True


def test_k2_is_triggerable_only_for_draft_ingestion() -> None:
    assert DEFAULT_INPUT["k2_kitchen"] == "draft"
    assert TRIGGERABLE["k2_kitchen"] == frozenset({"draft"})


def test_demo_environment_allows_fixture_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class Result:
        def all(self) -> list[object]:
            return []

    class Connection:
        def execute(self, _statement: object, params: dict[str, Any]) -> Result:
            seen.update(params)
            return Result()

        def __enter__(self) -> Connection:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class Engine:
        def connect(self) -> Connection:
            return Connection()

    monkeypatch.setattr(kitchen_rag, "get_engine", lambda: Engine())
    monkeypatch.setattr(kitchen_rag, "get_settings", lambda: SimpleNamespace(app_env="demo"))
    kitchen_rag.retrieve("recipe", principal(Role.KITCHEN_STAFF))
    assert seen["include_fixtures"] is True
