"""Verify a custom-format Postgres backup using an isolated Compose project."""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import IO

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = ROOT / "infra" / "compose.yaml"
COUNTS = (
    "SELECT 'regions=' || count(*) FROM app.regions",
    "SELECT 'kitchens=' || count(*) FROM app.kitchens",
    "SELECT 'menu_items=' || count(*) FROM app.menu_items",
    "SELECT 'pipeline_runs=' || count(*) FROM ops.pipeline_runs",
    "SELECT 'raw_events=' || count(*) FROM raw.events",
)


def _compose(project: str | None = None) -> list[str]:
    args = [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "-f",
        str(COMPOSE_FILE),
        "--profile",
        "core",
    ]
    if project:
        args.extend(("-p", project))
    return args


def _run(label: str, args: list[str], *, env: dict[str, str], stdin: IO[bytes] | None = None) -> str:
    result = subprocess.run(args, cwd=ROOT, env=env, stdin=stdin, capture_output=True, check=False)  # noqa: S603
    if result.returncode:
        raise RuntimeError(f"{label} failed (exit {result.returncode})")
    return result.stdout.decode("utf-8", errors="strict").strip()


def _sql(project: str | None, query: str, env: dict[str, str]) -> str:
    return _run(
        "database comparison query",
        [
            *_compose(project),
            "exec",
            "-T",
            "postgres",
            "sh",
            "-c",
            'psql -X -A -t -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"',
            "drill",
            query,
        ],
        env=env,
    )


def _snapshot(project: str | None, env: dict[str, str]) -> tuple[str, ...]:
    head = _sql(project, "SELECT version_num FROM alembic_version", env)
    counts = tuple(_sql(project, statement, env) for statement in COUNTS)
    return (head, *counts)


def main() -> int:
    env = os.environ.copy()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        restore_port = str(probe.getsockname()[1])
    env["POSTGRES_HOST_PORT"] = restore_port
    project = f"deliveriq-t21-restore-{uuid.uuid4().hex[:10]}"
    created = False
    try:
        source = _snapshot(None, env)
        with tempfile.TemporaryDirectory(prefix="deliveriq-t21-backup-") as tmp:
            archive = Path(tmp) / "database.dump"
            with archive.open("wb") as output:
                dump = subprocess.run(  # noqa: S603
                    [
                        *_compose(),
                        "exec",
                        "-T",
                        "postgres",
                        "sh",
                        "-c",
                        'pg_dump --format=custom -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=output,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if dump.returncode:
                    raise RuntimeError(f"pg_dump failed (exit {dump.returncode})")
            created = True
            _run(
                "start isolated restore database",
                [*_compose(project), "up", "-d", "--wait", "postgres"],
                env=env,
            )
            with archive.open("rb") as input_stream:
                _run(
                    "pg_restore",
                    [
                        *_compose(project),
                        "exec",
                        "-T",
                        "postgres",
                        "sh",
                        "-c",
                        'pg_restore --exit-on-error --no-owner --no-acl -U "$POSTGRES_USER" '
                        '-d "$POSTGRES_DB"',
                    ],
                    env=env,
                    stdin=input_stream,
                )
            restored = _snapshot(project, env)
            if restored != source:
                raise RuntimeError("restored migration head or selected row counts do not match the source")
            print("Backup/restore drill passed")
            print(f"Migration head: {source[0]}")
            print("Row counts: " + ", ".join(source[1:]))
    finally:
        if created:
            _run(
                "remove isolated restore project",
                [*_compose(project), "down", "-v", "--remove-orphans"],
                env=env,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
