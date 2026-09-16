from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    metadata: Mapping[str, str | int | float | bool]
    distance: float
    similarity: float


class RetrievalService:
    REQUIRED_METADATA = ("chunk_id", "document_id", "title", "page", "url")

    def __init__(self, model: Any, collection: Any, top_k: int = 4) -> None:
        self.model = model
        self.collection = collection
        self.top_k = top_k

    def retrieve(self, question: str) -> list[RetrievedChunk]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-blank string")
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        device = getattr(getattr(self.model, "device", None), "type", None)
        if device != "cpu":
            raise RuntimeError("query embeddings must run on CPU")

        count = self.collection.count()
        if count == 0:
            return []
        embeddings = self.model.encode(
            [question.strip()],
            device="cpu",
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        embeddings = np.asarray(embeddings, dtype=np.float32)
        if embeddings.ndim != 2 or embeddings.shape[0] != 1 or embeddings.shape[1] != 384:
            raise RuntimeError("query embedding must have shape (1, 384)")
        if not np.isfinite(embeddings).all() or not np.allclose(np.linalg.norm(embeddings, axis=1), 1.0, atol=1e-5):
            raise RuntimeError("query embedding is invalid or not normalized")

        response = self.collection.query(
            query_embeddings=embeddings,
            n_results=min(self.top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        rows = zip(
            response["ids"][0],
            response["documents"][0],
            response["metadatas"][0],
            response["distances"][0],
            strict=True,
        )
        results: list[RetrievedChunk] = []
        for chunk_id, text, metadata, distance in rows:
            if not text or not isinstance(metadata, dict) or not math.isfinite(float(distance)):
                raise RuntimeError("incomplete retrieval result")
            missing = [key for key in self.REQUIRED_METADATA if metadata.get(key) in (None, "")]
            if missing or metadata.get("chunk_id") != chunk_id:
                raise RuntimeError(f"invalid retrieval metadata: {', '.join(missing) or 'chunk ID mismatch'}")
            try:
                page = int(metadata["page"])
            except (TypeError, ValueError) as exc:
                raise RuntimeError("retrieval page metadata is invalid") from exc
            if page <= 0:
                raise RuntimeError("retrieval page metadata is invalid")
            distance_value = float(distance)
            results.append(
                RetrievedChunk(
                    chunk_id=str(chunk_id),
                    text=str(text),
                    metadata=metadata,
                    distance=distance_value,
                    similarity=1.0 - distance_value,
                )
            )
        return sorted(results, key=lambda item: (-item.similarity, item.chunk_id))
