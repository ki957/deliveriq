# ADR-007 Provider-neutral model gateway

**Status:** Accepted · **Date:** 2026-11-12 (supersedes the earlier "Groq direct; OpenRouter deferred" proposal, DDR-26)

## Context
The owner uses a Groq free-tier key now and wants to switch to OpenRouter or another provider later without code changes.

## Decision
One OpenAI-compatible adapter plus a mock adapter. Providers, logical models (`fast`, `strong`, `guard`), capabilities and harness routing live in `backend/config/ai_models.yaml`; keys only in `.env`. Defaults: `openai/gpt-oss-20b` for Copilots and Operational Actions, `openai/gpt-oss-120b` for the Builder Agent. The CA can switch a harness to another configured model in "AI settings"; the switch is capability-checked, audited and applied without restart. The UI never adds providers or keys.

## Consequences
- Harness code contains no provider or model IDs.
- Startup fails if a route lacks a required capability.
- Builder Agent egress allowlist = GitHub + configured provider hosts.

## References
DDR-85, DDR-86, DDR-87; `RAG_AI_DESIGN.md` §4.
