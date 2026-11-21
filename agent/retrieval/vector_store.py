"""In-memory vector store for document chunks.

Uses FAISS when it is installed and falls back to a NumPy index otherwise.
Both do exact inner-product search, so results are identical; FAISS only
matters for speed on very large documents.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .embeddings import HashedTfidfEmbedder
from .pdf_loader import Chunk

try:  # Optional dependency: `pip install faiss-cpu`
    import faiss
except ImportError:
    faiss = None


TITLE_WEIGHT = 1.5


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float  # cosine similarity, 0..1


class VectorStore:
    def __init__(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError("Cannot build a vector store from zero chunks.")
        self.chunks = chunks
        self.embedder = HashedTfidfEmbedder()
        body = self.embedder.fit_transform([c.text for c in chunks])
        # A FAQ question is the best predictor of what customers will type, so it
        # counts extra. Chunks without a title get a zero vector here (no effect).
        titles = self.embedder.transform([c.title for c in chunks])
        combined = body + TITLE_WEIGHT * titles
        self._vectors = (combined / np.linalg.norm(combined, axis=1, keepdims=True)).astype(np.float32)
        self._faiss_index = None
        if faiss is not None:
            self._faiss_index = faiss.IndexFlatIP(self._vectors.shape[1])
            self._faiss_index.add(self._vectors)

    @property
    def backend(self) -> str:
        return "FAISS" if self._faiss_index is not None else "NumPy"

    def search(self, query: str, k: int = 4) -> list[SearchHit]:
        """Return up to k chunks most similar to the query, best first."""
        k = min(k, len(self.chunks))
        query_vector = self.embedder.transform([query])
        if self._faiss_index is not None:
            scores, indices = self._faiss_index.search(query_vector, k)
            pairs = zip(indices[0].tolist(), scores[0].tolist())
        else:
            all_scores = self._vectors @ query_vector[0]
            top = np.argsort(-all_scores)[:k]
            pairs = ((int(i), float(all_scores[i])) for i in top)
        return [SearchHit(self.chunks[i], score) for i, score in pairs if i >= 0 and score > 0]
