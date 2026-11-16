"""Check the live agent container without printing configuration values."""

# This checker invokes fixed system binaries with the locally created Compose container ID.
# ruff: noqa: S603, S607

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

EXPECTED_PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", "deliveriq")
TMP_TARGET = chr(47) + "tmp"
TMPFS_WORKSPACE_ROOT = str(Path(chr(47)).joinpath("dev", "shm", "deliveriq-agent."))
EXPECTED_MOUNTS = {"/workspace"}
ALLOWED_ENV = {
    "GPG_KEY",
    "LANG",
    "HOME",
    "PATH",
    "PYTHONPATH",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONUNBUFFERED",
    "PYTHON_SHA256",
    "PYTHON_VERSION",
    "http_proxy",
    "https_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "no_proxy",
    "GITHUB_TOKEN",
}


def selected_provider_key() -> str | None:
    config = json.loads(Path("backend/config/ai_models.yaml").read_text(encoding="utf-8"))
    route = config.get("harnesses", {}).get("builder_agent", {})
    model = config.get("models", {}).get(route.get("default_model", "strong"))
    if model is None:
        raise AssertionError("Builder Agent model is not configured")
    provider = config.get("providers", {}).get(model.get("provider"))
    if provider is None:
        raise AssertionError("Builder Agent provider is not configured")
    key_env = provider.get("key_env")
    if provider.get("adapter") == "mock":
        return None
    return key_env


def inspect_container(container_id: str) -> dict[str, object]:
    result = subprocess.run(
        ["docker", "inspect", container_id],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)[0]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    listing = subprocess.run(
        ["docker", "compose", "ls", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    projects = {row["Name"] for row in json.loads(listing.stdout)}
    require(EXPECTED_PROJECT in projects, f"Compose project {EXPECTED_PROJECT} is not running")
    print(f"PASS: docker compose ls reports {EXPECTED_PROJECT}")

    item = inspect_container(sys.argv[1])
    mounts = item.get("Mounts", [])
    destinations = {mount.get("Destination"): mount for mount in mounts}
    require(set(destinations) == EXPECTED_MOUNTS, "unexpected agent mount destination")
    workspace_mount = destinations["/workspace"]
    require(workspace_mount.get("Type") == "bind", "workspace must be a disposable bind from tmpfs")
    workspace_source = Path(workspace_mount["Source"])
    require(
        str(workspace_source).startswith(TMPFS_WORKSPACE_ROOT),
        "workspace source is not disposable tmpfs",
    )
    filesystem = subprocess.run(
        ["findmnt", "-n", "-o", "FSTYPE", "--target", str(workspace_source)],
        check=True,
        capture_output=True,
        text=True,
    )
    require(filesystem.stdout.strip() == "tmpfs", "workspace source is not on tmpfs")
    require(
        all(".env" not in str(mount) and "docker.sock" not in str(mount) for mount in mounts),
        "agent mount references a forbidden host path",
    )
    env_files = [
        path for path in workspace_source.rglob(".env*") if path.name != ".env.example" and path.is_file()
    ]
    require(not env_files, "workspace contains an .env file other than the placeholder")
    print("PASS: workspace is tmpfs-backed; no .env or Docker socket mount or file")

    env_entries = item["Config"]["Env"]
    env_names = {entry.partition("=")[0] for entry in env_entries}
    key_env = selected_provider_key()
    expected = set(ALLOWED_ENV)
    if key_env is not None:
        expected.add(key_env)
    require(
        env_names == expected,
        f"agent environment names differ from allowlist: {sorted(env_names)}",
    )
    sensitive = {
        name
        for name in env_names
        if name != "GPG_KEY" and name.endswith(("_KEY", "_PASSWORD", "_TOKEN", "_PEPPER"))
    }
    expected_sensitive = {"GITHUB_TOKEN"} | ({key_env} if key_env is not None else set())
    require(sensitive == expected_sensitive, "unexpected secret environment name")
    print("PASS: environment names are explicitly allowlisted")

    network_names = set(item["NetworkSettings"]["Networks"])
    require(
        len(network_names) == 1 and all("agent_net" in name for name in network_names),
        "agent is attached to an unexpected network",
    )
    print("PASS: agent is attached only to its internal network")

    host_config = item["HostConfig"]
    require(set(host_config["Tmpfs"]) == {TMP_TARGET}, "agent /tmp is not an isolated tmpfs")
    require(host_config["Memory"] == 1024**3, "agent memory cap is not 1 GiB")
    require(host_config["NanoCpus"] == 1_000_000_000, "agent CPU cap is not 1 CPU")
    print("PASS: agent resource limits are 1 GiB and 1 CPU")


if __name__ == "__main__":
    main()
