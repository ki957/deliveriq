# Embedding benchmark report

**Status:** Task 16B benchmark complete. The DDR-89 rule gives MiniLM L6 v2 as the provisional result, but no winner or vector dimension is recorded until the owner confirms it. The 90-case set remains draft and is not the DDR-90 golden set.

## Method and evidence

- Candidates: BGE small, E5 small, GTE small and MiniLM L6 v2, each run alone and sequentially in the built worker image with no host mounts.
- Dataset: `backend/test_inputs/embedding_benchmark_draft.json`, 90 source-grounded cases; SHA-256 `36b55d8302f49a9230dc66e8a473cf009a0ad40d15e69b30c1ebb1cb803ac1f3`. It is approved for benchmark use only and labelled “draft, not the DDR-90 golden set”.
- Quantization was completed before the measured process. Each run used ONNX Runtime `intra_op_num_threads=1`, `inter_op_num_threads=1`, sequential execution, `enable_cpu_mem_arena=False`, `RAYON_NUM_THREADS=1`, and ingestion batch size 16.
- Pass RSS is the process `VmRSS` after model load, five warm-ups and the query set, minus the same process's `VmRSS` before load. `VmHWM` ingestion peak and cgroup memory are information-only.
- The first worker build was cancelled while `dbt-core-experimental-parser==2.0.11` was building after ONNX Runtime and tokenizers were added. The fix was to allow the dependency build to complete; the final worker image contains the locked packages. The benchmark ran from that image with no host-mounted packages.
- Corrected rows are persisted in `ops.ai_eval_runs` / `ops.ai_eval_results` by migration 0026. The write path is through SECURITY DEFINER functions executable by `worker`.

## First run

The first run used the earlier RSS measurement, which did not implement the approved steady-state `VmRSS` definition. Its saved evidence contains no `VmHWM` or cgroup values.

| Candidate | Recall@5 | p95 ms | Added RSS MiB | VmHWM | cgroup | Dimension |
|---|---:|---:|---:|---:|---:|---:|
| BAAI/bge-small-en-v1.5 | 0.922 | 7.14 | 863.0 | not saved | not saved | 384 |
| intfloat/e5-small-v2 | 0.933 | 6.87 | 873.4 | not saved | not saved | 384 |
| thenlper/gte-small | 0.933 | 18.02 | 971.2 | not saved | not saved | 384 |
| sentence-transformers/all-MiniLM-L6-v2 | 0.922 | 10.29 | 933.8 | not saved | not saved | 384 |

Those RSS values are retained for comparison only and are not the DDR-89 pass metric.

## Corrected run

| Candidate | Recall@5 | p95 ms | Added VmRSS MiB | VmHWM MiB | cgroup peak MiB | cgroup current MiB | Dimension | Recall | p95 | RSS |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| BAAI/bge-small-en-v1.5 | 0.922 | 5.73 | 364.57 | 513.82 | 471.45 | 393.03 | 384 | Pass | Pass | Fail |
| intfloat/e5-small-v2 | 0.933 | 4.84 | 300.59 | 423.06 | 381.20 | 363.66 | 384 | Pass | Pass | Fail |
| thenlper/gte-small | 0.933 | 25.71 | 242.41 | 472.20 | 428.82 | 269.47 | 384 | Pass | Pass | Pass |
| sentence-transformers/all-MiniLM-L6-v2 | 0.922 | 19.17 | 175.52 | 452.88 | 409.86 | 202.05 | 384 | Pass | Pass | Pass |

Corrected evidence is persisted in four DDR-89 runs created 2026-11-15, one candidate per run, with the runtime settings above.

## DDR-89 decision procedure

1. Bars remain Recall@5 ≥ 0.85, p95 ≤ 50 ms and added worker RSS ≤ 300 MiB.
2. BGE and E5 fail only the RSS bar. GTE and MiniLM pass all three bars.
3. GTE and E5 have the highest Recall@5 at 0.933, but E5 is ineligible because its RSS is 300.59 MiB. Among passing models, GTE and MiniLM tie at 0.922.
4. The RSS tie-break selects MiniLM at 175.52 MiB over GTE at 242.41 MiB.
5. The rule therefore gives MiniLM L6 v2 as the provisional winner. Owner confirmation is required before recording point (7) in DDR-121 or fixing a vector dimension.

## Open items

- The draft questions still require KM and CA approval in-app as the DDR-90 golden set under DDR-46 during 16C.
- The worker-image build issue is fixed in the final image, but future dependency changes must keep the worker build as the verification gate.
- Evaluation persistence is implemented by migration 0026; future benchmark runs should continue using the SECURITY DEFINER write functions and persisted run/result rows.
