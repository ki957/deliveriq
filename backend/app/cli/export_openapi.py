"""Export or check the committed OpenAPI schema (DDR-81 contract drift check).

    PYTHONPATH=backend python -m app.cli.export_openapi --write   # update backend/openapi.json
    PYTHONPATH=backend python -m app.cli.export_openapi --check   # exit 1 if it is out of date

The TypeScript client generated from this schema is added with the frontend scaffold (Task 4).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.main import openapi_app

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "openapi.json"


def render() -> str:
    return json.dumps(openapi_app().openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)

    current = render()
    if args.write:
        args.path.write_text(current, encoding="utf-8")
        print(f"wrote {args.path}")
        return 0

    committed = args.path.read_text(encoding="utf-8") if args.path.exists() else ""
    if committed != current:
        message = f"OpenAPI schema is out of date: run `make openapi` and commit {args.path.name}"
        print(message, file=sys.stderr)
        return 1
    print("OpenAPI schema is up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
