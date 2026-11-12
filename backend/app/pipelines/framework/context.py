"""Run context: the only way a stage records progress, errors and quality results (DDR-63).

Records are written on a separate autocommit connection, so the UI sees progress while the data
transaction of a stage is still open, and failed data work never erases the run history.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Connection, text


class DataError(Exception):
    """Bad input or failed quality rule: the run fails and is never retried (DDR-67 rule 1)."""


class StructuralError(DataError):
    """Input structure is unusable: the run fails and nothing loads (DDR-67 rule 3)."""


class TransientError(Exception):
    """Infrastructure hiccup (connection, I/O): retried with backoff (DDR-67 rule 1, DDR-105)."""


class CancelledError(Exception):
    """Cancel requested; raised at a stage boundary (DDR-67 rule 6)."""


@dataclass
class StageCounts:
    rows_in: int | None = None
    rows_out: int | None = None
    rows_rejected: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunContext:
    run_id: uuid.UUID
    pipeline: str
    is_test: bool
    input_ref: str | None
    records: Connection  # autocommit, pipeline role: run/stage/error/dq rows
    data: Connection  # pipeline role: the stage's data work
    quarantined: int = 0
    counts: dict[str, Any] = field(default_factory=dict)
    _seq: int = 0

    def check_cancel(self) -> None:
        requested = self.records.execute(
            text("SELECT cancel_requested FROM ops.pipeline_runs WHERE id = :id"), {"id": self.run_id}
        ).scalar_one()
        if requested:
            raise CancelledError

    @contextmanager
    def stage(self, name: str) -> Iterator[StageCounts]:
        """Record a stage; stops at its start if a cancel is pending (stage boundary)."""
        self.check_cancel()
        self._seq += 1
        seq = self._seq
        self.records.execute(
            text(
                "INSERT INTO ops.pipeline_stage_runs (run_id, seq, stage, status, started_at) "
                "VALUES (:r, :s, :n, 'running', now())"
            ),
            {"r": self.run_id, "s": seq, "n": name},
        )
        counts = StageCounts()
        started = time.perf_counter()
        status = "failed"
        try:
            yield counts
            status = "succeeded"
        except CancelledError:
            status = "cancelled"
            raise
        finally:
            counts.detail.setdefault("duration_ms", round((time.perf_counter() - started) * 1000, 1))
            self.records.execute(
                text(
                    "UPDATE ops.pipeline_stage_runs SET status = :st, rows_in = :i, rows_out = :o, "
                    "rows_rejected = :x, detail = CAST(:d AS jsonb), finished_at = now() "
                    "WHERE run_id = :r AND seq = :s"
                ),
                {
                    "st": status,
                    "i": counts.rows_in,
                    "o": counts.rows_out,
                    "x": counts.rows_rejected,
                    "d": json.dumps(counts.detail, default=str),
                    "r": self.run_id,
                    "s": seq,
                },
            )

    def error(self, stage: str, record_ref: str | None, reason_code: str, message: str) -> None:
        self.quarantined += 1
        self.records.execute(
            text(
                "INSERT INTO ops.ingestion_errors (run_id, stage, record_ref, reason_code, message) "
                "VALUES (:r, :s, :ref, :c, :m)"
            ),
            {"r": self.run_id, "s": stage, "ref": record_ref, "c": reason_code, "m": message[:2000]},
        )

    def dq(self, check: str, severity: str, passed: bool, failures: int, detail: dict[str, Any]) -> None:
        self.records.execute(
            text(
                "INSERT INTO ops.dq_results (run_id, check_name, severity, status, failures, detail) "
                "VALUES (:r, :c, :sev, :st, :f, CAST(:d AS jsonb))"
            ),
            {
                "r": self.run_id,
                "c": check,
                "sev": severity,
                "st": "pass" if passed else "fail",
                "f": failures,
                "d": json.dumps(detail, default=str),
            },
        )

    def save_report(self, markdown: str) -> None:
        self.records.execute(
            text("UPDATE ops.pipeline_runs SET report_md = :m WHERE id = :id"),
            {"m": markdown, "id": self.run_id},
        )
