# ADR-CODE-001 Module boundaries enforced with import-linter

**Status:** Accepted · **Date:** 2026-11-12

## Context
A modular monolith (ADR-001) erodes if dependency rules are only conventions.

## Decision
`import-linter` contracts run in CI: `domain` uses the standard library only; pipelines, worker and CLI call module services, not repositories; a harness never imports another harness or another portal's `*_rag` code; `ai/shared` imports only `core`.

## Consequences
- Boundary violations fail the build.
- Access isolation (e.g. Customer harness cannot import Kitchen retrieval) becomes a structural, testable property.

## References
DDR-80; `CODE_STRUCTURE_DESIGN.md` §4.
