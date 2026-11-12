"""Source registry: verify source files against the values recorded in the inventory.

This module does hash verification only. Content validation (recipe parsing,
reconciliation) is a separate concern (KITCHEN_SOURCE_VALIDATION.md, P1 pipeline).

The expected values are read directly from the tables in
docs/SOURCE_DOCUMENT_INVENTORY.md (sections 2 and 3), so the inventory stays the
single record of truth. Standard library only, so it runs in CI before the
backend environment exists (Task 0).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath

_CHUNK_SIZE = 1 << 16

# Matches inventory rows such as:
# | 13 | `kitchen/original/Kitchen_SOP_Manual_Token_Friendly.md` | ... | 106671 | 1599 | `7ee6...` |
_INVENTORY_ROW = re.compile(
    r"^\|\s*(?P<number>\d+)\s*\|\s*`(?P<path>[^`]+)`\s*\|.*"
    r"\|\s*(?P<size>\d+)\s*\|\s*(?P<lines>\d+)\s*\|\s*`(?P<sha256>[0-9a-f]{64})`\s*\|\s*$"
)


class InventoryError(ValueError):
    """The inventory could not be parsed into a valid list of expected sources."""


class Status(str, Enum):
    OK = "OK"
    MISSING = "MISSING"
    HASH_MISMATCH = "HASH_MISMATCH"
    # Hash matches but recorded size/line count differs: the inventory itself is wrong.
    METADATA_MISMATCH = "METADATA_MISMATCH"
    UNEXPECTED = "UNEXPECTED"


@dataclass(frozen=True)
class ExpectedSource:
    number: int
    path: str
    size: int
    lines: int
    sha256: str


@dataclass(frozen=True)
class ObservedSource:
    size: int
    lines: int
    sha256: str


@dataclass(frozen=True)
class CheckResult:
    path: str
    status: Status
    detail: str = ""


def _validate_relative_path(path: str) -> None:
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or path.strip() != path or not path:
        raise InventoryError(f"Unsafe or invalid source path in inventory: {path!r}")


def parse_inventory(text: str) -> list[ExpectedSource]:
    """Extract the expected sources from the inventory Markdown."""
    sources: list[ExpectedSource] = []
    seen_numbers: set[int] = set()
    seen_paths: set[str] = set()

    for line in text.splitlines():
        match = _INVENTORY_ROW.match(line.strip())
        if match is None:
            continue
        source = ExpectedSource(
            number=int(match["number"]),
            path=match["path"],
            size=int(match["size"]),
            lines=int(match["lines"]),
            sha256=match["sha256"],
        )
        _validate_relative_path(source.path)
        if source.number in seen_numbers:
            raise InventoryError(f"Duplicate inventory number: {source.number}")
        if source.path in seen_paths:
            raise InventoryError(f"Duplicate inventory path: {source.path}")
        seen_numbers.add(source.number)
        seen_paths.add(source.path)
        sources.append(source)

    if not sources:
        raise InventoryError("No source rows found in the inventory")
    return sources


def observe(file_path: Path) -> ObservedSource:
    """Compute SHA-256, byte size and newline count (same as `wc -l`)."""
    digest = hashlib.sha256()
    size = 0
    lines = 0
    with file_path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
            size += len(chunk)
            lines += chunk.count(b"\n")
    return ObservedSource(size=size, lines=lines, sha256=digest.hexdigest())


def _relative_files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() or p.is_symlink()}


def verify(root: Path, expected: list[ExpectedSource]) -> list[CheckResult]:
    """Check every expected source under `root` and report files not in the inventory."""
    results: list[CheckResult] = []

    for source in expected:
        file_path = root / source.path
        if file_path.is_symlink():
            results.append(CheckResult(source.path, Status.UNEXPECTED, "symlinks are not accepted"))
            continue
        if not file_path.is_file():
            results.append(CheckResult(source.path, Status.MISSING))
            continue

        observed = observe(file_path)
        if observed.sha256 != source.sha256:
            results.append(
                CheckResult(
                    source.path,
                    Status.HASH_MISMATCH,
                    f"expected {source.sha256}, got {observed.sha256}",
                )
            )
        elif (observed.size, observed.lines) != (source.size, source.lines):
            results.append(
                CheckResult(
                    source.path,
                    Status.METADATA_MISMATCH,
                    f"recorded size/lines {source.size}/{source.lines}, "
                    f"actual {observed.size}/{observed.lines}",
                )
            )
        else:
            results.append(CheckResult(source.path, Status.OK))

    expected_paths = {source.path for source in expected}
    if root.is_dir():
        for extra in sorted(_relative_files(root) - expected_paths):
            results.append(CheckResult(extra, Status.UNEXPECTED, "not listed in the inventory"))

    return results


def all_ok(results: list[CheckResult]) -> bool:
    return all(result.status is Status.OK for result in results)
