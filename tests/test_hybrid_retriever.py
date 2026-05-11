# -*- coding: utf-8 -*-
"""Unit tests for audit_rag.hybrid_retriever and AuditKnowledgeBase hybrid mode.

These tests are dependency-free: they exercise the pure-Python BM25 fallback
and RRF merger, so they pass in `mock` mode without needing rank_bm25,
sentence-transformers, or chromadb.

Run:
    python -m unittest tests.test_hybrid_retriever
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make the repo root importable when running this file directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from audit_rag.hybrid_retriever import (  # noqa: E402
    BM25Retriever,
    HybridSearchPlan,
    reciprocal_rank_fusion,
    run_hybrid_search,
    tokenize_for_bm25,
)
from audit_rag.rag import AuditKnowledgeBase, RetrievedChunk  # noqa: E402


def _make_chunk(chunk_id: str, text: str, source: str = "test.md") -> RetrievedChunk:
    return RetrievedChunk(
        source=source,
        text=text,
        score=0.0,
        source_file=source,
        chunk_id=chunk_id,
    )


class TestTokenizer(unittest.TestCase):
    def test_keeps_alphanumeric_tokens_whole(self):
        tokens = tokenize_for_bm25("ISA240 第 1141 号舞弊")
        # Latin/digit runs must survive intact — they're audit references.
        self.assertIn("isa240", tokens)
        self.assertIn("1141", tokens)

    def test_chinese_unigrams_and_bigrams(self):
        tokens = tokenize_for_bm25("舞弊风险")
        self.assertIn("舞", tokens)
        self.assertIn("弊", tokens)
        self.assertIn("舞弊", tokens)  # CJK bigram
        self.assertIn("弊风", tokens)
        self.assertIn("风险", tokens)

    def test_no_cross_script_bigrams(self):
        # We should NOT pair a CJK char with a Latin char as a bigram.
        tokens = tokenize_for_bm25("ISA 审计")
        self.assertNotIn("isa审", tokens)
        self.assertNotIn("a审", tokens)


class TestBM25Retriever(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            _make_chunk("c1", "中国注册会计师审计准则第 1141 号: 舞弊相关责任。"),
            _make_chunk("c2", "企业会计准则第 4 号: 固定资产确认与计量。"),
            _make_chunk("c3", "跨境电商存货跌价准备需要考虑滞销风险与汇率波动。"),
            _make_chunk("c4", "无关文本: 今天的天气真好，我去公园散步。"),
        ]
        self.bm25 = BM25Retriever(self.chunks)

    def test_finds_audit_standard_by_number(self):
        # Vector search would struggle here; BM25 should ace it.
        results = self.bm25.search("1141 号", top_k=2)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, "c1")

    def test_unrelated_query_returns_no_match(self):
        # All chunks should score 0 for a query that shares no tokens.
        results = self.bm25.search("xyz_unrelated_token_zzz", top_k=4)
        self.assertEqual(results, [])

    def test_topk_respected(self):
        # "审计" appears in chunk 1; bigrams in 2 may share single chars only.
        results = self.bm25.search("审计 准则 资产", top_k=2)
        self.assertLessEqual(len(results), 2)

    def test_score_strictly_positive(self):
        # When BM25 returns a chunk, its score must be > 0 (zero-score items
        # are filtered out by the retriever).
        results = self.bm25.search("舞弊", top_k=4)
        for r in results:
            self.assertGreater(r.score, 0.0)


class TestRRF(unittest.TestCase):
    def test_merge_prefers_consensus(self):
        # Chunk c1 appears at rank 0 in both lists → should win.
        # c2 appears only in list A; c3 only in list B.
        a = [_make_chunk("c1", "alpha"), _make_chunk("c2", "beta")]
        b = [_make_chunk("c1", "alpha"), _make_chunk("c3", "gamma")]
        merged = reciprocal_rank_fusion([a, b], k=60)
        self.assertEqual(merged[0].chunk_id, "c1")
        # c1's RRF score should exceed each singleton's.
        c1_score = merged[0].score
        for c in merged[1:]:
            self.assertGreater(c1_score, c.score)

    def test_top_k_truncation(self):
        a = [_make_chunk(f"a{i}", f"text {i}") for i in range(5)]
        b = [_make_chunk(f"b{i}", f"text {i}") for i in range(5)]
        merged = reciprocal_rank_fusion([a, b], top_k=3)
        self.assertEqual(len(merged), 3)

    def test_dedup_uses_chunk_id(self):
        # Same chunk_id in two lists must NOT appear twice.
        a = [_make_chunk("same", "v1", source="A.md")]
        b = [_make_chunk("same", "v2", source="LONGER-source-name.md")]
        merged = reciprocal_rank_fusion([a, b])
        self.assertEqual(len(merged), 1)
        # The merger keeps the richer-source variant.
        self.assertEqual(merged[0].source, "LONGER-source-name.md")


class TestRunHybridSearch(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            _make_chunk("c1", "审计准则第 1141 号关注舞弊风险。"),
            _make_chunk("c2", "固定资产资本化与费用化的判断。"),
        ]
        self.bm25 = BM25Retriever(self.chunks)

    def test_vector_search_none_falls_back_to_bm25(self):
        results = run_hybrid_search(
            "1141 号",
            bm25=self.bm25,
            vector_search=None,
            plan=HybridSearchPlan(fused_top_k=2),
        )
        self.assertEqual(results[0].chunk_id, "c1")

    def test_vector_search_failure_does_not_crash(self):
        def boom(_q, _k):
            raise RuntimeError("ChromaDB down")

        results = run_hybrid_search(
            "舞弊",
            bm25=self.bm25,
            vector_search=boom,
            plan=HybridSearchPlan(fused_top_k=2),
        )
        # We should still get BM25 results despite the vector backend dying.
        self.assertTrue(any(r.chunk_id == "c1" for r in results))


class TestAuditKnowledgeBaseHybridIntegration(unittest.TestCase):
    """End-to-end: AuditKnowledgeBase with enable_hybrid=True over real fixtures."""

    def setUp(self):
        repo_root = Path(__file__).resolve().parents[1]
        self.kb = AuditKnowledgeBase(
            knowledge_dir=repo_root / "sample_knowledge",
            chroma_dir=repo_root / "data" / "chroma_audit_rules_test_nonexistent",
            enable_hybrid=True,
            enable_rerank=False,  # Skip heavy model for unit tests
        )

    def test_loads_fixtures(self):
        # Sanity: the sample_knowledge directory has at least 2 markdown files
        # and several sections, so the chunk count should be > 5.
        self.assertGreater(len(self.kb._fallback_chunks), 5)

    def test_hybrid_search_returns_results(self):
        # "1141 号" — a literal audit-standard reference. BM25 must surface it.
        results = self.kb.search("1141 号 舞弊", top_k=3)
        self.assertGreater(len(results), 0)
        joined = " ".join(r.text for r in results)
        # The 1141 standard must appear in the returned text.
        self.assertIn("1141", joined)

    def test_default_mode_preserved_when_hybrid_disabled(self):
        """Legacy path (no ChromaDB, no hybrid) must not raise.

        Note: the legacy ``_keyword_search`` tokenizer matches *whole runs* of
        CJK characters, so a short query like "舞弊" won't intersect a chunk's
        long run "考虑舞弊导致的重大错报风险". This is a pre-existing limitation
        — and one of the motivations for adding hybrid retrieval.

        We assert: API works, returns a list (possibly empty), doesn't crash.
        """
        repo_root = Path(__file__).resolve().parents[1]
        kb_legacy = AuditKnowledgeBase(
            knowledge_dir=repo_root / "sample_knowledge",
            chroma_dir=repo_root / "data" / "chroma_audit_rules_test_nonexistent",
            enable_hybrid=False,
            enable_rerank=False,
        )
        results = kb_legacy.search("舞弊", top_k=3)
        self.assertIsInstance(results, list)

    def test_hybrid_outperforms_legacy_on_short_query(self):
        """Concrete demonstration of WHY hybrid is the new default:
        a short literal query that the legacy tokenizer misses entirely.
        """
        repo_root = Path(__file__).resolve().parents[1]
        kb_legacy = AuditKnowledgeBase(
            knowledge_dir=repo_root / "sample_knowledge",
            chroma_dir=repo_root / "data" / "chroma_audit_rules_test_nonexistent",
            enable_hybrid=False,
        )
        kb_hybrid = AuditKnowledgeBase(
            knowledge_dir=repo_root / "sample_knowledge",
            chroma_dir=repo_root / "data" / "chroma_audit_rules_test_nonexistent",
            enable_hybrid=True,
        )
        legacy_hits = kb_legacy.search("舞弊", top_k=3)
        hybrid_hits = kb_hybrid.search("舞弊", top_k=3)
        # Hybrid must find at least as many as legacy; typically strictly more.
        self.assertGreaterEqual(len(hybrid_hits), len(legacy_hits))
        self.assertGreater(len(hybrid_hits), 0)


if __name__ == "__main__":
    unittest.main()
