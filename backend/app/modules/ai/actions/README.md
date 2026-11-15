# Operational Actions Assistant

1. Purpose: Central Admin proposes a typed operational change, previews it, then confirms it.
2. Sources: allowlisted action contracts and read models; no RAG.
3. Ingestion: none.
4. Chunking: none.
5. Embeddings: none.
6. Retrieval: none.
7. Prompt/model: `prompt.md`, fast logical model; mock proposal adapter in local/test.
8. Output: persisted exact change preview, confirmation key, underlying service write, audit.
9. Evaluation: 15 valid and 10 must-refuse proposals; integration and E2E checks.
10. Security: CA only. No excluded tools. Refund, promotion, review and regional settings are unavailable (DDR-120). TEST menu items only. Copilot remains read-only.
