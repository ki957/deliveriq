"""Single heartbeating worker: polls the job queue, runs one job at a time (DDR-63, DDR-105)."""

from __future__ import annotations

import logging
import os
import signal
import socket
import sys
import threading
import uuid
from types import FrameType

from sqlalchemy import Connection

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.logging import configure_logging
from app.pipelines.framework import queue, runner
from app.pipelines.framework.context import TransientError

POLL_SECONDS = 2
HEARTBEAT_SECONDS = 10

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

    def stop(self, signum: int, _frame: FrameType | None) -> None:
        _log.info("stopping after the current job", extra={"signal": signum})
        self.stopping.set()

    def run(self) -> None:
        with self._autocommit() as conn:
            queue.register_worker(conn, self.worker_id)
        threading.Thread(target=self._heartbeats, name="heartbeat", daemon=True).start()
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
