# ADR-002 PostgreSQL only; no MongoDB

**Status:** Accepted · **Date:** 2026-11-12

## Context
Phase 1 (#16) listed MongoDB "to verify"; the Requirements spec baseline excludes it. The system needs relational integrity, geospatial queries and vectors.

## Decision
PostgreSQL is the only database, with PostGIS (locations, distance) and pgvector (RAG). MongoDB is not used.

## Consequences
- One backup, one migration tool (Alembic), one set of DB roles.
- Document-like data uses `jsonb` columns where needed.
- No document-store use case has been identified; revisiting needs a new DDR.

## References
DDR-27; Requirements spec §1.2; source conflict X-08.
