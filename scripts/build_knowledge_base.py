# -*- coding: utf-8 -*-
from __future__ import annotations

from audit_multi_agent_rag.audit_rag.config import get_settings
from audit_multi_agent_rag.audit_rag.rag import AuditKnowledgeBase


def main() -> None:
    settings = get_settings()
    kb = AuditKnowledgeBase([settings.sample_knowledge_dir, settings.local_knowledge_dir], settings.chroma_dir)
    try:
        count = kb.build_chroma_index()
    except Exception as exc:
        print("ChromaDB index was not built.")
        print("Reason:", exc)
        print("The prototype can still run in keyword fallback mode:")
        print("python -m audit_multi_agent_rag.scripts.run_phase1_demo --mode mock")
        return
    print(f"Built ChromaDB audit_rules collection with {count} chunks.")
    print(f"Persist dir: {settings.chroma_dir}")
    print(f"Sample knowledge dir: {settings.sample_knowledge_dir}")
    print(f"Local knowledge dir: {settings.local_knowledge_dir}")


if __name__ == "__main__":
    main()
