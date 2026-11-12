"""Tests for the source registry (Task 0).

Unit tests use small throwaway files, never SOP or source content.
The last test class checks the real committed copies in data/source/ against the
real inventory, which is the Task 0 acceptance check.
"""

from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from app.cli.source_registry import main
from app.shared.source_registry import (
    InventoryError,
    Status,
    all_ok,
    observe,
    parse_inventory,
    verify,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
INVENTORY = REPO_ROOT / "docs" / "SOURCE_DOCUMENT_INVENTORY.md"
SOURCE_COPIES = REPO_ROOT / "data" / "source"

SAMPLE_FILES = {
    "alpha/one.md": b"line one\nline two\n",
    "beta/name with space (1).md": b"single line\n",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inventory_for(files: dict[str, bytes]) -> str:
    rows = [
        "| # | Relative path | Type | Read | Bytes | Lines | SHA-256 |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for number, (path, data) in enumerate(files.items(), start=1):
        rows.append(
            f"| {number} | `{path}` | Test | Complete | {len(data)} | {data.count(b'\n')} | `{_sha(data)}` |"
        )
    return "\n".join(rows) + "\n"


class SampleTreeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "sources"
        for path, data in SAMPLE_FILES.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        self.inventory_path = Path(self._tmp.name) / "inventory.md"
        self.inventory_path.write_text(_inventory_for(SAMPLE_FILES), encoding="utf-8")
        self.expected = parse_inventory(self.inventory_path.read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        self._tmp.cleanup()


class ParseInventoryTests(unittest.TestCase):
    def test_parses_rows_and_ignores_other_tables(self) -> None:
        text = _inventory_for(SAMPLE_FILES) + "\n| 1 | Customer_Dashboard | some summary | #2 | 4 | Yes |\n"
        expected = parse_inventory(text)
        self.assertEqual([s.path for s in expected], list(SAMPLE_FILES))

    def test_rejects_empty_inventory(self) -> None:
        with self.assertRaises(InventoryError):
            parse_inventory("# nothing here\n")

    def test_rejects_duplicate_paths(self) -> None:
        row = _inventory_for({"a.md": b"x\n"}).splitlines()[-1]
        duplicate = row.replace("| 1 |", "| 2 |", 1)
        with self.assertRaises(InventoryError):
            parse_inventory(f"{row}\n{duplicate}\n")

    def test_rejects_path_traversal(self) -> None:
        text = _inventory_for({"../escape.md": b"x\n"})
        with self.assertRaises(InventoryError):
            parse_inventory(text)

    def test_rejects_absolute_path(self) -> None:
        text = _inventory_for({"/etc/passwd": b"x\n"})
        with self.assertRaises(InventoryError):
            parse_inventory(text)


class ObserveTests(unittest.TestCase):
    def test_counts_newlines_like_wc_l(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.md"
            path.write_bytes(b"a\nb\nno trailing newline")
            observed = observe(path)
        self.assertEqual(observed.lines, 2)
        self.assertEqual(observed.size, 23)
        self.assertEqual(observed.sha256, _sha(b"a\nb\nno trailing newline"))


class VerifyTests(SampleTreeTestCase):
    def test_unmodified_tree_passes(self) -> None:
        results = verify(self.root, self.expected)
        self.assertTrue(all_ok(results), results)
        self.assertEqual(len(results), len(SAMPLE_FILES))

    def test_single_byte_change_is_detected(self) -> None:
        target = self.root / "alpha/one.md"
        target.write_bytes(b"line one\nline twO\n")
        statuses = {r.path: r.status for r in verify(self.root, self.expected)}
        self.assertIs(statuses["alpha/one.md"], Status.HASH_MISMATCH)

    def test_missing_file_is_detected(self) -> None:
        (self.root / "alpha/one.md").unlink()
        statuses = {r.path: r.status for r in verify(self.root, self.expected)}
        self.assertIs(statuses["alpha/one.md"], Status.MISSING)

    def test_extra_file_is_detected(self) -> None:
        (self.root / "alpha/extra.md").write_bytes(b"not in inventory\n")
        statuses = {r.path: r.status for r in verify(self.root, self.expected)}
        self.assertIs(statuses["alpha/extra.md"], Status.UNEXPECTED)

    def test_symlink_is_rejected(self) -> None:
        target = self.root / "alpha/one.md"
        real = self.root.parent / "outside.md"
        real.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(real)
        statuses = {r.path: r.status for r in verify(self.root, self.expected)}
        self.assertIs(statuses["alpha/one.md"], Status.UNEXPECTED)

    def test_wrong_recorded_metadata_is_reported(self) -> None:
        data = SAMPLE_FILES["alpha/one.md"]
        text = self.inventory_path.read_text(encoding="utf-8").replace(
            f"| {len(data)} | {data.count(b'\n')} |", f"| {len(data) + 1} | {data.count(b'\n')} |", 1
        )
        statuses = {r.path: r.status for r in verify(self.root, parse_inventory(text))}
        self.assertIs(statuses["alpha/one.md"], Status.METADATA_MISMATCH)


class CliTests(SampleTreeTestCase):
    def _run(self, *args: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue() + err.getvalue()

    def test_exit_zero_when_all_match(self) -> None:
        code, output = self._run(
            "--root", str(self.root), "--inventory", str(self.inventory_path), "--expect-count", "2"
        )
        self.assertEqual(code, 0, output)
        self.assertIn("PASS", output)

    def test_exit_one_on_mismatch(self) -> None:
        (self.root / "alpha/one.md").write_bytes(b"changed\n")
        code, output = self._run(
            "--root", str(self.root), "--inventory", str(self.inventory_path), "--expect-count", "2"
        )
        self.assertEqual(code, 1, output)
        self.assertIn("HASH_MISMATCH", output)

    def test_exit_two_on_unexpected_row_count(self) -> None:
        code, output = self._run("--root", str(self.root), "--inventory", str(self.inventory_path))
        self.assertEqual(code, 2, output)

    def test_exit_two_on_missing_root(self) -> None:
        code, _ = self._run(
            "--root", str(self.root / "nope"), "--inventory", str(self.inventory_path), "--expect-count", "2"
        )
        self.assertEqual(code, 2)


class RealInventoryTests(unittest.TestCase):
    """Acceptance: the committed copies match the recorded inventory exactly."""

    def test_inventory_lists_21_sources(self) -> None:
        expected = parse_inventory(INVENTORY.read_text(encoding="utf-8"))
        self.assertEqual(len(expected), 21)

    @unittest.skipUnless(SOURCE_COPIES.is_dir(), "data/source not present")
    def test_committed_copies_match_inventory(self) -> None:
        expected = parse_inventory(INVENTORY.read_text(encoding="utf-8"))
        results = verify(SOURCE_COPIES, expected)
        failures = [r for r in results if r.status is not Status.OK]
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
