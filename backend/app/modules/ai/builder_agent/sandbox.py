"""Committed-HEAD tmpfs workspaces based on the Task 15B snapshot helper."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from app.modules.ai.builder_agent import policy

MAX_FILE_BYTES = 64 * 1024
MAX_PATCH_BYTES = 256 * 1024
MAX_CHANGED_FILES = 10
MAX_LISTED_FILES = 100
TEST_TIMEOUT_SECONDS = 300


class SandboxError(RuntimeError):
    pass


class AgentWorkspace:
    def __init__(self, repository: Path) -> None:
        self.repository = repository.resolve()
        git = shutil.which("git")
        if git is None:
            raise SandboxError("Git is unavailable for the committed repository snapshot")
        self.git: str = git
        self._temp = tempfile.TemporaryDirectory(prefix="deliveriq-builder.", dir="/dev/shm")
        self.root = Path(self._temp.name) / "repo"
        snapshot = self.repository / "infra" / "agent" / "snapshot.py"
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(snapshot), "clone-head", str(self.repository), str(self.root)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode:
            self.close()
            raise SandboxError("Could not seed the committed repository snapshot")
        self._written: set[str] = set()

    def close(self) -> None:
        self._temp.cleanup()

    def __enter__(self) -> AgentWorkspace:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _path(self, relative: str) -> tuple[str, Path]:
        normalized = policy.normalized_repo_path(relative)
        target = (self.root / normalized).resolve(strict=False)
        if not target.is_relative_to(self.root):
            raise policy.ProtectedPath("Repository path escapes the sandbox")
        cursor = target.parent
        while cursor != self.root.parent:
            if cursor.is_symlink():
                raise policy.ProtectedPath("Repository path traverses a symlink")
            if cursor == self.root:
                break
            cursor = cursor.parent
        return normalized, target

    def list_files(self, directory: str = "") -> list[str]:
        base = self.root
        if directory:
            normalized = policy.require_readable_context(directory)
            base = self.root / normalized
            if not base.is_dir() or base.is_symlink():
                raise SandboxError("Directory is unavailable")
        result: list[str] = []
        for path in sorted(base.rglob("*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            relative = path.relative_to(self.root).as_posix()
            try:
                policy.require_readable_context(relative)
            except policy.UntrustedContext:
                continue
            result.append(relative)
            if len(result) >= MAX_LISTED_FILES:
                break
        return result

    def read_file(self, relative: str) -> str:
        normalized = policy.require_readable_context(relative)
        _, target = self._path(normalized)
        if not target.is_file() or target.is_symlink() or target.stat().st_size > MAX_FILE_BYTES:
            raise SandboxError("File is unavailable or too large")
        return target.read_text(encoding="utf-8")

    def write_file(self, relative: str, content: str) -> str:
        normalized = policy.require_writable(relative)
        if len(self._written | {normalized}) > MAX_CHANGED_FILES:
            raise SandboxError("The proposed change exceeds the file limit")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            raise SandboxError("The proposed file exceeds the size limit")
        _, target = self._path(normalized)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise policy.ProtectedPath("Cannot overwrite a symlink")
        target.write_bytes(encoded)
        self._written.add(normalized)
        return normalized

    def run_unit_tests(self) -> dict[str, Any]:
        if not self._written:
            raise SandboxError("No file changes are available to test")
        docker = shutil.which("docker")
        if docker is None:
            raise SandboxError("The isolated agent test runner is unavailable")
        compose = [docker, "compose", "--project-directory", str(self.repository), "-f", "infra/compose.yaml"]
        image = subprocess.run(  # noqa: S603
            [docker, "image", "inspect", "deliveriq-agent:local"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if image.returncode:
            build = subprocess.run(  # noqa: S603
                [*compose, "--profile", "agent", "build", "agent"],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
            if build.returncode:
                raise SandboxError("Could not prepare the isolated agent test image")
        result = subprocess.run(  # noqa: S603
            [
                docker,
                "run",
                "--rm",
                "--network",
                "none",
                "--memory",
                "1g",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",  # noqa: S108
                "--mount",
                f"type=bind,source={self.root},target=/workspace,readonly",
                "--workdir",
                "/workspace",
                "--env",
                "HOME=/tmp",
                "--env",
                "PYTHONPATH=/workspace/backend",
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                "deliveriq-agent:local",
                "python",
                "-m",
                "pytest",
                "-m",
                "not integration",
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
            check=False,
        )
        output = (result.stdout + result.stderr)[-12_000:]
        return {"passed": result.returncode == 0, "exit_code": result.returncode, "output": output}

    def diff(self) -> str:
        result = subprocess.run(  # noqa: S603
            [self.git, "diff", "--no-ext-diff", "--unified=3", "--"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        if len(result.stdout.encode("utf-8")) > MAX_PATCH_BYTES:
            raise SandboxError("The diff exceeds the review limit")
        changed = subprocess.run(  # noqa: S603
            [self.git, "diff", "--name-only", "--"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        ).stdout.splitlines()
        for path in changed:
            policy.require_writable(path)
        if len(changed) > MAX_CHANGED_FILES:
            raise SandboxError("The proposed change exceeds the file limit")
        if not result.stdout:
            raise SandboxError("The agent proposed no reviewable changes")
        return result.stdout

    def files(self) -> list[dict[str, str]]:
        changed = subprocess.run(  # noqa: S603
            [self.git, "diff", "--name-only", "--"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        ).stdout.splitlines()
        return [{"path": path, "content": (self.root / path).read_text(encoding="utf-8")} for path in changed]

    def base_sha(self) -> str:
        return subprocess.run(  # noqa: S603
            [self.git, "rev-parse", "HEAD"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
