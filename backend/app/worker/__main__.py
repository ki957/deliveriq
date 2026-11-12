"""Worker entry point: `python -m app.worker` (DDR-63, DDR-105)."""

from app.worker.main import main

raise SystemExit(main())
