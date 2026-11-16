from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai import gateway
from app.core.permissions import Grant, Principal, Role
from app.modules.ai import customer_assistant, customer_rag

CUSTOMER = Principal(uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"), (Grant(role=Role.CUSTOMER),))
GOLDEN_PATH = Path(__file__).parents[4] / "test_inputs" / "customer_assistant_golden_draft.json"


class Result:
    def __init__(self, *, row: object | None = None, rows: list[dict[str, object]] | None = None) -> None:
        self.row = row
        self.rows = rows or []

    def first(self) -> object | None:
        return self.row

    def scalar_one(self) -> uuid.UUID:
        return uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

    def mappings(self) -> Result:
        return self

    def all(self) -> list[dict[str, object]]:
        return self.rows


class Connection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, dict[str, Any] | None]] = []

    def execute(self, statement: object, params: dict[str, Any] | None = None) -> Result:
        sql = str(statement)
        self.statements.append((sql, params))
        if "INSERT INTO app.ai_conversations" in sql:
            return Result()
        if "SELECT name, price_paise" in sql:
            return Result(
                rows=[
                    {
                        "name": "TEST dish",
                        "price_paise": 1234,
                        "publication_status": "TEMPORARILY_UNAVAILABLE",
                    }
                ]
            )
        if "SELECT id, fulfilment_status" in sql:
            return Result(rows=[{"id": "own-order", "fulfilment_status": "PREPARING"}])
        if "SELECT 1 FROM app.ai_conversations" in sql:
            return Result(row=(1,))
        return Result()

    def __enter__(self) -> Connection:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class Engine:
    def __init__(self) -> None:
        self.connection = Connection()

    def connect(self) -> Connection:
        return self.connection

    def begin(self) -> Connection:
        return self.connection


def _setup(monkeypatch: pytest.MonkeyPatch, *, guard: bool) -> tuple[Engine, list[dict[str, str]], list[str]]:
    engine = Engine()
    prompts: list[dict[str, str]] = []
    guard_events: list[str] = []
    monkeypatch.setattr(customer_assistant, "get_engine", lambda: engine)
    monkeypatch.setattr(
        customer_assistant,
        "get_settings",
        lambda: SimpleNamespace(ai_prompt_guard_enabled=guard),
    )
    monkeypatch.setattr(
        customer_assistant,
        "_record_guard_event",
        lambda _principal, status: guard_events.append(status),
    )
    monkeypatch.setattr(customer_assistant, "retrieve", lambda *_args: [])

    def complete(_harness: str, messages: list[dict[str, str]]) -> tuple[str, str]:
        prompts.extend(messages)
        return "Mock customer answer", "fast"

    monkeypatch.setattr(gateway, "complete", complete)
    return engine, prompts, guard_events


def test_customer_assistant_uses_approved_prompt_and_logs_its_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, messages, _ = _setup(monkeypatch, guard=False)
    monkeypatch.setattr(
        customer_assistant,
        "_public_live_context",
        lambda *_args: "menu:TEST price_paise=1234",
    )

    answer, _, _, _, status = customer_assistant.ask(CUSTOMER, "Is this dish safe for my allergy?", None)

    approved_prompt = customer_assistant.PROMPT_PATH.read_text(encoding="utf-8")
    system_prompt = messages[0]["content"]
    assert "Never guarantee allergen safety" in approved_prompt
    assert "Never guarantee allergen safety" in system_prompt
    assert "For current price, availability, order status, and delivery quotes" in system_prompt
    assert answer == "Mock customer answer"
    assert status == "off"
    expected_hash = hashlib.sha256(approved_prompt.encode("utf-8")).hexdigest()
    request_sql = next(sql for sql, _ in engine.connection.statements if "INSERT INTO ops.ai_requests" in sql)
    request_params = next(
        params for sql, params in engine.connection.statements if "INSERT INTO ops.ai_requests" in sql
    )
    assert "prompt_sha256" in request_sql
    assert request_params is not None and request_params["prompt_sha256"] == expected_hash


def test_live_facts_are_tool_sourced_and_scoped_to_the_authenticated_customer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, messages, _ = _setup(monkeypatch, guard=False)
    monkeypatch.setattr(
        customer_assistant,
        "retrieve",
        lambda *_args: [
            customer_rag.CustomerChunk("c1", "Old price: ₹9.99; currently available", "K-C1 #4", 1.0)
        ],
    )

    customer_assistant.ask(CUSTOMER, "What is the current price and my order status?", None)

    user_context = messages[1]["content"]
    assert "Old price: ₹9.99" in user_context
    assert "price_paise=1234" in user_context
    assert "availability=unavailable status=TEMPORARILY_UNAVAILABLE" in user_context
    assert "status=PREPARING" in user_context
    assert "Live read-only facts:" in user_context
    order_query, order_params = next(
        (sql, params) for sql, params in engine.connection.statements if "SELECT id, fulfilment_status" in sql
    )
    assert "customer_user_id=:customer" in order_query
    assert order_params == {"customer": CUSTOMER.user_id}


def test_shared_injection_cases_are_evaluated_with_prompt_guard_on_and_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    cases = [case["question"] for case in dataset["cases"] if case["category"] == "injection"]
    assert len(cases) == 10
    enabled: list[str] = []
    disabled: list[str] = []
    for question in cases:
        monkeypatch.setattr(
            customer_assistant, "get_settings", lambda: SimpleNamespace(ai_prompt_guard_enabled=True)
        )
        flagged, status = customer_assistant._guard(question)
        assert status in {"blocked", "clear"}
        if flagged:
            enabled.append(question)
        monkeypatch.setattr(
            customer_assistant, "get_settings", lambda: SimpleNamespace(ai_prompt_guard_enabled=False)
        )
        flagged, status = customer_assistant._guard(question)
        assert not flagged and status == "off"
        disabled.append(question)
    assert len(enabled) == 8
    assert len(disabled) == 10


@pytest.mark.parametrize("failure", ["classifier outage", "rate limit"])
def test_prompt_guard_classifier_failure_is_fail_open_and_logged(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    engine, _messages, guard_events = _setup(monkeypatch, guard=True)
    monkeypatch.setattr(customer_assistant, "_public_live_context", lambda *_args: "")

    def classify(*_args: object) -> tuple[bool, str]:
        raise gateway.GatewayError(failure)

    monkeypatch.setattr(gateway, "classify", classify)
    answer, _, _, _, status = customer_assistant.ask(CUSTOMER, "Where can I get delivery help?", None)

    assert answer == "Mock customer answer"
    assert status == "unavailable"
    assert guard_events == ["unavailable"]
    assert any("INSERT INTO ops.ai_requests" in sql for sql, _ in engine.connection.statements)


def test_prompt_guard_outcome_is_inserted_into_the_event_log(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = Engine()
    monkeypatch.setattr(customer_assistant, "get_engine", lambda: engine)

    customer_assistant._record_guard_event(CUSTOMER, "unavailable")

    sql, params = engine.connection.statements[0]
    assert "INSERT INTO ops.prompt_guard_events" in sql
    assert params == {
        "user_id": CUSTOMER.user_id,
        "harness": "customer_assistant",
        "outcome": "unavailable",
    }


def test_anonymous_customer_retrieval_is_public_only(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class RetrievalResult(Result):
        def all(self) -> list[dict[str, object]]:
            return []

    class RetrievalConnection(Connection):
        def execute(self, statement: object, params: dict[str, Any] | None = None) -> RetrievalResult:
            captured["sql"] = str(statement)
            captured["params"] = params
            return RetrievalResult()

    class RetrievalEngine(Engine):
        def connect(self) -> RetrievalConnection:
            return RetrievalConnection()

    monkeypatch.setattr(customer_rag, "get_engine", lambda: RetrievalEngine())
    assert customer_rag.retrieve("public menu", None) == []
    assert "app.retrieve_customer_chunks_hybrid" in str(captured["sql"])
    assert captured["params"] == {"question": "public menu", "authenticated": False, "fixtures": False}


def test_unowned_customer_conversation_is_rejected_before_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    engine, _messages, _ = _setup(monkeypatch, guard=False)
    retrieved = False

    def retrieve(*_args: object) -> list[object]:
        nonlocal retrieved
        retrieved = True
        return []

    monkeypatch.setattr(customer_assistant, "retrieve", retrieve)
    monkeypatch.setattr(engine.connection, "execute", lambda *_args, **_kwargs: Result())

    with pytest.raises(customer_assistant.NotFound):
        customer_assistant.ask(CUSTOMER, "Read another customer's conversation", uuid.uuid4())
    assert not retrieved
