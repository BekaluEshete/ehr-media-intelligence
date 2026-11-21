"""
FAISS-backed vector store for FHIR document embeddings.

Index is persisted to FAISS_INDEX_DIR:
  - index.faiss   — the flat L2 / inner-product index
  - metadata.json — parallel list of document metadata dicts

We use IndexFlatIP (inner product) which equals cosine similarity
when vectors are L2-normalised (we always normalise in embedder.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import faiss  # type: ignore
import numpy as np

from app.config import settings


class VectorStore:
    def __init__(self, index_dir: Path | None = None):
        self.index_dir = index_dir or settings.faiss_index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.dim = settings.embedding_dim

        self._index_path = self.index_dir / "index.faiss"
        self._meta_path = self.index_dir / "metadata.json"

        self._index: faiss.IndexFlatIP = self._load_index()
        self._metadata: list[dict] = self._load_metadata()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_index(self) -> faiss.IndexFlatIP:
        if self._index_path.exists():
            idx = faiss.read_index(str(self._index_path))
            return idx
        return faiss.IndexFlatIP(self.dim)

    def _load_metadata(self) -> list[dict]:
        if self._meta_path.exists():
            return json.loads(self._meta_path.read_text())
        return []

    def save(self) -> None:
        faiss.write_index(self._index, str(self._index_path))
        self._meta_path.write_text(json.dumps(self._metadata, indent=2))

    def clear(self) -> None:
        """Wipe the index and metadata. Used before a full re-index."""
        self._index = faiss.IndexFlatIP(self.dim)
        self._metadata = []
        self.save()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def add(self, embeddings: list[list[float]], metadata: list[dict]) -> None:
        """Add pre-computed embeddings with associated metadata."""
        if not embeddings:
            return
        arr = np.array(embeddings, dtype=np.float32)
        # Ensure unit vectors (cosine via inner product)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        arr /= norms
        self._index.add(arr)
        self._metadata.extend(metadata)
        self.save()

    def count(self) -> int:
        return self._index.ntotal

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        resource_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_score: float = 0.0,
    ) -> list[dict]:
        """
        Return top_k results with relevance scores.
        Results below min_score are discarded — prevents returning unrelated
        records when the query has no meaningful match in the index.
        Optionally filter by resource_type and/or date range.
        """
        if self._index.ntotal == 0:
            return []

        q = np.array([query_vector], dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q /= norm

        # Retrieve more candidates to allow post-filter
        k = min(self._index.ntotal, top_k * 10)
        scores, indices = self._index.search(q, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            # Drop results below the relevance threshold
            if float(score) < min_score:
                continue
            meta = self._metadata[idx]

            # Filters
            if resource_type and meta.get("resource_type") != resource_type:
                continue
            if date_from and meta.get("date", "") < date_from:
                continue
            if date_to and meta.get("date", "") > date_to:
                continue

            results.append({**meta, "score": float(score)})
            if len(results) >= top_k:
                break

        return results

    # ------------------------------------------------------------------
    # Convenience: index an entire collection of documents
    # ------------------------------------------------------------------

    def index_documents(
        self,
        docs: list[dict],
        embed_fn,  # callable(list[str]) -> list[list[float]]
    ) -> int:
        """
        docs: list of dicts with at least {"text": str, ...metadata...}
        Returns number of documents indexed.
        """
        texts = [d["text"] for d in docs]
        if not texts:
            return 0
        vectors = embed_fn(texts)
        meta = [{k: v for k, v in d.items() if k != "text"} for d in docs]
        self.add(vectors, meta)
        return len(texts)
