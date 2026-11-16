"""Host-side worker for the CA-confirmed Builder Agent queue."""

from __future__ import annotations

import signal
import time

from app.modules.ai.builder_agent.service import process_next_job

_running = True


def _stop(_signum: int, _frame: object) -> None:
    global _running
    _running = False


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    while _running:
        if not process_next_job():
            time.sleep(1)


if __name__ == "__main__":
    main()
