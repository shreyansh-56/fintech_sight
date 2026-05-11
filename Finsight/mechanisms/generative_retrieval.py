"""Generative retrieval for Chain-of-Analysis segments."""
from __future__ import annotations

from typing import Any, Dict, List, Union
import numpy as np

from Finsight.tools.unified_llm_client import EmbeddingClient


class CoARetriever:
    """
    Embedding-based retrieval of relevant CoA segments for report generation.
    Uses sentence-transformers for local embeddings (no API needed).

    retrieve() accepts either:
      - candidates: List[str]   → returns List[int] (indices into the input list)
      - candidates: List[Dict]  → returns top-k Dict items with similarity_score
    Both call paths are supported for backward compatibility.
    """

    def __init__(self, embedding_client: EmbeddingClient = None):
        self.embedding_client = embedding_client or EmbeddingClient()
        self._cached_embeddings: Dict[str, List[float]] = {}

    # ------------------------------------------------------------------
    # Primary entry point used by EnhancedReportWriter
    # ------------------------------------------------------------------
    def retrieve(  # type: ignore[override]
        self,
        query: str,
        candidates: Union[List[str], List[Dict[str, Any]]],
        top_k: int = 5,
    ) -> List[int]:
        """
        Retrieve top-k relevant candidates.

        Args:
            query:      Section title / description to retrieve for.
            candidates: Either a list of plain strings OR list of CoA dicts.
            top_k:      Number of top results to return.

        Returns:
            List of integer indices into *candidates* (sorted by relevance).
        """
        if not candidates:
            return []

        # Normalise candidates to strings
        if isinstance(candidates[0], dict):
            texts = [self._make_searchable_text(seg) for seg in candidates]  # type: ignore[arg-type]
        else:
            texts = candidates  # type: ignore[assignment]

        # Guard: empty texts after normalisation
        texts = [t for t in texts if t and str(t).strip()]
        if not texts:
            return list(range(min(top_k, len(candidates))))

        # Try embedding-based retrieval, fall back to keyword matching
        try:
            return self._embed_retrieve(query, texts, top_k)
        except Exception:
            return self._keyword_retrieve(query, texts, top_k)

    # ------------------------------------------------------------------
    # Dict-based retrieval (kept for any callers that use the old API)
    # ------------------------------------------------------------------
    def retrieve_dicts(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve top-k CoA segment dicts with similarity_score attached."""
        indices = self.retrieve(query, candidates, top_k)
        results = []
        for idx in indices:
            item = candidates[idx].copy()
            item.setdefault("similarity_score", 0.0)
            results.append(item)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _embed_retrieve(self, query: str, texts: List[str], top_k: int) -> List[int]:
        """Embedding cosine-similarity retrieval; returns indices."""
        query_embedding = np.array(self.embedding_client.encode_single(query))

        candidate_embeddings = []
        for text in texts:
            cache_key = text[:200]  # short key for caching
            if cache_key not in self._cached_embeddings:
                self._cached_embeddings[cache_key] = self.embedding_client.encode_single(text)
            candidate_embeddings.append(np.array(self._cached_embeddings[cache_key]))

        candidate_matrix = np.array(candidate_embeddings)
        # Normalise
        qnorm = np.linalg.norm(query_embedding)
        if qnorm == 0:
            return list(range(min(top_k, len(texts))))
        query_embedding = query_embedding / qnorm

        norms = np.linalg.norm(candidate_matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        candidate_matrix = candidate_matrix / norms

        similarities = candidate_matrix @ query_embedding
        top_k_actual = min(top_k, len(texts))
        top_k_indices = np.argsort(similarities)[::-1][:top_k_actual].tolist()
        return top_k_indices

    def _keyword_retrieve(self, query: str, texts: List[str], top_k: int) -> List[int]:
        """Simple keyword-overlap fallback when embeddings fail."""
        query_words = set(query.lower().split())
        scores = []
        for i, text in enumerate(texts):
            text_words = set(str(text).lower().split())
            overlap = len(query_words & text_words)
            scores.append((overlap, i))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [idx for _, idx in scores[:min(top_k, len(texts))]]

    def _make_searchable_text(self, segment: Dict[str, Any]) -> str:
        """Create a searchable text representation of a CoA segment dict."""
        parts = []
        if segment.get("title"):
            parts.append(segment["title"])
        if segment.get("focus"):
            parts.append(segment["focus"])
        if segment.get("step_focus"):
            parts.append(segment["step_focus"])
        if segment.get("text"):
            parts.append(segment["text"][:500])
        if segment.get("insights"):
            parts.append(" ".join(segment["insights"][:3]))
        if segment.get("stdout"):
            parts.append(segment["stdout"][:200])
        return " ".join(parts)

    def clear_cache(self):
        """Clear the embedding cache."""
        self._cached_embeddings.clear()
