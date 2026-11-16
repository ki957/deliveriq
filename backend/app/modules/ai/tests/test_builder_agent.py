"""Builder Agent policy, tool boundary, and branch-publication invariants."""

from __future__ import annotations

import ast
import inspect
import json

import pytest

from app.ai import gateway
from app.modules.ai.builder_agent import github, policy


@pytest.mark.parametrize(
    "path",
    [
        "backend/app/modules/ai/builder_agent/prompt.md",
        "backend/app/modules/ai/builder_agent/policy.py",
        "backend/app/core/permissions.py",
        "backend/app/core/rbac.py",
        "backend/app/core/permission.py",
        "backend/app/core/access_control.py",
        "backend/app/core/rbac/roles.py",
        "backend/app/shared/guardrails.py",
        "backend/config/ai_models.yaml",
        ".env",
        ".env.production",
        "backend/.env.local",
        "secrets/provider.pem",
        "backend/app/secrets_manager.py",
        "secrets/github.key",
        ".github/workflows/check.yml",
        ".codex/hooks.json",
        ".agents/skills/ship/SKILL.md",
        "AGENTS.md",
        ".kiro/steering/rules.md",
        "infra/agent/run.sh",
    ],
)
def test_builder_rejects_protected_paths(path: str) -> None:
    with pytest.raises(policy.ProtectedPath):
        policy.require_writable(path)


@pytest.mark.parametrize("path", ["../escape.py", "/etc/passwd", "backend\\outside.py", "C:/repo/file.py"])
def test_builder_rejects_path_traversal(path: str) -> None:
    with pytest.raises(policy.ProtectedPath):
        policy.require_writable(path)


def test_builder_allows_safe_source_and_readme_changes() -> None:
    assert policy.require_writable("backend/app/modules/ai/customer_assistant.py") == (
        "backend/app/modules/ai/customer_assistant.py"
    )
    assert policy.require_writable("backend/app/modules/ai/builder_agent/README.md").endswith("README.md")


@pytest.mark.parametrize(
    "path",
    [
        "docs/ORDER_NOTES.md",
        "data/source/ticket.txt",
        "backend/app/modules/ai/rag/knowledge.json",
        "tests/fixtures/customer_orders.json",
        "passon.md",
    ],
)
def test_builder_never_reads_untrusted_context_paths(path: str) -> None:
    with pytest.raises(policy.UntrustedContext):
        policy.require_readable_context(path)


def test_builder_mock_provider_uses_strong_and_only_direct_request_context() -> None:
    catalog = gateway.load_catalog()
    model = gateway.select_model(catalog, "builder_agent", "strong")
    assert model.logical_name == "strong"
    assert model.provider == "mock"
    messages = [
        {"role": "system", "content": "You are the DeliverIQ Builder Agent.\nTool protocol."},
        {"role": "user", "content": "Add a small README example."},
    ]
    result = gateway.MockAdapter().complete(model=model, messages=messages)
    assert json.loads(result)["tool"] == "read_file"
    context = " ".join(message["content"] for message in messages)
    assert not any(
        label in context for label in ("ticket body", "customer order note", "RAG document sentinel")
    )


def test_builder_github_client_has_no_main_update_or_merge_operation() -> None:
    source = inspect.getsource(github.GitHubClient)
    tree = ast.parse(source)
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert "merge" not in methods
    assert "/merges" not in source
    assert "refs/heads/" in source
    assert '"base": self._base_branch' in source
    assert '"head": branch' in source


def test_builder_mock_github_only_returns_a_new_non_main_branch() -> None:
    client = github.MockGitHubClient()
    result = client.open_pull_request(
        task_id="12345678-1234-5678-1234-567812345678",
        base_sha="a" * 40,
        summary="test proposal",
        files=[{"path": "README.md", "content": "updated"}],
        diff="+updated",
        test_result={"passed": True, "summary": "unit tests passed"},
    )
    assert result.branch == "builder-agent/12345678"
    assert result.branch != "main"
    assert len(client.calls) == 1


def test_builder_token_is_taken_from_environment_and_missing_token_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(github.GitHubPublishError, match="not configured"):
        github.github_client(local_or_test=False)
