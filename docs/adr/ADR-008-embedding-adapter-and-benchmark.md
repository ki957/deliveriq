# ADR-008 Embedding adapter and selection by benchmark

**Status:** Accepted · **Date:** 2026-11-12

## Context
#12 and #20 require the embedding model to be chosen by evidence. The owner wants multi-provider support without mixing vectors.

## Decision
`Embedder` interface with a local int8 ONNX default, an optional remote OpenAI-compatible embedder (config only) and a mock for CI. Candidates `bge-small-en-v1.5`, `e5-small-v2`, `gte-small`, `all-MiniLM-L6-v2` are benchmarked in the worker container. Pass bar: Recall@5 ≥ 0.85, p95 ≤ 50 ms, added RSS ≤ 300 MB. Best Recall@5 among passing models wins; tie → lower RSS; none pass → owner decides.

## Consequences
- The vector dimension is fixed only after the benchmark report.
- Each index records its model; changing models means a versioned re-index with atomic swap. No runtime switch.

## References
DDR-45, DDR-57, DDR-88, DDR-89; `RAG_AI_DESIGN.md` §5.
