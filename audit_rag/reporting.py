# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .agents import AgentTurn
from .data_tools import Finding, Voucher, format_findings
from .rag import RetrievedChunk, format_rag_context

CASE_LABELS = {
    "fixed_asset": "固定资产专项审计",
    "cross_border": "跨境电商专项审计",
}


def _risk_summary_table(findings: list[Finding]) -> str:
    if not findings:
        return "本次样本未识别出需关注的审计风险事项。\n"

    high = [f for f in findings if f.risk_level == "高"]
    mid = [f for f in findings if f.risk_level == "中"]
    low = [f for f in findings if f.risk_level not in ("高", "中")]

    lines = [
        "| 风险等级 | 数量 | 主要事项 |",
        "| --- | --- | --- |",
    ]
    if high:
        issues = "、".join(f.issue for f in high)
        lines.append(f"| **高** | {len(high)} | {issues} |")
    if mid:
        issues = "、".join(f.issue for f in mid)
        lines.append(f"| **中** | {len(mid)} | {issues} |")
    if low:
        issues = "、".join(f.issue for f in low)
        lines.append(f"| **低** | {len(low)} | {issues} |")
    return "\n".join(lines)


def write_audit_report(
    reports_dir: Path,
    case_description: str,
    vouchers: list[Voucher],
    findings: list[Finding],
    rag_chunks: list[RetrievedChunk],
    turns: list[AgentTurn],
    mode: str,
    case_type: str = "fixed_asset",
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    case_label = CASE_LABELS.get(case_type, case_type)
    filename = f"{stamp}_{case_type}_{mode}.md"
    path = reports_dir / filename

    high_count = sum(1 for f in findings if f.risk_level == "高")
    mid_count = sum(1 for f in findings if f.risk_level == "中")

    lines = [
        f"# 多Agent审计小组工作底稿 — {case_label}",
        "",
        "---",
        "",
        "## 基本信息",
        "",
        f"| 项目 | 内容 |",
        f"| --- | --- |",
        f"| 生成时间 | {now.strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| 运行模式 | {mode} |",
        f"| 审计场景 | {case_label} |",
        f"| 样本凭证数 | {len(vouchers)} 条 |",
        f"| 识别发现数 | 高风险 {high_count} 项 / 中风险 {mid_count} 项 |",
        "",
        "---",
        "",
        "## 审计任务描述",
        "",
        case_description,
        "",
        "---",
        "",
        "## 风险汇总",
        "",
        _risk_summary_table(findings),
        "",
        "---",
        "",
        "## 数据提取发现（明细）",
        "",
        format_findings(findings),
        "",
        "---",
        "",
        "## RAG 知识库检索依据",
        "",
        format_rag_context(rag_chunks),
        "",
        "---",
        "",
        "## 多Agent审计讨论记录",
        "",
    ]

    for turn in turns:
        speaker_label = {
            "Data_Extractor": "数据提取助理 (Data_Extractor)",
            "Compliance_Checker": "合规检查专家 (Compliance_Checker)",
            "Audit_Partner": "签字合伙人 (Audit_Partner)",
        }.get(turn.speaker, turn.speaker)
        lines += [f"### {speaker_label}", "", turn.content, ""]

    lines += [
        "---",
        "",
        "## 审计结论与后续程序要求",
        "",
    ]

    if findings:
        lines.append("根据上述多Agent分析，后续须重点执行以下程序:\n")
        for idx, finding in enumerate(findings, start=1):
            lines.append(f"**{idx}. [{finding.risk_level}风险] {finding.issue}**")
            lines.append(f"   - 凭证: `{finding.voucher_id}`")
            lines.append(f"   - 建议程序: {finding.suggested_procedure}")
            lines.append("")
    else:
        lines.append("本次审计样本未识别出重大异常，建议维持原定审计计划，按时完成常规实质性程序。\n")

    lines += [
        "---",
        "",
        f"*本工作底稿由多Agent AI审计系统自动生成，仅供审计人员参考，最终审计结论以注册会计师专业判断为准。*",
        "",
    ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
