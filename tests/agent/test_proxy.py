from __future__ import annotations

# pytest assertions are the test idiom.
# ruff: noqa: S101, S603
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.shared.agent_egress import GITHUB_HOSTS, configured_provider_hosts, parse_connect_target

REPO_ROOT = Path(__file__).resolve().parents[2]


def generate_override(tmp_path: Path, config: dict[str, object]) -> dict[str, object]:
    config_path = tmp_path / "ai_models.yaml"
    output_path = tmp_path / "override.json"
    workspace_path = tmp_path / "repo"
    workspace_path.mkdir()
    config_path.write_text(json.dumps(config), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "infra/agent/compose_override.py"),
            str(config_path),
            str(output_path),
            str(workspace_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(output_path.read_text(encoding="utf-8"))


def test_proxy_allows_github_and_exact_configured_provider_hosts(tmp_path: Path) -> None:
    config_path = tmp_path / "ai_models.yaml"
    config_path.write_text(
        json.dumps(
            {
                "providers": {
                    "groq": {"adapter": "openai_compatible", "host": "https://api.groq.com"},
                    "mock": {"adapter": "mock", "host": "local"},
                }
            }
        ),
        encoding="utf-8",
    )

    assert {
        "api.github.com",
        "codeload.github.com",
        "github.com",
        "raw.githubusercontent.com",
    } == GITHUB_HOSTS
    assert configured_provider_hosts(config_path) == {"api.groq.com"}


@pytest.mark.parametrize("host", ["*.groq.com", "http://api.groq.com", "api.groq.com:8443"])
def test_proxy_rejects_non_exact_https_provider_hosts(tmp_path: Path, host: str) -> None:
    config_path = tmp_path / "ai_models.yaml"
    config_path.write_text(
        json.dumps({"providers": {"custom": {"adapter": "openai_compatible", "host": host}}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        configured_provider_hosts(config_path)


def test_connect_target_parses_host_and_port() -> None:
    assert parse_connect_target("API.GITHUB.COM:443") == ("api.github.com", 443)
    assert parse_connect_target("example.com:80") == ("example.com", 80)
    assert parse_connect_target("example.com:99999") is None
    assert parse_connect_target("127.0.0.1") is None


def test_agent_route_passes_no_provider_key_for_mock_adapter(tmp_path: Path) -> None:
    config = json.loads(Path("backend/config/ai_models.yaml").read_text(encoding="utf-8"))
    override = generate_override(tmp_path, config)
    assert set(override["services"]["agent"]["environment"]) == {"GITHUB_TOKEN"}


def test_agent_route_key_comes_from_selected_model_provider(tmp_path: Path) -> None:
    override = generate_override(
        tmp_path,
        {
            "harnesses": {"builder_agent": {"default_model": "strong"}},
            "models": {"strong": {"provider": "groq"}},
            "providers": {"groq": {"adapter": "openai_compatible", "key_env": "GROQ_API_KEY"}},
        },
    )

    assert set(override["services"]["agent"]["environment"]) == {
        "GITHUB_TOKEN",
        "GROQ_API_KEY",
    }
