# ADR-AI-004 Local CPU embeddings

**Status:** Accepted · **Date:** 2026-11-12

## Context
The laptop has no GPU budget for AI and limited RAM. Sending every knowledge chunk to a remote API adds cost and a dependency.

## Decision
A small English embedding model, int8 ONNX, runs on CPU inside the worker. It is lazy-loaded and released after ingestion; query embedding for live requests goes through the worker's internal endpoint. No local LLM is run. A remote embedder exists only as a config option (ADR-008).

## Consequences
- Estimated 150–250 MB RSS within the 1.2 GB worker limit (to be measured).
- If the worker is down, retrieval falls back to full-text search and is marked "reduced retrieval".

## References
DDR-57, DDR-88; `RAG_AI_DESIGN.md` §5, §18.
