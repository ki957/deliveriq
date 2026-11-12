# Health module

**Purpose and scope:** liveness and readiness probes for Compose health checks and monitoring.

| Item | Value |
|---|---|
| UI screens | None |
| API endpoints | `GET /health/live` → 200 `{"status":"alive"}` · `GET /health/ready` → 200 when DB and Redis respond, else 503 with per-check `ok`/`unavailable` |
| Service functions | `check_database` (`SELECT 1`), `check_redis` (`PING`), `readiness` |
| Tables / events | None |
| Permissions | Public, no data returned beyond check status |
| States | ready, not_ready; failures are logged (redacted), never returned in detail |
| Tests | `tests/test_health.py` (unit, fake checks); `tests/test_ready_integration.py` (real Postgres + Redis, `integration` marker) |
| Assumptions | Migrations never run on API start; the `migrate` job runs first (DOCKER_DEPLOYMENT_DESIGN §8) |
