# ADR-CODE-002 OpenAPI-generated TypeScript client

**Status:** Accepted · **Date:** 2026-11-12

## Context
Hand-written frontend types drift from the API.

## Decision
FastAPI Pydantic schemas → OpenAPI → `openapi-typescript` → `frontend/src/shared/api/generated`, committed. CI regenerates the client and fails if the committed copy differs.

## Consequences
- Contract changes are visible in PR diffs.
- Backend schema changes require regenerating the client in the same PR.

## References
DDR-81; `CODE_STRUCTURE_DESIGN.md` §9.
