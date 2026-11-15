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
        if "DeliverIQ Kitchen Copilot" in system and "[S1]" in user:
            excerpt = user.split("[S1]", 1)[1].split("\n\n[S2]", 1)[0].strip()
            return "Simulated source excerpt [S1]: " + excerpt[:500]
        if "DeliverIQ Customer Assistant" in system:
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


def structured_proposal[T](harness: str, request: str, mock_handler: Callable[[str], T]) -> tuple[T, str]:
    """Select by harness capabilities; the mock handler returns a typed proposal, never executes it."""
    model = select_model(load_catalog(), harness)
    if model.provider != "mock":
        raise GatewayError("Live AI provider is not configured")
    return mock_handler(request), model.logical_name


def ai_enabled() -> bool:
    return get_settings().is_local_or_test
