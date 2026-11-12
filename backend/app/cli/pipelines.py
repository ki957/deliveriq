"""Queue a pipeline run from the host, the same entry point as the UI trigger (DATA_PIPELINE §11).

    make pipeline NAME=p1_sop
    # = docker compose ... exec -T api python -m app.cli.pipelines run p1_sop --wait

Runs as `app_api`, which may only insert the run and its queue row; the worker executes it as the
pipeline's own role. With --wait, polls until the run ends and exits 0 for "succeeded" or
"completed_with_quarantine", 1 otherwise (2 for a refused request).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence

from app.modules.pipelines import service

POLL_SECONDS = 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a DeliverIQ pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="queue a run")
    run.add_argument("name", help="pipeline name, e.g. p1_sop")
    run.add_argument(
        "--input", dest="input_ref", default=None, help="input reference (default: the pipeline's)"
    )
    run.add_argument("--wait", action="store_true", help="wait until the run ends")
    run.add_argument("--timeout", type=int, default=900, help="seconds to wait (default 900)")
    args = parser.parse_args(argv)

    try:
        run_id = service.trigger_from_cli(args.name, args.input_ref)
    except service.NotFound:
        print(f"refused: unknown pipeline {args.name}", file=sys.stderr)
        return 2
    except service.Conflict as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(f"queued {args.name} run {run_id}")
    if not args.wait:
        return 0

    deadline = time.monotonic() + args.timeout
    status = "queued"
    while time.monotonic() < deadline:
        current = service.run_status(run_id)
        if current.status != status:
            status = current.status
            print(f"status: {status}")
        if status in service.TERMINAL:
            print(json.dumps(current.counts, indent=2, sort_keys=True, default=str))
            if current.error_summary:
                print(f"error: {current.error_summary}")
            return 0 if status in ("succeeded", "completed_with_quarantine") else 1
        time.sleep(POLL_SECONDS)
    print(
        f"timed out after {args.timeout}s; run {run_id} is still {status} (is the worker running?)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
