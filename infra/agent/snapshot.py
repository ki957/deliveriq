"""Check a clean source checkout and clone exactly its committed HEAD."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def require_clean_repository(source: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=normal"],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print("Refusing to start agent: working tree is not clean.", file=sys.stderr)
        return False
    return True


def clone_committed_head(source: Path, workspace: Path) -> None:
    commit = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--no-hardlinks",
            "--local",
            "--no-checkout",
            str(source),
            str(workspace),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(workspace), "checkout", "--quiet", "--detach", commit],
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> int:
    action = sys.argv[1]
    source = Path(sys.argv[2]).resolve()
    try:
        if action == "check-clean":
            return 0 if require_clean_repository(source) else 1
        if action == "clone-head":
            clone_committed_head(source, Path(sys.argv[3]).resolve())
            return 0
    except (OSError, subprocess.CalledProcessError):
        print("Failed to prepare committed agent workspace.", file=sys.stderr)
        return 1
    print("Usage: snapshot.py check-clean SOURCE | clone-head SOURCE WORKSPACE", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
