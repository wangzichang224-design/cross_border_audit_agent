# -*- coding: utf-8 -*-
"""
Cross-encoder reranking for the audit RAG pipeline.

Pipeline position:
    BM25 ∪ Vector  →  RRF fuse (cheap)  →  Reranker (expensive but precise)  →  LLM

Why a separate stage instead of trusting RRF order?
- RRF is rank-based: it knows two rankers agreed, but not *by how much*.
- A cross-encoder (e.g. BAAI/bge-reranker-base) reads the query and candidate
  together with full attention — order of magnitude better at deciding
  "does this准则 actually cover this 跨境业务" than either retriever alone.

Cost & loading:
- Model size ~280 MB (base) / ~1.1 GB (large). Loaded lazily on first use.
- CPU inference ~30–80 ms per (query, passage) pair on a modern laptop, so we
  cap reranking to a small top-K (default 20) from the fused candidates.
- If `sentence_transformers` isn't installed (the project's mock mode), the
  reranker is a no-op — we just return the input list unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Sequence

from .rag import RetrievedChunk


logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """
    Wraps a HuggingFace cross-encoder for relevance scoring.

    Designed to fail soft: any failure to load or run the model
    returns the input ordering, so the audit pipeline never breaks
    just because a heavy ML dep is missing.
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-base", max_length: int = 512):
        self.model_name = model_name
        self.max_length = max_length
        self._model = None
        self._load_failed = False

    @property
    def is_available(self) -> bool:
        """True if the model is loaded OR loadable. False if we already tried and failed."""
        if self._model is not None:
            return True
        if self._load_failed:
            return False
        return self._try_load()

    def _try_load(self) -> bool:
        try:
            from sentence_transformers import CrossEncoder  # type: ignore

            self._model = CrossEncoder(self.model_name, max_length=self.max_length)
            return True
        except Exception as exc:  # noqa: BLE001 — log and degrade
            logger.warning(
                "Reranker unavailable, skipping cross-encoder stage: %s", exc
            )
            self._load_failed = True
            return False

    def rerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Reorder `chunks` by cross-encoder relevance to `query`.

        Returns chunks with `score` overwritten by the rerank score. If the
        model can't be loaded, returns the input list (optionally truncated).
        """
        if not chunks:
            return []
        if not self.is_available or self._model is None:
            return list(chunks if top_k is None else chunks[:top_k])

        pairs = [(query, c.text) for c in chunks]
        try:
            scores = self._model.predict(pairs, convert_to_numpy=True).tolist()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Rerank inference failed, returning unranked list: %s", exc)
            return list(chunks if top_k is None else chunks[:top_k])

        scored = sorted(
            zip(scores, chunks), key=lambda pair: pair[0], reverse=True
        )
        result = [replace(c, score=float(s)) for s, c in scored]
        if top_k is not None:
            result = result[:top_k]
        return result


# Module-level singleton to avoid reloading the model on every search call.
# Build with explicit `get_default_reranker()` so callers can swap models.
_default_reranker: CrossEncoderReranker | None = None


def get_default_reranker(model_name: str = "BAAI/bge-reranker-base") -> CrossEncoderReranker:
    global _default_reranker
    if _default_reranker is None or _default_reranker.model_name != model_name:
        _default_reranker = CrossEncoderReranker(model_name=model_name)
    return _default_reranker
