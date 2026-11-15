"""Embedding interfaces shared by ingestion and retrieval (DDR-57, DDR-88)."""

from __future__ import annotations

import hashlib
import math
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
