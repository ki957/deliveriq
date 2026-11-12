"""Exit-code tests for the source registry CLI (uses throwaway sample files only)."""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

from app.cli.source_registry import main
from app.shared.tests.test_source_registry import SampleTreeTestCase


class CliTests(SampleTreeTestCase):
    def _run(self, *args: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue() + err.getvalue()

    def _sample_args(self, *extra: str) -> list[str]:
        return ["--root", str(self.root), "--inventory", str(self.inventory_path), *extra]

    def test_exit_zero_when_all_match(self) -> None:
        code, output = self._run(*self._sample_args("--expect-count", "2"))
        self.assertEqual(code, 0, output)
        self.assertIn("PASS", output)

    def test_exit_one_on_mismatch(self) -> None:
        (self.root / "alpha/one.md").write_bytes(b"changed\n")
        code, output = self._run(*self._sample_args("--expect-count", "2"))
        self.assertEqual(code, 1, output)
        self.assertIn("HASH_MISMATCH", output)

    def test_json_output_reports_status(self) -> None:
        code, output = self._run(*self._sample_args("--expect-count", "2", "--json"))
        self.assertEqual(code, 0, output)
        self.assertIn('"ok": true', output)

    def test_exit_two_on_unexpected_row_count(self) -> None:
        code, output = self._run(*self._sample_args())
        self.assertEqual(code, 2, output)

    def test_exit_two_on_missing_root(self) -> None:
        code, _ = self._run(
            "--root", str(self.root / "nope"), "--inventory", str(self.inventory_path), "--expect-count", "2"
        )
        self.assertEqual(code, 2)
