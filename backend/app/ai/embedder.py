"""Embedding interfaces shared by ingestion and retrieval (DDR-57, DDR-88)."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Literal, Protocol

EmbedKind = Literal["query", "document"]


class Embedder(Protocol):
    def embed(self, texts: list[str], kind: EmbedKind = "document") -> list[list[float]]: ...


class MockEmbedder:
    """Deterministic test embedder; dimension is explicit and never persisted as a model choice."""

    def __init__(self, dimension: int) -> None:
        if dimension < 1:
            raise ValueError("dimension must be positive")
        self.dimension = dimension

    def embed(self, texts: list[str], kind: EmbedKind = "document") -> list[list[float]]:
        del kind
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                vector[index] += 1.0 if digest[4] & 1 else -1.0
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append([value / norm for value in vector] if norm else vector)
        return vectors


class LocalOnnxEmbedder:
    """Pinned MiniLM L6 v2 ONNX adapter used by the worker (DDR-57, DDR-88, DDR-121, DDR-122)."""

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    dimension = 384

    def __init__(self, models_root: str | Path = "/srv/embedding-models") -> None:
        # Imports are lazy so the API image can retain its small dependency group.
        import onnxruntime as ort  # type: ignore[import-untyped]
        from tokenizers import Tokenizer

        model_dir = Path(models_root) / self.model_name.replace("/", "--")
        self.model_path = model_dir / "model.int8.onnx"
        tokenizer_path = model_dir / "tokenizer.json"
        if not self.model_path.is_file() or not tokenizer_path.is_file():
            raise FileNotFoundError(f"Missing MiniLM ONNX artifacts under {model_dir}")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.enable_cpu_mem_arena = False
        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self._session = ort.InferenceSession(
            str(self.model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )

    def embed(self, texts: list[str], kind: EmbedKind = "document") -> list[list[float]]:
        import numpy as np

        self._tokenizer.enable_truncation(max_length=512)
        encoded = self._tokenizer.encode_batch(texts)
        max_len = max((len(item.ids) for item in encoded), default=0)
        pad_id = self._tokenizer.token_to_id("[PAD]") or 0
        ids = [item.ids + [pad_id] * (max_len - len(item.ids)) for item in encoded]
        masks = [item.attention_mask + [0] * (max_len - len(item.attention_mask)) for item in encoded]
        inputs: dict[str, object] = {
            "input_ids": np.asarray(ids, dtype="int64"),
            "attention_mask": np.asarray(masks, dtype="int64"),
        }
        if "token_type_ids" in {item.name for item in self._session.get_inputs()}:
            inputs["token_type_ids"] = np.zeros_like(inputs["input_ids"])
        output = self._session.run(None, inputs)[0]
        vectors: list[list[float]] = []
        for row, mask in zip(output, masks, strict=True):
            weights = np.asarray(mask, dtype="float32")[:, None]
            vector = (row * weights).sum(axis=0) / max(float(weights.sum()), 1.0)
            norm = math.sqrt(float((vector * vector).sum()))
            vectors.append((vector / norm).astype("float32").tolist() if norm else vector.tolist())
        return vectors
