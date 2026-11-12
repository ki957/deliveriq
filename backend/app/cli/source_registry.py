"""CLI: verify source files against SOURCE_DOCUMENT_INVENTORY.md.

Usage (from the repo root):
    PYTHONPATH=backend python -m app.cli.source_registry \
        --root data/source --inventory docs/SOURCE_DOCUMENT_INVENTORY.md

Exit codes: 0 all files match, 1 any mismatch, 2 inventory or argument error.
Writing results to ops.source_registry is added with the pipeline framework (Task 5).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.shared.source_registry import (
    InventoryError,
    Status,
    all_ok,
    parse_inventory,
    verify,
)

EXPECTED_SOURCE_COUNT = 21


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify source files against the inventory hashes.")
    parser.add_argument("--root", type=Path, required=True, help="Directory holding the source files")
    parser.add_argument("--inventory", type=Path, required=True, help="Path to SOURCE_DOCUMENT_INVENTORY.md")
    parser.add_argument(
        "--expect-count",
        type=int,
        default=EXPECTED_SOURCE_COUNT,
        help="Number of inventory rows expected (guards against parse regressions)",
    )
    parser.add_argument("--json", action="store_true", help="Print results as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        expected = parse_inventory(args.inventory.read_text(encoding="utf-8"))
    except (OSError, InventoryError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if len(expected) != args.expect_count:
        print(
            f"error: inventory lists {len(expected)} sources, expected {args.expect_count}",
            file=sys.stderr,
        )
        return 2

    if not args.root.is_dir():
        print(f"error: source root not found: {args.root}", file=sys.stderr)
        return 2

    results = verify(args.root, expected)
    ok = all_ok(results)

    if args.json:
        payload = {
            "ok": ok,
            "checked": len(expected),
            "results": [{"path": r.path, "status": r.status.value, "detail": r.detail} for r in results],
        }
        print(json.dumps(payload, indent=2))
    else:
        for result in results:
            suffix = f"  ({result.detail})" if result.detail else ""
            print(f"{result.status.value:<18} {result.path}{suffix}")
        matched = sum(1 for r in results if r.status is Status.OK)
        print(f"\n{matched}/{len(expected)} sources match the inventory; {'PASS' if ok else 'FAIL'}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
