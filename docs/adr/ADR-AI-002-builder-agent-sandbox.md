# ADR-AI-002 Builder Agent sandbox

**Status:** Accepted · **Date:** 2026-11-12

## Context
A CA-only agent that writes code must not be able to damage the live system, leak secrets or approve its own changes.

## Decision
An on-demand container in the `agent` Compose profile, started manually with `make agent` (no Docker socket in any app container). It works on a throwaway repo copy on tmpfs, has no route to Postgres or Redis and no `.env`, and reaches only GitHub and the configured LLM provider hosts through an allowlisting proxy. 1 GB / 1 CPU; destroyed after each task. Flow: change → unit tests in sandbox → CA reviews diff → PR → CI → owner merges. Protected paths (prompts, policies, guardrails, RBAC, `ai_models.yaml`, `.github/`, `infra/`, `.env*`) are read-only and rejected again by a diff check. Untrusted content never enters its context.

## Consequences
- The agent never merges or pushes to `main` (branch protection required).
- Playwright runs only in CI, not in the sandbox.

## References
DDR-70, DDR-71, DDR-85, DDR-87; `DOCKER_DEPLOYMENT_DESIGN.md` §10; `RAG_AI_DESIGN.md` §12.3, §14.
