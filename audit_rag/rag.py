# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class RetrievedChunk:
    source: str
    text: str
    score: float
    source_file: str = ""
    page: int | None = None
    section: str = ""
    title: str = ""
    chunk_id: str = ""


def _tokenize_zh(text: str) -> set[str]:
    text = text.lower()
    words = set(re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]{2,}", text))
    return {w for w in words if len(w.strip()) >= 2}


class AuditKnowledgeBase:
    """ChromaDB/bge-backed retriever with a keyword fallback for lightweight demos.

    Retrieval modes (controlled via constructor flags; defaults preserve old behavior):

    1. ``enable_hybrid=False``, ``enable_rerank=False`` (default):
       Vector search if ChromaDB is built, else legacy keyword fallback.
       Identical to behavior prior to the hybrid-retrieval upgrade.

    2. ``enable_hybrid=True``:
       BM25 ∪ ChromaDB merged via Reciprocal Rank Fusion. BM25 is built once
       at init time over the same local chunk corpus. Recommended for audit
       work because准则编号 ("第 1141 号"、"ISA 240") are literal strings vector
       models under-rank.

    3. ``enable_rerank=True``:
       Append a cross-encoder rerank stage (BAAI/bge-reranker-base by default)
       over the top fused candidates. Fails soft if the model can't load.
    """

    def __init__(
        self,
        knowledge_dir: Path | Iterable[Path],
        chroma_dir: Path,
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
        *,
        enable_hybrid: bool = False,
        enable_rerank: bool = False,
        reranker_model: str = "BAAI/bge-reranker-base",
    ):
        if isinstance(knowledge_dir, Path):
            self.knowledge_dirs = [knowledge_dir]
        else:
            self.knowledge_dirs = [Path(path) for path in knowledge_dir]
        self.chroma_dir = chroma_dir
        self.embedding_model = embedding_model
        self.enable_hybrid = enable_hybrid
        self.enable_rerank = enable_rerank
        self.reranker_model = reranker_model
        self._fallback_chunks = self._load_local_chunks()
        # Lazy-built artifacts (instantiated on first hybrid/rerank call).
        self._bm25 = None
        self._reranker = None

    def _load_local_chunks(self) -> list[RetrievedChunk]:
        chunks = self._load_text_chunks()
        chunks.extend(self._load_pdf_chunks())
        return chunks

    def _load_text_chunks(self) -> list[RetrievedChunk]:
        chunks: list[RetrievedChunk] = []
        for knowledge_dir in self.knowledge_dirs:
            if not knowledge_dir.exists():
                continue
            for pattern in ("*.md", "*.txt"):
                for path in sorted(knowledge_dir.rglob(pattern)):
                    if path.name.lower() == "readme.md":
                        continue
                    text = path.read_text(encoding="utf-8")
                    parts = re.split(r"\n(?=## )", text) if path.suffix.lower() == ".md" else _chunk_text(text, max_chars=900, overlap=100)
                    for idx, part in enumerate(parts, start=1):
                        part = part.strip()
                        if not part:
                            continue
                        section, title = _extract_markdown_metadata(part, path.name)
                        chunks.append(
                            RetrievedChunk(
                                source=_format_source_label(path.name, None, section, title),
                                source_file=path.name,
                                text=part,
                                score=0.0,
                                section=section,
                                title=title,
                                chunk_id=f"{path.name}::text::{idx}",
                            )
                        )
        return chunks

    def _load_pdf_chunks(self) -> list[RetrievedChunk]:
        try:
            from pypdf import PdfReader
        except Exception:
            return []

        chunks: list[RetrievedChunk] = []
        for knowledge_dir in self.knowledge_dirs:
            if not knowledge_dir.exists():
                continue
            for path in sorted(knowledge_dir.rglob("*.pdf")):
                try:
                    reader = PdfReader(str(path))
                except Exception:
                    continue
                for page_num, page in enumerate(reader.pages, start=1):
                    text = (page.extract_text() or "").strip()
                    if not text:
                        continue
                    pdf_meta = _extract_pdf_page_metadata(text)
                    page_text = _normalize_pdf_text(text)
                    for idx, chunk in enumerate(_chunk_pdf_text(page_text), start=1):
                        chunk_section = _extract_chunk_section(chunk) or pdf_meta["section"]
                        chunks.append(
                            RetrievedChunk(
                                source=_format_source_label(path.name, page_num, chunk_section, pdf_meta["title"]),
                                source_file=path.name,
                                page=page_num,
                                section=chunk_section,
                                title=pdf_meta["title"],
                                text=chunk,
                                score=0.0,
                                chunk_id=f"{path.name}::page::{page_num}::{idx}",
                            )
                        )
        return chunks

    def search(self, query: str, top_k: int = 4) -> list[RetrievedChunk]:
        """Top-level retrieval entry point. Routing:

        - If ``enable_hybrid`` → BM25 ∪ vector, RRF-fused, optional rerank.
        - Else if ChromaDB built → pure vector (legacy path).
        - Else → keyword fallback (legacy path).
        """
        if self.enable_hybrid:
            results = self._hybrid_search(query, fused_top_k=max(top_k * 4, 20))
            if self.enable_rerank and results:
                results = self._rerank(query, results, top_k=top_k)
            return results[:top_k]

        chroma_results = self._try_chroma_search(query, top_k)
        if chroma_results:
            if self.enable_rerank:
                chroma_results = self._rerank(query, chroma_results, top_k=top_k)
            return chroma_results
        keyword_results = self._keyword_search(query, top_k)
        if self.enable_rerank and keyword_results:
            keyword_results = self._rerank(query, keyword_results, top_k=top_k)
        return keyword_results

    # ── Hybrid + rerank helpers ─────────────────────────────────────────────

    def _get_bm25(self):
        if self._bm25 is None:
            from .hybrid_retriever import BM25Retriever

            self._bm25 = BM25Retriever(self._fallback_chunks)
        return self._bm25

    def _get_reranker(self):
        if self._reranker is None:
            from .reranker import get_default_reranker

            self._reranker = get_default_reranker(self.reranker_model)
        return self._reranker

    def _hybrid_search(self, query: str, fused_top_k: int) -> list[RetrievedChunk]:
        from .hybrid_retriever import HybridSearchPlan, run_hybrid_search

        bm25 = self._get_bm25()
        plan = HybridSearchPlan(
            vector_top_k=max(fused_top_k, 20),
            bm25_top_k=max(fused_top_k, 20),
            fused_top_k=fused_top_k,
        )
        return run_hybrid_search(
            query,
            bm25=bm25,
            vector_search=self._try_chroma_search,
            plan=plan,
        )

    def _rerank(
        self, query: str, candidates: list[RetrievedChunk], top_k: int
    ) -> list[RetrievedChunk]:
        reranker = self._get_reranker()
        return reranker.rerank(query, candidates, top_k=top_k)

    def _keyword_search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        query_terms = _tokenize_zh(query)
        scored: list[RetrievedChunk] = []
        for chunk in self._fallback_chunks:
            terms = _tokenize_zh(chunk.text)
            overlap = len(query_terms & terms)
            score = overlap / math.sqrt(max(len(terms), 1))
            if overlap:
                scored.append(
                    RetrievedChunk(
                        source=chunk.source,
                        source_file=chunk.source_file,
                        page=chunk.page,
                        section=chunk.section,
                        title=chunk.title,
                        chunk_id=chunk.chunk_id,
                        text=chunk.text,
                        score=score,
                    )
                )
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    def _try_chroma_search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except Exception:
            return []
        if not self.chroma_dir.exists():
            return []
        client = chromadb.PersistentClient(path=str(self.chroma_dir))
        try:
            collection = client.get_collection("audit_rules")
        except Exception:
            return []
        model = SentenceTransformer(self.embedding_model)
        query_embedding = model.encode([query], normalize_embeddings=True).tolist()[0]
        result = collection.query(query_embeddings=[query_embedding], n_results=top_k)
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        chunks = []
        for doc, meta, distance in zip(docs, metas, distances):
            chunks.append(
                RetrievedChunk(
                    source=str(meta.get("source", "chroma")),
                    source_file=str(meta.get("source_file", meta.get("source", "chroma"))),
                    page=int(meta["page"]) if meta.get("page") not in (None, "") else None,
                    section=str(meta.get("section", "")),
                    title=str(meta.get("title", "")),
                    chunk_id=str(meta.get("chunk_id", "")),
                    text=doc,
                    score=1.0 - float(distance),
                )
            )
        return chunks

    def build_chroma_index(self) -> int:
        import chromadb
        from sentence_transformers import SentenceTransformer

        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.chroma_dir))
        try:
            client.delete_collection("audit_rules")
        except Exception:
            pass
        collection = client.create_collection("audit_rules")
        chunks = self._fallback_chunks
        model = SentenceTransformer(self.embedding_model)
        embeddings = model.encode([c.text for c in chunks], normalize_embeddings=True).tolist()
        collection.add(
            ids=[c.chunk_id or f"chunk-{i}" for i, c in enumerate(chunks)],
            documents=[c.text for c in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "source": c.source,
                    "source_file": c.source_file or c.source,
                    "page": c.page if c.page is not None else "",
                    "section": c.section,
                    "title": c.title,
                    "chunk_id": c.chunk_id or "",
                }
                for c in chunks
            ],
        )
        return len(chunks)


def format_rag_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "未检索到相关准则片段。"
    lines = []
    for i, c in enumerate(chunks, 1):
        excerpt = c.text.replace("\n", " ").strip()
        if len(excerpt) > 900:
            excerpt = excerpt[:900] + "..."
        lines.append(f"[依据 {i}] 来源: {format_chunk_citation(c)}, score={c.score:.3f}\n{excerpt}")
    return "\n\n".join(lines)


def format_chunk_citation(chunk: RetrievedChunk) -> str:
    parts = [chunk.source_file or chunk.source]
    if chunk.page is not None:
        parts.append(f"第{chunk.page}页")
    if chunk.section:
        parts.append(chunk.section)
    if chunk.title and chunk.title not in parts:
        parts.append(chunk.title)
    return " | ".join(part for part in parts if part)


def _normalize_pdf_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(text: str, max_chars: int = 1000, overlap: int = 120) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else current + "\n\n" + paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            end = min(start + max_chars, len(paragraph))
            chunks.append(paragraph[start:end].strip())
            if end >= len(paragraph):
                break
            start = max(end - overlap, start + 1)
        current = ""
    if current:
        chunks.append(current)
    return chunks


def _chunk_pdf_text(text: str) -> list[str]:
    article_split = re.split(r"(?=第[一二三四五六七八九十百零〇]+条)", text)
    article_split = [part.strip() for part in article_split if part.strip()]
    if len(article_split) >= 2:
        chunks: list[str] = []
        for part in article_split:
            if len(part) <= 1100:
                chunks.append(part)
            else:
                chunks.extend(_chunk_text(part, max_chars=1100, overlap=120))
        return chunks
    return _chunk_text(text, max_chars=1000, overlap=120)


def _extract_markdown_metadata(text: str, filename: str) -> tuple[str, str]:
    title = ""
    section = ""
    first_header = next((line.strip() for line in text.splitlines() if line.strip().startswith("## ")), "")
    if first_header:
        section = first_header[3:].strip()
    top_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if top_line.startswith("# "):
        title = top_line[2:].strip()
    elif section:
        title = filename
    else:
        title = filename
    return section, title


def _extract_pdf_page_metadata(text: str) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = ""
    section = ""

    for line in lines[:10]:
        if "审计准则第" in line or "会计准则第" in line:
            title = re.sub(r"\s+", " ", line).strip()
            break

    chapter_line = next((line for line in lines if re.match(r"^第[一二三四五六七八九十百零]+章", line)), "")
    section_line = next((line for line in lines if re.match(r"^第[一二三四五六七八九十百零]+节", line)), "")
    article_line = next((line for line in lines if re.match(r"^第[一二三四五六七八九十百零]+条", line)), "")

    section_candidates = [candidate for candidate in [chapter_line, section_line, article_line] if candidate]
    if section_candidates:
        section = re.sub(r"\s+", " ", section_candidates[0]).strip()

    return {"title": title, "section": section}


def _extract_chunk_section(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    article_line = next((line for line in lines if re.match(r"^第[一二三四五六七八九十百零〇]+条", line)), "")
    chapter_line = next((line for line in lines if re.match(r"^第[一二三四五六七八九十百零]+章", line)), "")
    section_line = next((line for line in lines if re.match(r"^第[一二三四五六七八九十百零]+节", line)), "")
    candidate = article_line or section_line or chapter_line
    return re.sub(r"\s+", " ", candidate).strip() if candidate else ""


def _format_source_label(filename: str, page: int | None, section: str, title: str) -> str:
    parts = [filename]
    if page is not None:
        parts.append(f"第{page}页")
    if section:
        parts.append(section)
    if title and title not in parts:
        parts.append(title)
    return " | ".join(parts)
