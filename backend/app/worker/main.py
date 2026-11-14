"""Single heartbeating worker: polls the job queue, runs one job at a time (DDR-63, DDR-105)."""

from __future__ import annotations

import logging
import os
import signal
import socket
import sys
import threading
import time
import uuid
from types import FrameType

from sqlalchemy import Connection, text

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.logging import configure_logging
from app.pipelines.framework import queue, runner
from app.pipelines.framework.context import TransientError
from app.pipelines.p2_elt import landing

POLL_SECONDS = 2
HEARTBEAT_SECONDS = 10
# Delivery jobs (DDR-113 (2), (11), (17)): narrow database functions, the worker role holds EXECUTE only.
OFFER_SWEEP_SECONDS = 10
RETENTION_SECONDS = 24 * 60 * 60
PURGE_DAYS = 30  # DL-16 history; DDR-115 (11), (12)

_log = logging.getLogger("app.worker")


class Worker:
    def __init__(self) -> None:
        self.worker_id = f"{socket.gethostname()}-{os.getpid()}"
        self.stopping = threading.Event()
        self.current: uuid.UUID | None = None

    def _autocommit(self) -> Connection:
        return get_engine().connect().execution_options(isolation_level="AUTOCOMMIT")

    def _heartbeats(self) -> None:
        while not self.stopping.wait(HEARTBEAT_SECONDS):
            try:
                with self._autocommit() as conn:
                    queue.heartbeat(conn, self.worker_id, self.current)
            except Exception:
                _log.warning("heartbeat failed", exc_info=True)

    def _delivery_jobs(self) -> None:
        next_retention = 0.0
        while not self.stopping.wait(OFFER_SWEEP_SECONDS):
            try:
                with get_engine().begin() as conn:
                    expired = conn.execute(text("SELECT app.expire_and_reoffer()")).scalar_one()
                if expired:
                    _log.info("offers expired", extra={"count": expired})
                # DDR-116 (9): the optional P2 timer (off by default); queues a due run, never two.
                with get_engine().begin() as conn:
                    queued = conn.execute(text("SELECT ops.queue_due_schedules()")).scalar_one()
                if queued:
                    _log.info("scheduled runs queued", extra={"count": queued})
                if time.monotonic() >= next_retention:
                    # NULL = the configured GPS_RETENTION_DAYS (30, DDR-43).
                    with get_engine().begin() as conn:
                        deleted = conn.execute(text("SELECT app.purge_delivery_locations(NULL)")).scalar_one()
                    _log.info("gps retention", extra={"deleted": deleted})
                    # DDR-115 (11), (12): notification history and OTP/session records, 30 days.
                    with get_engine().begin() as conn:
                        notes = conn.execute(
                            text("SELECT app.purge_notifications(:d)"), {"d": PURGE_DAYS}
                        ).scalar_one()
                        auth = conn.execute(text("SELECT app.purge_auth(:d)"), {"d": PURGE_DAYS}).scalar_one()
                    _log.info("retention", extra={"notifications": notes, **auth})
                    next_retention = time.monotonic() + RETENTION_SECONDS
            except Exception:
                _log.warning("delivery job failed", exc_info=True)

    def _landing(self) -> None:
        """P2 landing, continuous and independent of queued jobs (DATA_PIPELINE §11; DDR-116 (6))."""
        while not self.stopping.wait(landing.POLL_SECONDS):
            try:
                while True:  # drain the backlog in batches, then wait
                    with runner.role_engine("p2_elt").begin() as conn:
                        result = landing.land_batch(conn)
                    if result.accepted or result.rejected:
                        _log.info("events landed", extra=result.__dict__)
                    if result.accepted + result.rejected + result.duplicates < landing.BATCH_MAX:
                        break
            except Exception:
                _log.warning("landing failed; retrying", exc_info=True)

    def stop(self, signum: int, _frame: FrameType | None) -> None:
        _log.info("stopping after the current job", extra={"signal": signum})
        self.stopping.set()

    def run(self) -> None:
        with self._autocommit() as conn:
            queue.register_worker(conn, self.worker_id)
        threading.Thread(target=self._heartbeats, name="heartbeat", daemon=True).start()
        threading.Thread(target=self._delivery_jobs, name="delivery-jobs", daemon=True).start()
        threading.Thread(target=self._landing, name="p2-landing", daemon=True).start()
        _log.info("worker started", extra={"worker_id": self.worker_id})
        while not self.stopping.is_set():
            try:
                self.tick()
            except Exception:
                _log.exception("worker loop error; continuing")
                self.stopping.wait(POLL_SECONDS)

    def tick(self) -> None:
        with get_engine().begin() as conn:
            queue.release_stale(conn)
            job = queue.claim(conn, self.worker_id)
        if job is None:
            self.stopping.wait(POLL_SECONDS)
            return
        self.current = job.run_id
        _log.info("job started", extra={"run_id": str(job.run_id), "attempt": job.attempts})
        try:
            status = runner.execute(job.run_id)
            _log.info("job finished", extra={"run_id": str(job.run_id), "status": status})
        except TransientError as exc:
            with get_engine().begin() as conn:
                outcome = queue.retry_or_fail(conn, job, str(exc))
            _log.warning("job transient failure", extra={"run_id": str(job.run_id), "outcome": outcome})
        finally:
            self.current = None


def healthy() -> bool:
    """Container health: a worker on this host heartbeated recently (DOCKER_DEPLOYMENT_DESIGN §8)."""
    with get_engine().connect() as conn:
        return queue.recent_heartbeat(conn, socket.gethostname(), 3 * HEARTBEAT_SECONDS)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["--health"]:
        return 0 if healthy() else 1
    configure_logging(get_settings().log_level)
    worker = Worker()
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run()
    return 0
