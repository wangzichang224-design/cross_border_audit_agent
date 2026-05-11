# -*- coding: utf-8 -*-
"""
Hybrid retrieval: BM25 (keyword) + dense vector + Reciprocal Rank Fusion (RRF).

Why hybrid?
- Vector search captures semantics ("舞弊风险" matches "管理层操纵").
- BM25 captures literal tokens (准则编号 "1141 号"、"ISA 240"、SKU code).
- Audit work is highly literal — missing a 编号 is a compliance failure, not a style miss.

Reciprocal Rank Fusion merges multiple ranked lists by:
    rrf_score(d) = sum over rankers r of  1 / (k + rank_r(d))
where k is a smoothing constant (default 60, per Cormack et al. 2009).
RRF requires no score calibration between rankers — robust default for
audit retrieval where vector cosine and BM25 scores live in different ranges.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from typing import Callable, Sequence

from .rag import RetrievedChunk


# ──────────────────────────────────────────────────────────────────────────────
# Tokenization (Chinese-aware, dependency-free)
# ──────────────────────────────────────────────────────────────────────────────

_CN_RANGE = r"一-鿿"
_TOKEN_RE = re.compile(rf"[a-zA-Z0-9_]+|[{_CN_RANGE}]")


def tokenize_for_bm25(text: str) -> list[str]:
    """
    Tokenization tailored for audit Chinese + alphanumeric codes.

    Strategy:
    - Latin/digit runs kept whole (so "ISA240" or "1141号" survive as units).
    - Chinese characters split into unigrams AND bigrams. Unigrams give recall
      on single-character searches; bigrams ("舞弊"、"准则") give precision.
      For BM25 this is a common dependency-free alternative to jieba.

    Example:
      "审计准则第 1141 号 舞弊" →
          ["审", "计", "准", "则", "1141", "号", "舞", "弊",
           "审计", "计准", "准则", "舞弊"]
    """
    text = text.lower()
    raw = _TOKEN_RE.findall(text)
    unigrams = [t for t in raw if t]
    # Build bigrams for adjacent CJK characters only (skip across non-CJK).
    bigrams: list[str] = []
    for i in range(len(unigrams) - 1):
        a, b = unigrams[i], unigrams[i + 1]
        if len(a) == 1 and len(b) == 1 and _is_cjk(a) and _is_cjk(b):
            bigrams.append(a + b)
    return unigrams + bigrams


def _is_cjk(ch: str) -> bool:
    return bool(ch) and "一" <= ch[0] <= "鿿"


# ──────────────────────────────────────────────────────────────────────────────
# BM25 retriever (pure-Python; uses rank_bm25 if available for speed)
# ──────────────────────────────────────────────────────────────────────────────


class BM25Retriever:
    """
    BM25 over a fixed chunk corpus. Builds an in-memory index at construction.

    Falls back to a manual BM25 implementation if `rank_bm25` is not installed,
    so this module remains usable in mock-mode without extra deps.
    """

    def __init__(self, chunks: Sequence[RetrievedChunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = list(chunks)
        self.k1 = k1
        self.b = b
        self._tokens: list[list[str]] = [tokenize_for_bm25(c.text) for c in self.chunks]
        self._impl = self._build_impl()

    def _build_impl(self):
        try:
            from rank_bm25 import BM25Okapi  # type: ignore

            return BM25Okapi(self._tokens, k1=self.k1, b=self.b)
        except ImportError:
            return _ManualBM25(self._tokens, k1=self.k1, b=self.b)

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        if not self.chunks:
            return []
        query_tokens = tokenize_for_bm25(query)
        if not query_tokens:
            return []
        scores = self._impl.get_scores(query_tokens)
        ranked = sorted(
            ((float(s), idx) for idx, s in enumerate(scores) if s > 0),
            key=lambda t: t[0],
            reverse=True,
        )
        out: list[RetrievedChunk] = []
        for score, idx in ranked[:top_k]:
            out.append(replace(self.chunks[idx], score=score))
        return out


class _ManualBM25:
    """Minimal pure-Python BM25 used when rank_bm25 is unavailable."""

    def __init__(self, tokenized_corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = tokenized_corpus
        self.doc_len = [len(d) for d in tokenized_corpus]
        self.avgdl = sum(self.doc_len) / max(len(tokenized_corpus), 1)
        self.doc_freqs: list[dict[str, int]] = []
        df: dict[str, int] = {}
        for doc in tokenized_corpus:
            freqs: dict[str, int] = {}
            for term in doc:
                freqs[term] = freqs.get(term, 0) + 1
            self.doc_freqs.append(freqs)
            for term in freqs:
                df[term] = df.get(term, 0) + 1
        n = len(tokenized_corpus)
        self.idf = {
            term: math.log(1 + (n - count + 0.5) / (count + 0.5))
            for term, count in df.items()
        }

    def get_scores(self, query: list[str]) -> list[float]:
        scores = [0.0] * len(self.corpus)
        for i, freqs in enumerate(self.doc_freqs):
            denom_norm = 1 - self.b + self.b * (self.doc_len[i] / (self.avgdl or 1))
            for term in query:
                f = freqs.get(term)
                if not f:
                    continue
                idf = self.idf.get(term, 0.0)
                scores[i] += idf * (f * (self.k1 + 1)) / (f + self.k1 * denom_norm)
        return scores


# ──────────────────────────────────────────────────────────────────────────────
# Reciprocal Rank Fusion
# ──────────────────────────────────────────────────────────────────────────────


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[RetrievedChunk]],
    k: int = 60,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """
    Merge multiple ranked lists with RRF.

    Args:
        ranked_lists: each element is a list ordered best→worst.
        k: smoothing constant. Higher k reduces the dominance of top ranks.
        top_k: if set, truncate output.

    Returns:
        Merged list ordered by RRF score (descending). Chunk.score is overwritten
        with the RRF score so downstream code (e.g. reporting) shows fused weight.

    Deduplication key:
        Prefer chunk_id (stable across rankers); fall back to source + text hash.
    """
    fused: dict[str, dict] = {}
    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked):
            key = chunk.chunk_id or f"{chunk.source_file}::{hash(chunk.text)}"
            slot = fused.setdefault(key, {"chunk": chunk, "score": 0.0})
            slot["score"] += 1.0 / (k + rank + 1)  # rank is 0-based; spec is 1-based
            # Keep the version with the richest metadata (longest source label).
            if len(chunk.source) > len(slot["chunk"].source):
                slot["chunk"] = chunk

    merged = sorted(fused.values(), key=lambda s: s["score"], reverse=True)
    result: list[RetrievedChunk] = []
    for slot in merged:
        result.append(replace(slot["chunk"], score=slot["score"]))
    if top_k is not None:
        result = result[:top_k]
    return result


# ──────────────────────────────────────────────────────────────────────────────
# High-level orchestrator
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HybridSearchPlan:
    """Configuration for one hybrid retrieval call."""

    vector_top_k: int = 20
    bm25_top_k: int = 20
    fused_top_k: int = 10
    rrf_k: int = 60


def run_hybrid_search(
    query: str,
    *,
    bm25: BM25Retriever,
    vector_search: Callable[[str, int], list[RetrievedChunk]] | None,
    plan: HybridSearchPlan = HybridSearchPlan(),
) -> list[RetrievedChunk]:
    """
    Execute hybrid search.

    `vector_search` may return [] (e.g. ChromaDB not initialized), in which case
    we degrade to BM25-only. This matches the project's "mock-friendly" stance.
    """
    bm25_hits = bm25.search(query, plan.bm25_top_k)
    vector_hits: list[RetrievedChunk] = []
    if vector_search is not None:
        try:
            vector_hits = vector_search(query, plan.vector_top_k) or []
        except Exception:
            # Never let a backend failure break the audit pipeline.
            vector_hits = []

    if not vector_hits and not bm25_hits:
        return []
    if not vector_hits:
        return bm25_hits[: plan.fused_top_k]
    if not bm25_hits:
        return vector_hits[: plan.fused_top_k]
    return reciprocal_rank_fusion(
        [vector_hits, bm25_hits], k=plan.rrf_k, top_k=plan.fused_top_k
    )
