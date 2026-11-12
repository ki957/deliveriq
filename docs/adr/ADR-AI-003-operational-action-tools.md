# ADR-AI-003 Operational Action tools

**Status:** Accepted · **Date:** 2026-11-12

## Context
The CA wants to run routine operations by chat without giving the model direct write access.

## Decision
Typed, allowlisted tools. The model only proposes; the backend validates through the same service and RBAC checks as the UI; the UI shows the exact change; the CA confirms; the service executes with an idempotency key; an audit row is written. **Allowed:** kitchen mode/capacity, agent assign/reassign, dish-unavailability approval, promotions, review moderation, exceptional refund approval (disabled until DDR-44 thresholds exist), regional settings, menu publication (TEST items only). **Excluded:** staff/role changes, RM creation and region assignment, AI provider/model settings, integrations, secrets, global YAML at runtime, customer suspension, refund overrides.

## Consequences
- Excluded actions are not registered as tools at all.
- No tool can change AI model routing (DDR-87).

## References
DDR-69, DDR-87, DDR-93; `RAG_AI_DESIGN.md` §12.2, §13.1.
