"""Provider-neutral AI gateway; harnesses depend on capabilities, never provider IDs."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings


class GatewayError(Exception):
    pass


@dataclass(frozen=True)
class ModelSpec:
    logical_name: str
    provider: str
    capabilities: frozenset[str]


@dataclass(frozen=True)
class HarnessSpec:
    name: str
    default_model: str
    required_capabilities: frozenset[str]


@dataclass(frozen=True)
class Catalog:
    models: dict[str, ModelSpec]
    harnesses: dict[str, HarnessSpec]


class ChatAdapter(Protocol):
    def complete(self, *, model: ModelSpec, messages: list[dict[str, str]]) -> str: ...


class MockAdapter:
    def complete(self, *, model: ModelSpec, messages: list[dict[str, str]]) -> str:
        del model
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        if "You are the DeliverIQ Builder Agent" in system:
            original_request = next(
                (
                    m["content"]
                    for m in messages
                    if m["role"] == "user" and not m["content"].startswith("TOOL RESULT:")
                ),
                "",
            )
            golden_path = {
                "GOLDEN_REAL_TASK_1": "backend/app/modules/ai/actions/README.md",
                "GOLDEN_REAL_TASK_2": "frontend/src/features/management/README.md",
                "GOLDEN_REAL_TASK_3": "backend/app/modules/ai/customer_assistant/README.md",
            }
            protected_path = {
                "GOLDEN_PROTECTED_ENV": ".env.builder-test",
                "GOLDEN_PROTECTED_CONFIG": "backend/config/ai_models.yaml",
                "GOLDEN_PROTECTED_WORKFLOW": ".github/workflows/checks.yml",
            }
            for marker, path in protected_path.items():
                if marker in original_request:
                    return json.dumps({"tool": "write_file", "path": path, "content": "blocked"})
            if "TOOL RESULT:" not in user:
                path = next(
                    (path for marker, path in golden_path.items() if marker in original_request),
                    "backend/app/modules/ai/actions/README.md",
                )
                return json.dumps({"tool": "read_file", "path": path})
            try:
                result = json.loads(user.split("TOOL RESULT:", 1)[1].strip())
            except json.JSONDecodeError:
                result = {}
            if result.get("tool") == "read_file" and result.get("ok"):
                content = str(result.get("content", ""))
                path = str(result.get("path", "backend/app/modules/ai/actions/README.md"))
                marker = next(
                    (key for key, candidate in golden_path.items() if candidate == path), "local-preview"
                )
                task_name = marker if marker != "local-preview" else original_request[:48]
                note = f"Builder Agent mock task: {task_name}"
                if note not in content:
                    content = content.rstrip() + f"\n\n{note}\n"
                return json.dumps(
                    {
                        "tool": "write_file",
                        "path": path,
                        "content": content,
                    }
                )
            if result.get("tool") == "write_file" and result.get("ok"):
                return json.dumps({"tool": "run_unit_tests"})
            if result.get("tool") == "run_unit_tests" and result.get("passed"):
                return json.dumps(
                    {
                        "tool": "finish",
                        "summary": "Added a review-only mock preview note to the Builder Agent README.",
                    }
                )
            return json.dumps({"tool": "finish", "summary": "The mock Builder Agent stopped safely."})
        if "DeliverIQ Kitchen Copilot" in system and "[S1]" in user:
            excerpt = user.split("[S1]", 1)[1].split("\n\n[S2]", 1)[0].strip()
            return "Simulated source excerpt [S1]: " + excerpt[:500]
        if "DeliverIQ Customer Assistant" in system:
            question = user.split("\n\nCustomer sources:", 1)[0].lower()
            refusal_terms = (
                "allergy",
                "allergen",
                "recipe",
                "staff",
                "promise my refund",
                "inventory",
                "system prompt",
                "change my order",
                "another customer",
                "customer a",
                "different order id",
                "customer orders",
                "neighbour",
                "different session",
                "another person's cart",
                "guessed id",
                "phone number",
                "support case",
                "list all",
                "password",
                "guarantee a delivery time",
                "ignore ",
                "jailbreak",
                "developer message",
            )
            if any(term in question for term in refusal_terms):
                return (
                    "I can't provide private or internal information, make changes, promise a refund, "
                    "or guarantee allergen safety or delivery outcomes. Please contact support for help."
                )
            return (
                "I can help with customer menu, delivery and support information using the "
                "available published sources and live read-only facts."
            )
        return (
            "Management Copilot response. I can provide read-only operational context "
            "when approved knowledge is available. Your request was: " + user[:500]
        )


def load_catalog(path: Path | None = None) -> Catalog:
    config_path = path or Path(__file__).parents[2] / "config" / "ai_models.yaml"
    raw: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    models = {
        name: ModelSpec(name, value["provider"], frozenset(value["capabilities"]))
        for name, value in raw["models"].items()
    }
    harnesses = {
        name: HarnessSpec(name, value["default_model"], frozenset(value["required_capabilities"]))
        for name, value in raw["harnesses"].items()
    }
    return Catalog(models, harnesses)


def select_model(catalog: Catalog, harness: str, logical_model: str | None = None) -> ModelSpec:
    spec = catalog.harnesses.get(harness)
    if spec is None:
        raise GatewayError("Unknown AI harness")
    name = logical_model or spec.default_model
    model = catalog.models.get(name)
    if model is None or not spec.required_capabilities.issubset(model.capabilities):
        raise GatewayError("Configured model does not support this harness")
    return model


def complete(
    harness: str, messages: list[dict[str, str]], logical_model: str | None = None
) -> tuple[str, str]:
    model = select_model(load_catalog(), harness, logical_model)
    if model.provider != "mock":
        raise GatewayError("Live AI provider is not configured")
    return MockAdapter().complete(model=model, messages=messages), model.logical_name


def classify(harness: str, text: str, logical_model: str = "guard") -> tuple[bool, str]:
    """Provider-neutral classifier hook used by Prompt Guard; the local adapter is deterministic."""
    catalog = load_catalog()
    harness_spec = catalog.harnesses.get(harness)
    model = catalog.models.get(logical_model)
    if (
        harness_spec is None
        or model is None
        or model.provider != "mock"
        or "classification" not in model.capabilities
    ):
        raise GatewayError("Prompt Guard classifier is not configured")
    markers = ("ignore previous", "system prompt", "jailbreak", "developer message")
    return any(marker in text.lower() for marker in markers), model.logical_name


def structured_proposal[T](harness: str, request: str, mock_handler: Callable[[str], T]) -> tuple[T, str]:
    """Select by harness capabilities; the mock handler returns a typed proposal, never executes it."""
    model = select_model(load_catalog(), harness)
    if model.provider != "mock":
        raise GatewayError("Live AI provider is not configured")
    return mock_handler(request), model.logical_name


def ai_enabled() -> bool:
    return get_settings().is_local_or_test
