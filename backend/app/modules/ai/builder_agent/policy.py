"""Builder Agent path rules: reject protected writes and untrusted context reads."""

from __future__ import annotations

from pathlib import PurePosixPath


class ProtectedPath(ValueError):
    pass


class UntrustedContext(ValueError):
    pass


def normalized_repo_path(raw_path: str) -> str:
    if not raw_path or "\x00" in raw_path or "\\" in raw_path:
        raise ProtectedPath("Invalid repository path")
    path = PurePosixPath(raw_path)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ProtectedPath("Invalid repository path")
    if path.parts and path.parts[0].endswith(":"):
        raise ProtectedPath("Invalid repository path")
    return path.as_posix()


def is_protected_path(raw_path: str) -> bool:
    try:
        value = normalized_repo_path(raw_path)
    except ProtectedPath:
        return True
    path = PurePosixPath(value)
    lower_parts = tuple(part.lower() for part in path.parts)
    name = path.name.lower()
    if any(part == ".git" for part in lower_parts):
        return True
    if any(part.startswith(".env") for part in lower_parts):
        return True
    if name in {"agents.md", "permission.py", "permissions.py", "rbac.py", "access_control.py"}:
        return True
    if "secret" in name or name.endswith((".pem", ".key", ".p12", ".pfx")):
        return True
    protected_components = {
        ".agents",
        ".codex",
        ".kiro",
        "guardrail",
        "guardrails",
        "prompts",
        "secrets",
        "permissions",
        "rbac",
        "access_control",
    }
    if any(part in protected_components or part.startswith("guardrail") for part in lower_parts):
        return True
    if any("prompt" in part for part in lower_parts):
        return True
    if value.startswith(".github/workflows/") or value == ".github/workflows":
        return True
    if value == "backend/config/ai_models.yaml":
        return True
    # DDR-13.2 identifies all infrastructure as read-only to the Builder Agent.
    if value == "infra" or value.startswith("infra/"):
        return True
    # The agent must not change the policy module that enforces these checks.
    return value == "backend/app/modules/ai/builder_agent/policy.py"


def require_writable(raw_path: str) -> str:
    normalized = normalized_repo_path(raw_path)
    if is_protected_path(normalized):
        raise ProtectedPath("The requested change touches a protected path")
    return normalized


def require_readable_context(raw_path: str) -> str:
    normalized = normalized_repo_path(raw_path)
    path = PurePosixPath(normalized)
    lower_parts = tuple(part.lower() for part in path.parts)
    if is_protected_path(normalized):
        raise UntrustedContext("Protected content cannot enter the agent context")
    if (
        lower_parts[0] in {"data", "docs"}
        or normalized == "passon.md"
        or any(part in {"rag", "knowledge", "tickets", "reviews", "notes"} for part in lower_parts)
        or (path.suffix.lower() in {".json", ".jsonl", ".csv", ".tsv"} and "tests" in lower_parts)
    ):
        raise UntrustedContext("Untrusted content cannot enter the agent context")
    return normalized
