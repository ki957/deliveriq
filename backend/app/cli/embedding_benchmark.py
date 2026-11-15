"""DDR-89 CPU embedding benchmark runner for a draft retrieval set."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Any

os.environ["RAYON_NUM_THREADS"] = "1"

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]
import psycopg
from tokenizers import Tokenizer

BATCH_SIZE = 16
APPROVAL_LABEL = "approved for benchmark use only; draft, not the DDR-90 golden set"
MODELS: dict[str, dict[str, Any]] = {
    "BAAI/bge-small-en-v1.5": {
        "pooling": "cls",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "document_prefix": "",
    },
    "intfloat/e5-small-v2": {
        "pooling": "mean",
        "query_prefix": "query: ",
        "document_prefix": "passage: ",
    },
    "thenlper/gte-small": {"pooling": "mean", "query_prefix": "", "document_prefix": ""},
    "sentence-transformers/all-MiniLM-L6-v2": {
        "pooling": "mean",
        "query_prefix": "",
        "document_prefix": "",
    },
}


def proc_status_bytes(field: str) -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith(f"{field}:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError(f"{field} is missing from /proc/self/status")


def cgroup_bytes(filename: str) -> int | None:
    for path in (Path("/sys/fs/cgroup") / filename, Path("/sys/fs/cgroup/memory") / filename):
        try:
            return int(path.read_text().strip())
        except (OSError, ValueError):
            continue
    return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def embed(
    session: ort.InferenceSession, tokenizer: Tokenizer, texts: list[str], pooling: str
) -> list[list[float]]:
    tokenizer.enable_truncation(max_length=512)
    encoded = tokenizer.encode_batch(texts)
    max_len = max(len(item.ids) for item in encoded)
    pad_id = tokenizer.token_to_id("[PAD]") or 0
    ids = [item.ids + [pad_id] * (max_len - len(item.ids)) for item in encoded]
    masks = [item.attention_mask + [0] * (max_len - len(item.attention_mask)) for item in encoded]
    inputs: dict[str, Any] = {
        "input_ids": np.asarray(ids, dtype="int64"),
        "attention_mask": np.asarray(masks, dtype="int64"),
    }
    if "token_type_ids" in {item.name for item in session.get_inputs()}:
        inputs["token_type_ids"] = np.zeros_like(inputs["input_ids"])
    output = session.run(None, inputs)[0]
    vectors: list[list[float]] = []
    for row, mask in zip(output, masks, strict=True):
        if pooling == "cls":
            vector = row[0]
        else:
            weights = np.asarray(mask, dtype="float32")[:, None]
            vector = (row * weights).sum(axis=0) / max(float(weights.sum()), 1.0)
        norm = math.sqrt(float((vector * vector).sum()))
        vectors.append((vector / norm).astype("float32").tolist() if norm else vector.tolist())
    return vectors


def run(model_name: str, models_dir: Path, dataset_path: Path) -> dict[str, Any]:
    dataset = json.loads(dataset_path.read_text())
    model_dir = models_dir / model_name.replace("/", "--")
    model_path = model_dir / "model.int8.onnx"
    tokenizer_path = model_dir / "tokenizer.json"
    if not model_path.is_file() or not tokenizer_path.is_file():
        raise FileNotFoundError(f"Missing int8 model/tokenizer for {model_name} under {model_dir}")

    baseline_rss = proc_status_bytes("VmRSS")
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.enable_cpu_mem_arena = False
    session = ort.InferenceSession(str(model_path), sess_options=options, providers=["CPUExecutionProvider"])
    spec = MODELS[model_name]
    query_texts = [spec["query_prefix"] + item["question"] for item in dataset["queries"]]
    for query in query_texts[:5]:
        embed(session, tokenizer, [query], spec["pooling"])

    corpus = dataset["corpus"]
    document_vectors: list[list[float]] = []
    for start in range(0, len(corpus), BATCH_SIZE):
        batch = corpus[start : start + BATCH_SIZE]
        texts = [spec["document_prefix"] + item["text"] for item in batch]
        document_vectors.extend(embed(session, tokenizer, texts, spec["pooling"]))
    ingestion_hwm = proc_status_bytes("VmHWM")

    latencies: list[float] = []
    hits = 0
    for case, query in zip(dataset["queries"], query_texts, strict=True):
        started = time.perf_counter()
        vector = embed(session, tokenizer, [query], spec["pooling"])[0]
        latencies.append((time.perf_counter() - started) * 1000)
        scored = [
            (sum(left * right for left, right in zip(vector, passage, strict=True)), item["id"])
            for passage, item in zip(document_vectors, corpus, strict=True)
        ]
        top_five = {item_id for _, item_id in sorted(scored, reverse=True)[:5]}
        hits += int(case["expected_chunk_id"] in top_five)

    final_rss = proc_status_bytes("VmRSS")
    cgroup_current = cgroup_bytes("memory.current")
    cgroup_peak = cgroup_bytes("memory.peak")
    result = {
        "model": model_name,
        "revision": json.loads((model_dir / "metadata.json").read_text())["revision"],
        "artifact_sha256": sha256(model_path),
        "dimension": len(document_vectors[0]),
        "dataset_cases": len(dataset["queries"]),
        "recall_at_5": hits / len(dataset["queries"]),
        "p95_query_embedding_ms": percentile95(latencies),
        "mean_query_embedding_ms": sum(latencies) / len(latencies),
        "steady_state_added_rss_mb": (final_rss - baseline_rss) / (1024 * 1024),
        "steady_state_worker_vmrss_mb": final_rss / (1024 * 1024),
        "ingestion_batch_peak_vmhwm_mb": ingestion_hwm / (1024 * 1024),
        "cgroup_memory_current_mb": (cgroup_current / (1024 * 1024) if cgroup_current is not None else None),
        "cgroup_memory_peak_mb": (cgroup_peak / (1024 * 1024) if cgroup_peak is not None else None),
        "ingestion_batch_size": BATCH_SIZE,
        "runtime": ort.__version__,
    }
    return result


def persist(result: dict[str, Any], dataset_hash: str) -> str:
    runtime = {
        "onnxruntime_intra_op_num_threads": 1,
        "onnxruntime_inter_op_num_threads": 1,
        "onnxruntime_execution_mode": "sequential",
        "onnxruntime_enable_cpu_mem_arena": False,
        "tokenizers_rayon_num_threads": 1,
        "ingestion_batch_size": BATCH_SIZE,
        "quantization": "per-channel dynamic QInt8, performed before measured container run",
    }
    with psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    ) as connection:
        run_row = connection.execute(
            "SELECT ops.record_ai_eval_run(%s, %s, %s, %s::jsonb)",
            ("DDR-89", dataset_hash, APPROVAL_LABEL, json.dumps(runtime)),
        ).fetchone()
        if run_row is None:
            raise RuntimeError("evaluation run function returned no id")
        run_id = run_row[0]
        metrics = {
            key: result[key]
            for key in (
                "recall_at_5",
                "p95_query_embedding_ms",
                "mean_query_embedding_ms",
                "steady_state_added_rss_mb",
                "steady_state_worker_vmrss_mb",
                "ingestion_batch_peak_vmhwm_mb",
                "cgroup_memory_current_mb",
                "cgroup_memory_peak_mb",
                "dataset_cases",
                "ingestion_batch_size",
            )
        }
        connection.execute(
            "SELECT ops.record_ai_eval_result(%s, %s, %s, %s, %s, %s::jsonb)",
            (
                run_id,
                result["model"],
                result["revision"],
                result["artifact_sha256"],
                result["dimension"],
                json.dumps(metrics),
            ),
        )
    return str(run_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=sorted(MODELS))
    parser.add_argument("--models-dir", type=Path, default=Path("/srv/embedding-models"))
    parser.add_argument(
        "--dataset", type=Path, default=Path("/srv/test_inputs/embedding_benchmark_draft.json")
    )
    parser.add_argument("--dataset-sha256", required=True)
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    result = run(args.model, args.models_dir, args.dataset)
    if args.persist:
        result["eval_run_id"] = persist(result, args.dataset_sha256)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
