# ADR-009 Per-portal RAG schemas and DB roles

**Status:** Accepted · **Date:** 2026-11-12

## Context
Customer, Kitchen and Management knowledge must never leak across portals (#12 §9, #3, #6, #9).

## Decision
Three schemas (`customer_rag`, `kitchen_rag`, `management_rag`), each read and written only through its own DB role (`rag_customer`, `rag_kitchen`, `rag_management`). Ingestion jobs K1–K3 and each harness's retrieval connect with that role. import-linter forbids a harness importing another harness's retrieval code.

## Consequences
- Isolation holds even if application code has a bug.
- Tests prove a Kitchen job cannot write `customer_rag` and Management cannot query other collections.
- Shared embedding/retrieval code is parameterized by role and schema.

## References
DDR-63, DDR-80; `RAG_AI_DESIGN.md` §2, §7; `DATA_PIPELINE_DESIGN.md` §3.
