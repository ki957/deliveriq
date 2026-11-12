# ADR-AI-001 Read-only AI except Operational Actions and Builder Agent

**Status:** Accepted · **Date:** 2026-11-12

## Context
The RAG specs (#3, #6, #9, #12, #21) make every AI harness read-only. The SOP's Kitchen AI stock command (`<dish> x <portions>`) would let AI change stock. The owner wanted Management to act like a "mini Claude Code".

## Decision
- Customer Assistant, Kitchen Copilot and Management Copilot are read-only.
- The SOP AI stock-deduction command is excluded from the MVP (DDR-18).
- Two CA-only harnesses are a deliberate, owner-approved deviation: Operational Actions (typed, confirmed, audited; ADR-AI-003) and Builder Agent (sandboxed, PR-only; ADR-AI-002).
- Delivery has no AI.

## Consequences
- Model output never writes data directly.
- The source prohibitions keep binding the three Copilots.

## References
DDR-18, DDR-68; Matrix §10.
