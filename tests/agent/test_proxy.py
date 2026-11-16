from __future__ import annotations

# pytest assertions are the test idiom.
# ruff: noqa: S101, S603, S607
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.shared.agent_egress import GITHUB_HOSTS, configured_provider_hosts, parse_connect_target

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_SCRIPT = REPO_ROOT / "infra/agent/snapshot.py"


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


def test_provider_allowlist_tracks_host_changes_in_ai_models_config(tmp_path: Path) -> None:
    config_path = tmp_path / "ai_models.yaml"
    config_path.write_text(
        json.dumps({"providers": {"selected": {"adapter": "openai_compatible", "host": "api.groq.com"}}}),
        encoding="utf-8",
    )
    groq_hosts = configured_provider_hosts(config_path)

    config_path.write_text(
        json.dumps({"providers": {"selected": {"adapter": "openai_compatible", "host": "openrouter.ai"}}}),
        encoding="utf-8",
    )
    openrouter_hosts = configured_provider_hosts(config_path)

    assert groq_hosts == {"api.groq.com"}
    assert openrouter_hosts == {"openrouter.ai"}
    assert groq_hosts != openrouter_hosts


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


def test_agent_environment_contains_only_selected_provider_key_and_github_token(
    tmp_path: Path,
) -> None:
    override = generate_override(
        tmp_path,
        {
            "harnesses": {"builder_agent": {"default_model": "strong"}},
            "models": {"strong": {"provider": "groq"}},
            "providers": {
                "groq": {"adapter": "openai_compatible", "key_env": "GROQ_API_KEY"},
                "openrouter": {
                    "adapter": "openai_compatible",
                    "key_env": "OPENROUTER_API_KEY",
                },
            },
        },
    )

    environment_names = set(override["services"]["agent"]["environment"])
    print("sandbox secret environment names: " + ", ".join(sorted(environment_names)))
    assert environment_names == {"GITHUB_TOKEN", "GROQ_API_KEY"}
    assert "OPENROUTER_API_KEY" not in environment_names


def test_untracked_secret_file_is_not_seeded_and_dirty_checkout_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "source"
    workspace = tmp_path / "workspace"
    source.mkdir()
    subprocess.run(["git", "init", str(source)], check=True, capture_output=True, text=True)
    (source / "committed.txt").write_text("committed", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "committed.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Sandbox Test",
            "-c",
            "user.email=sandbox-test@example.invalid",
            "commit",
            "-m",
            "seed",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    (source / "secret.pem").write_text("dummy secret", encoding="utf-8")

    subprocess.run(
        [sys.executable, str(SNAPSHOT_SCRIPT), "clone-head", str(source), str(workspace)],
        check=True,
        capture_output=True,
        text=True,
    )
    dirty_result = subprocess.run(
        [sys.executable, str(SNAPSHOT_SCRIPT), "check-clean", str(source)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert (workspace / "committed.txt").is_file()
    assert not (workspace / "secret.pem").exists()
    assert dirty_result.returncode != 0
    assert "working tree is not clean" in dirty_result.stderr
