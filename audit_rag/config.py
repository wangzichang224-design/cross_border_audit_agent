# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv_file(path: Path | None = None) -> None:
    """Small .env loader to avoid making python-dotenv mandatory for mock mode."""
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.lstrip("\ufeff").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str
    deepseek_base_url: str
    llm_model: str
    temperature: float
    max_rounds: int
    rag_top_k: int
    feishu_app_id: str
    feishu_app_secret: str
    feishu_verification_token: str
    feishu_host: str
    feishu_port: int
    feishu_path: str
    feishu_default_mode: str
    project_root: Path
    sample_data_path: Path
    sample_knowledge_dir: Path
    local_knowledge_dir: Path
    chroma_dir: Path
    reports_dir: Path
    # Retrieval upgrades (Phase: advanced RAG)
    rag_enable_hybrid: bool
    rag_enable_rerank: bool
    rag_reranker_model: str
    # Orchestration upgrades (Phase: Maker-Checker review loop)
    enable_review_loop: bool
    review_max_retries: int


def get_settings() -> Settings:
    load_dotenv_file()
    reports_dir = PROJECT_ROOT / "output" / "audit_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        llm_model=os.getenv("LLM_MODEL", "deepseek-chat"),
        temperature=float(os.getenv("TEMPERATURE", "0.2")),
        max_rounds=int(os.getenv("MAX_ROUNDS", "7")),
        rag_top_k=int(os.getenv("RAG_TOP_K", "4")),
        feishu_app_id=os.getenv("FEISHU_APP_ID", ""),
        feishu_app_secret=os.getenv("FEISHU_APP_SECRET", ""),
        feishu_verification_token=os.getenv("FEISHU_VERIFICATION_TOKEN", ""),
        feishu_host=os.getenv("FEISHU_HOST", "0.0.0.0"),
        feishu_port=int(os.getenv("FEISHU_PORT", "8001")),
        feishu_path=os.getenv("FEISHU_PATH", "/feishu/webhook"),
        feishu_default_mode=os.getenv("FEISHU_DEFAULT_MODE", "autogen"),
        project_root=PROJECT_ROOT,
        sample_data_path=PROJECT_ROOT / "sample_data" / "vouchers.csv",
        sample_knowledge_dir=PROJECT_ROOT / "sample_knowledge",
        local_knowledge_dir=PROJECT_ROOT / "knowledge_sources",
        chroma_dir=PROJECT_ROOT / "data" / "chroma_audit_rules",
        reports_dir=reports_dir,
        rag_enable_hybrid=_env_bool("RAG_ENABLE_HYBRID", default=True),
        rag_enable_rerank=_env_bool("RAG_ENABLE_RERANK", default=False),
        rag_reranker_model=os.getenv("RAG_RERANKER_MODEL", "BAAI/bge-reranker-base"),
        enable_review_loop=_env_bool("AUDIT_ENABLE_REVIEW_LOOP", default=True),
        review_max_retries=int(os.getenv("AUDIT_REVIEW_MAX_RETRIES", "2")),
    )


def _env_bool(name: str, *, default: bool) -> bool:
    """Parse boolean-ish env vars (1/true/yes/on are True; everything else False).

    Hybrid is ON by default because BM25 has no extra dependency and improves
    accuracy on准则编号 lookups. Rerank is OFF by default because the model
    weights are ~280 MB and must be downloaded on first use.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def build_llm_config(settings: Settings) -> dict:
    """Return a classic pyautogen-compatible OpenAI-style config."""
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is empty. Use --mode mock or set audit_multi_agent_rag/.env.")

    return {
        "config_list": [
            {
                "model": settings.llm_model,
                "api_key": settings.deepseek_api_key,
                "base_url": settings.deepseek_base_url,
            }
        ],
        "temperature": settings.temperature,
    }
