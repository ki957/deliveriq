from pathlib import Path

import pytest

from app.ai.gateway import GatewayError, complete, load_catalog, select_model


def test_catalog_has_provider_neutral_harness() -> None:
    catalog = load_catalog(Path("backend/config/ai_models.yaml"))
    assert catalog.harnesses["management_copilot"].default_model == "fast"
    assert "chat" in catalog.models["fast"].capabilities


def test_capability_check_rejects_incompatible_model() -> None:
    with pytest.raises(GatewayError, match="does not support"):
        select_model(load_catalog(Path("backend/config/ai_models.yaml")), "management_copilot", "guard")


def test_mock_gateway_is_deterministic_and_does_not_expose_provider() -> None:
    answer, model = complete("management_copilot", [{"role": "user", "content": "show status"}])
    assert model == "fast"
    assert "show status" in answer
    assert "mock" not in answer.lower()
