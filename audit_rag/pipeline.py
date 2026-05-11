# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .agents import (
    AgentTurn,
    run_autogen_groupchat,
    run_mock_groupchat,
    run_mock_cross_border_groupchat,
)
from .config import Settings, get_settings
from .critic import ReviewVerdict
from .data_tools import (
    Finding,
    Voucher,
    analyze_vouchers,
    analyze_cross_border_vouchers,
    load_vouchers,
)
from .orchestrator import (
    ReviewLoopResult,
    run_mock_review_loop,
)
from .rag import AuditKnowledgeBase, RetrievedChunk
from .reporting import write_audit_report


DEFAULT_CASE = "公司将一笔本应资本化的服务器设备采购支出计入管理费用，请识别审计风险并形成初步审计意见。"
CROSS_BORDER_CASE = (
    "跨境电商企业同时运营Amazon和TikTok多平台业务，涉及多币种收入确认、"
    "FBA海外仓库存管理、境外关联方转让定价及进出口合规等复杂审计场景，"
    "请识别重大错报风险并形成跨境电商专项审计意见。"
)
DEFAULT_RAG_QUERY = ""

CASE_PRESETS: dict[str, dict] = {
    "fixed_asset": {
        "description": DEFAULT_CASE,
        "voucher_filename": "vouchers.csv",
        "rag_keywords": ["固定资产", "资本性支出", "费用化", "管理费用"],
    },
    "cross_border": {
        "description": CROSS_BORDER_CASE,
        "voucher_filename": "cross_border_vouchers.csv",
        "rag_keywords": ["收入确认", "外币折算", "关联方", "转让定价", "存货跌价", "跨境电商"],
    },
}


@dataclass(frozen=True)
class AuditPipelineResult:
    settings: Settings
    mode: str
    case_type: str
    case_description: str
    voucher_path: Path
    vouchers: list[Voucher]
    findings: list[Finding]
    rag_chunks: list[RetrievedChunk]
    turns: list[AgentTurn]
    report_path: Path

    # Review-loop artifacts (None when enable_review_loop is False).
    review_verdicts: list[ReviewVerdict] | None = None
    review_status: str | None = None  # 'approved' | 'escalated' | 'max_retries_exhausted'
    review_iterations: int = 0
    revised_agents: list[str] | None = None


def run_audit_pipeline(
    mode: str = "mock",
    case_type: str = "fixed_asset",
    case_description: str = "",
    voucher_file: str = "",
    rag_query: str = DEFAULT_RAG_QUERY,
) -> AuditPipelineResult:
    settings = get_settings()
    preset = CASE_PRESETS.get(case_type, CASE_PRESETS["fixed_asset"])

    effective_description = case_description.strip() or preset["description"]
    voucher_path = resolve_voucher_path(settings, voucher_file, preset["voucher_filename"])

    vouchers = load_vouchers(voucher_path)
    if case_type == "cross_border":
        findings = analyze_cross_border_vouchers(vouchers)
    else:
        findings = analyze_vouchers(vouchers)

    kb = AuditKnowledgeBase(
        [settings.sample_knowledge_dir, settings.local_knowledge_dir],
        settings.chroma_dir,
        enable_hybrid=settings.rag_enable_hybrid,
        enable_rerank=settings.rag_enable_rerank,
        reranker_model=settings.rag_reranker_model,
    )
    effective_query = rag_query.strip() or build_rag_query(effective_description, preset["rag_keywords"])
    rag_chunks = kb.search(effective_query, top_k=settings.rag_top_k)

    if mode == "autogen":
        turns = run_autogen_groupchat(settings, effective_description, findings, rag_chunks, case_type)
    elif mode == "mock":
        if case_type == "cross_border":
            turns = run_mock_cross_border_groupchat(effective_description, findings, rag_chunks)
        else:
            turns = run_mock_groupchat(effective_description, findings, rag_chunks)
    else:
        raise ValueError(f"Unsupported mode: {mode!r}")

    # ── Maker-Checker 复核回路 ─────────────────────────────────────────────
    review_verdicts = None
    review_status = None
    review_iterations = 0
    revised_agents = None
    if settings.enable_review_loop:
        if mode == "mock":
            loop_result = run_mock_review_loop(
                initial_turns=turns,
                case_type=case_type,
                max_retries=settings.review_max_retries,
            )
        else:
            # LLM 模式: 用 make_llm_reviewer / make_llm_rerun_maker 构造回调
            from openai import OpenAI
            from .agents import _select_prompts
            from .data_tools import format_findings
            from .orchestrator import make_llm_reviewer, make_llm_rerun_maker
            from .rag import format_rag_context

            client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
            data_p, comp_p, partner_p = _select_prompts(case_type)
            loop_result = run_review_loop(
                initial_turns=turns,
                reviewer=make_llm_reviewer(
                    client, settings, effective_description, case_type, settings.review_max_retries
                ),
                rerun_maker=make_llm_rerun_maker(
                    client, settings, effective_description, case_type,
                    agent_prompts={
                        "Data_Extractor": data_p,
                        "Compliance_Checker": comp_p,
                        "Audit_Partner": partner_p,
                    },
                    rag_context=format_rag_context(rag_chunks),
                    findings_text=format_findings(findings),
                ),
                max_retries=settings.review_max_retries,
            )
        turns = loop_result.turns
        review_verdicts = loop_result.verdicts
        review_status = loop_result.final_status
        review_iterations = loop_result.iteration_count
        revised_agents = loop_result.revised_agents

    report_path = write_audit_report(
        reports_dir=settings.reports_dir,
        case_type=case_type,
        case_description=effective_description,
        vouchers=vouchers,
        findings=findings,
        rag_chunks=rag_chunks,
        turns=turns,
        mode=mode,
        review_verdicts=review_verdicts,
        review_status=review_status,
        review_iterations=review_iterations,
    )

    return AuditPipelineResult(
        settings=settings,
        mode=mode,
        case_type=case_type,
        case_description=effective_description,
        voucher_path=voucher_path,
        vouchers=vouchers,
        findings=findings,
        rag_chunks=rag_chunks,
        turns=turns,
        report_path=report_path,
        review_verdicts=review_verdicts,
        review_status=review_status,
        review_iterations=review_iterations,
        revised_agents=revised_agents,
    )


def resolve_voucher_path(settings: Settings, voucher_file: str, fallback_filename: str = "vouchers.csv") -> Path:
    if voucher_file:
        raw_path = Path(voucher_file)
        if raw_path.is_absolute():
            return raw_path
        return settings.project_root / raw_path
    return settings.sample_data_path.parent / fallback_filename


def build_rag_query(case_description: str, preset_keywords: list[str] | None = None) -> str:
    base_terms = ["审计程序"]
    extra_terms: list[str] = list(preset_keywords or [])
    keyword_candidates = [
        "固定资产",
        "资本性支出",
        "费用化",
        "管理费用",
        "收入",
        "截止",
        "应付账款",
        "未入账负债",
        "关联方",
        "会计估计",
        "减值",
        "舞弊",
        "审计准则",
        "企业会计准则",
    ]
    for keyword in keyword_candidates:
        if keyword in case_description and keyword not in extra_terms:
            extra_terms.append(keyword)

    case_terms = [term for term in _tokenize_case_terms(case_description) if term not in extra_terms]
    query_terms = extra_terms + case_terms[:10]
    if "审计程序" not in query_terms:
        query_terms.extend(base_terms)
    return " ".join(query_terms)


def _tokenize_case_terms(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]{2,}", text)
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        normalized = token.strip()
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered
