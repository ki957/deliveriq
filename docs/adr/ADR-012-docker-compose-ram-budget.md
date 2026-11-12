# ADR-012 Docker Compose with profiles; RAM budget

**Status:** Accepted · **Date:** 2026-11-12

## Context
The target laptop has 16 GB RAM with about 8 GB available for containers. Kubernetes is out of scope (Requirements spec).

## Decision
Docker Compose with profiles: `core` (postgres, redis, migrate, api), `worker`, `osrm` (+`osrm-prep`), `e2e`, `demo` (`web`), `agent` (+`egress-proxy`). Only `core` runs daily; heavy profiles start on demand and never overlap. Starting limits: postgres 768 MB, redis 128 MB, api 512 MB, worker 1.2 GB, osrm 1 GB, e2e 2 GB, agent 1 GB / 1 CPU, adjusted after `docker stats` measurement. Vite runs on the host in dev.

## Consequences
- PostgreSQL and Redis are tuned small (DDR-62).
- Heavy E2E and visual suites also run in GitHub Actions.
- Memory is measured at every milestone gate.

## References
DDR-62; `DOCKER_DEPLOYMENT_DESIGN.md` §3–4.
