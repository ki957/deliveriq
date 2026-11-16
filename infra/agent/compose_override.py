"""Write a secret-free Compose override for the Builder Agent's selected route."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def selected_provider_key(config_path: Path) -> str | None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    harnesses = config.get("harnesses", {})
    models = config.get("models", {})
    providers = config.get("providers", {})
    route = harnesses.get("builder_agent", {})
    model_name = route.get("default_model", "strong")
    model = models.get(model_name)
    if model is None:
        raise ValueError("Builder Agent route references an unknown model")
    provider = providers.get(model.get("provider"))
    if provider is None:
        raise ValueError("Builder Agent model references an unknown provider")
    key_env = provider.get("key_env")
    if key_env is None or provider.get("adapter") == "mock":
        return None
    if not isinstance(key_env, str) or ENV_NAME.fullmatch(key_env) is None:
        raise ValueError("provider key environment name is invalid")
    return key_env


def main() -> None:
    config_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    workspace_path = Path(sys.argv[3]).resolve()
    environment: dict[str, str] = {"GITHUB_TOKEN": "${GITHUB_TOKEN:-}"}
    key_env = selected_provider_key(config_path)
    if key_env is not None:
        environment[key_env] = f"${{{key_env}:-}}"
    override = {
        "services": {
            "agent": {
                "environment": environment,
                "volumes": [
                    {
                        "type": "bind",
                        "source": str(workspace_path),
                        "target": "/workspace",
                    }
                ],
            }
        }
    }
    output_path.write_text(json.dumps(override), encoding="utf-8")
    output_path.chmod(0o600)


if __name__ == "__main__":
    main()
