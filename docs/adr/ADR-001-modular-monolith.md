# ADR-001 Modular monolith boundaries

**Status:** Accepted · **Date:** 2026-11-12

## Context
Four portals, data pipelines and five AI harnesses must run on one 16 GB laptop and stay reviewable. Microservices would multiply containers, RAM and deployment work (Phase 1 ADR-001, Requirements spec).

## Decision
One FastAPI codebase for API, worker and CLI, split into business modules (`backend/app/modules/<domain>`) with thin layers: `api`, `schemas`, `service`, `domain`, `repository`, `models`, `permissions`. Pipelines and AI harnesses are separate packages. Layout per `CODE_STRUCTURE_DESIGN.md`.

## Consequences
- One deploy unit and one database; transactions span modules where needed through services.
- Boundaries must be enforced by tooling (ADR-CODE-001), not convention.
- A module can be extracted later because it owns its routes, services and tables.

## References
DDR-80; `CODE_STRUCTURE_DESIGN.md` §2–4; Phase 1 (#16) ADR-001.
