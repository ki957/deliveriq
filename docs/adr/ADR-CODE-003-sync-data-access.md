# ADR-CODE-003 Sync data access; async only for WebSockets, Redis and outbound HTTP

**Status:** Accepted · **Date:** 2026-11-12

## Context
API, worker and CLI share the same services. Fully async or mixed data access adds complexity without a measured need.

## Decision
Sync SQLAlchemy 2.x with psycopg 3 for repositories and services; one session per request, job or command; transaction boundaries in services. Async only for WebSockets, Redis pub/sub and outbound HTTP (httpx to LLM providers and OSRM). CPU-heavy embedding runs only in the worker.

## Consequences
- One code path for API, worker and CLI.
- FastAPI runs sync endpoints in its threadpool.

## References
DDR-82; `CODE_STRUCTURE_DESIGN.md` §10.
