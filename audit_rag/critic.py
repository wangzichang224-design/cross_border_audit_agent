# -*- coding: utf-8 -*-
"""
Reviewer (Critic) for the audit multi-agent system.

Implements the Maker-Checker pattern used in real audit workflows:
the three "maker" agents (Data_Extractor / Compliance_Checker / Audit_Partner)
produce their analysis, and a senior Reviewer scrutinizes the output before
the workpaper is finalized. If the Reviewer rejects, the targeted agent
re-runs with the Reviewer's required revisions injected into its context.

Why a separate Critic instead of just longer prompts?
- A dedicated reviewer with its own system prompt is closer to how a Big-4
  engagement team actually works (manager review, partner review).
- Structured JSON output lets us *route mechanically*: orchestrator reads
  ``target_agent`` and reruns just that agent, not the whole conversation.
- Bounded retries prevent the loop from burning tokens forever — after
  ``max_retries`` we escalate to "needs human review", which is the
  audit-friendly failure mode (don't auto-sign a flawed workpaper).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Literal


# ──────────────────────────────────────────────────────────────────────────────
# Verdict schema
# ──────────────────────────────────────────────────────────────────────────────


Severity = Literal["low", "medium", "high", "critical"]
NextAction = Literal["approve", "revise", "escalate_to_human"]


@dataclass(frozen=True)
class ReviewIssue:
    """A single problem the Reviewer found in an agent's output."""

    severity: Severity
    target_agent: str  # which maker agent must redo their work
    description: str
    required_revision: str


@dataclass(frozen=True)
class ReviewVerdict:
    """Structured output of one Reviewer pass."""

    approved: bool
    verdict_summary: str
    issues: list[ReviewIssue] = field(default_factory=list)
    next_action: NextAction = "approve"
    attempt: int = 0  # 0-based: which retry cycle this verdict belongs to

    @property
    def needs_revision(self) -> bool:
        return self.next_action == "revise" and bool(self.issues)

    @property
    def target_agents(self) -> list[str]:
        """De-duplicated list of agents flagged across all issues."""
        seen: list[str] = []
        for issue in self.issues:
            if issue.target_agent and issue.target_agent not in seen:
                seen.append(issue.target_agent)
        return seen

    def to_markdown(self) -> str:
        """Render the verdict as the Reviewer's "turn" in the report."""
        status = "✅ 通过" if self.approved else "❌ 需修订"
        if self.next_action == "escalate_to_human":
            status = "⚠️ 升级人工复核"
        lines = [f"**复核裁定:** {status}", "", f"**裁定摘要:** {self.verdict_summary}", ""]
        if self.issues:
            lines.append("**发现的问题:**")
            for i, issue in enumerate(self.issues, 1):
                lines.append(
                    f"{i}. [{issue.severity.upper()}] 针对 `{issue.target_agent}`: "
                    f"{issue.description}"
                )
                lines.append(f"   - 要求修订: {issue.required_revision}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Reviewer prompts
# ──────────────────────────────────────────────────────────────────────────────


REVIEWER_PROMPT_TEMPLATE = """你是 Reviewer，事务所质量复核合伙人，资历高于 Audit_Partner。

你的职责:
1. 审查 Data_Extractor / Compliance_Checker / Audit_Partner 三位 Agent 的输出。
2. 检查以下质量门槛 (任一不达标即驳回):
   - 是否充分引用 RAG 检索依据 (出现 [依据 X] 字样且与发现对应)
   - 是否区分"已识别事实 / 推断风险 / 待补充证据"三类结论
   - 高/中风险事项是否给出具体的追加审计程序
   - 金额是否标注币种与折算汇率 (跨境场景)
   - 是否避免凭空引用准则条款编号
3. 必须以严格 JSON 格式输出裁定，禁止使用 markdown 代码块包裹。

JSON 输出 schema:
{{
  "approved": <true|false>,
  "verdict_summary": "<不超过 60 字的总评>",
  "issues": [
    {{
      "severity": "low|medium|high|critical",
      "target_agent": "Data_Extractor|Compliance_Checker|Audit_Partner",
      "description": "<具体问题描述>",
      "required_revision": "<被复核 Agent 必须如何修订, 可执行>"
    }}
  ],
  "next_action": "approve|revise|escalate_to_human"
}}

裁定规则:
- approved=true 当且仅当 issues 为空且质量门槛全部通过。
- 高严重度问题 (severity in [high, critical]) 强制 next_action=revise。
- 这是第 {attempt} 次复核 (从 0 开始); 当 attempt >= {max_retries} 且仍有高严重度问题时, next_action 必须为 escalate_to_human。

当前审计场景: {case_type_label}
"""


def build_reviewer_system_prompt(case_type: str, attempt: int, max_retries: int) -> str:
    case_type_label = {
        "fixed_asset": "固定资产专项审计 (CAS 4)",
        "cross_border": "跨境电商专项审计 (CAS 14 / CAS 19 / CAS 1 / OECD TP)",
    }.get(case_type, case_type)
    return REVIEWER_PROMPT_TEMPLATE.format(
        case_type_label=case_type_label,
        attempt=attempt,
        max_retries=max_retries,
    )


def build_reviewer_user_message(
    case_description: str,
    turns_so_far: list,  # list[AgentTurn] — typed via local import to avoid cycle
    revision_history: list[ReviewVerdict] | None = None,
) -> str:
    parts = ["[审计任务]", case_description, "", "[三位 Maker Agent 输出]"]
    for turn in turns_so_far:
        parts.append(f"\n--- {turn.speaker} ---\n{turn.content}")

    if revision_history:
        parts.append("\n[历史复核裁定]")
        for v in revision_history:
            parts.append(f"\n第 {v.attempt} 轮: approved={v.approved}, summary={v.verdict_summary}")

    parts.append("\n现在请输出本轮复核裁定 JSON。")
    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# JSON parsing — robust against LLM stragglers like markdown wrappers
# ──────────────────────────────────────────────────────────────────────────────


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_reviewer_output(raw_text: str, attempt: int = 0) -> ReviewVerdict:
    """Parse Reviewer's response into a ReviewVerdict.

    Defensive parsing:
    - Strip markdown code fences if present.
    - Extract the first top-level JSON object (LLM sometimes prepends a
      "好的，以下是复核结果:" preamble even when told not to).
    - On any failure, return a safe escalation verdict — the audit pipeline
      should never trust an unparseable critique as "approved".
    """
    if not raw_text or not raw_text.strip():
        return _failure_verdict("Reviewer 返回为空", attempt)

    cleaned = raw_text.strip()
    # Strip ```json ... ``` wrappers.
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()

    # If there's prose before the JSON, grab the first {...} block.
    match = _JSON_BLOCK_RE.search(cleaned)
    if not match:
        return _failure_verdict("Reviewer 未返回可解析的 JSON", attempt)

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return _failure_verdict(f"Reviewer JSON 解析失败: {exc.msg}", attempt)

    return _verdict_from_dict(data, attempt)


def _verdict_from_dict(data: dict, attempt: int) -> ReviewVerdict:
    approved = bool(data.get("approved", False))
    summary = str(data.get("verdict_summary", "(无摘要)")).strip()
    next_action = str(data.get("next_action", "")).strip().lower()
    if next_action not in {"approve", "revise", "escalate_to_human"}:
        next_action = "approve" if approved else "revise"

    issues_raw = data.get("issues") or []
    issues: list[ReviewIssue] = []
    for item in issues_raw:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity", "medium")).strip().lower()
        if severity not in {"low", "medium", "high", "critical"}:
            severity = "medium"
        issues.append(
            ReviewIssue(
                severity=severity,  # type: ignore[arg-type]
                target_agent=str(item.get("target_agent", "Audit_Partner")).strip(),
                description=str(item.get("description", "")).strip(),
                required_revision=str(item.get("required_revision", "")).strip(),
            )
        )

    # Enforce invariants: approved & non-empty issues is inconsistent.
    if approved and issues:
        approved = False
        next_action = "revise"

    return ReviewVerdict(
        approved=approved,
        verdict_summary=summary,
        issues=issues,
        next_action=next_action,  # type: ignore[arg-type]
        attempt=attempt,
    )


def _failure_verdict(reason: str, attempt: int) -> ReviewVerdict:
    """Defensive default when the Reviewer output is unusable.

    We deliberately set ``approved=False`` so a parse failure can never
    promote a flawed workpaper to "signed off". The orchestrator will
    treat this as a revision request — and if it keeps happening, escalate.
    """
    return ReviewVerdict(
        approved=False,
        verdict_summary=f"复核失败: {reason}",
        issues=[
            ReviewIssue(
                severity="high",
                target_agent="Audit_Partner",
                description=reason,
                required_revision="请重新输出符合 JSON schema 的复核裁定。",
            )
        ],
        next_action="escalate_to_human" if attempt >= 1 else "revise",
        attempt=attempt,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Mock Reviewer (offline / no-API mode)
# ──────────────────────────────────────────────────────────────────────────────


def run_mock_reviewer(
    turns,  # list[AgentTurn]
    case_type: str,
    attempt: int,
    max_retries: int,
) -> ReviewVerdict:
    """A deterministic Reviewer that runs quality checks without an LLM.

    Real checks performed:
      1. Audit_Partner output must contain "已识别事实" / "推断风险" / "待补充证据"
         section markers (or equivalents).
      2. Compliance_Checker output must cite [依据 X].
      3. Cross-border scenario: Data_Extractor must mention currency conversion.

    On the first attempt, we intentionally flag at least one issue so the
    review loop demonstrates a real revision cycle. On the second pass we
    accept (assuming revisions were applied). This makes the mock mode
    *show off the workflow* rather than rubber-stamp.
    """
    by_speaker = {t.speaker: t.content for t in turns}

    issues: list[ReviewIssue] = []

    # Check 1: Compliance must cite evidence.
    compliance = by_speaker.get("Compliance_Checker", "")
    if compliance and "[依据" not in compliance:
        issues.append(
            ReviewIssue(
                severity="high",
                target_agent="Compliance_Checker",
                description="合规分析未引用 RAG 检索依据 [依据 X]，无法回溯出处。",
                required_revision="重写时必须对每条准则判断附 [依据 1]/[依据 2] 等引用。",
            )
        )

    # Check 2: Partner must structure conclusions.
    partner = by_speaker.get("Audit_Partner", "")
    required_sections = ["已识别事实", "推断风险", "待补充证据"]
    if partner and not all(section in partner for section in required_sections):
        missing = [s for s in required_sections if s not in partner]
        issues.append(
            ReviewIssue(
                severity="medium",
                target_agent="Audit_Partner",
                description=f"复核意见缺少结构化分节: {', '.join(missing)}。",
                required_revision="按'已识别事实/推断风险/待补充证据'三段重组结论。",
            )
        )

    # Check 3: Cross-border requires currency disclosure.
    if case_type == "cross_border":
        data_text = by_speaker.get("Data_Extractor", "")
        if data_text and not any(token in data_text for token in ["汇率", "USD", "外币", "折算"]):
            issues.append(
                ReviewIssue(
                    severity="high",
                    target_agent="Data_Extractor",
                    description="跨境场景下未标注币种或折算汇率。",
                    required_revision="对每笔外币金额标注币种和折算汇率依据。",
                )
            )

    # First-attempt staging: if everything looks clean, inject a soft pedagogical
    # nudge so the demo shows the loop even on golden mock data. This is gated
    # so it only fires once and only if the mock outputs really passed checks.
    if attempt == 0 and not issues:
        issues.append(
            ReviewIssue(
                severity="medium",
                target_agent="Audit_Partner",
                description="复核意见未明确量化每项风险对财务报表的影响金额上下限。",
                required_revision="补充每项高风险的金额影响区间估算 (例如 ±10% 敏感性)。",
            )
        )

    if not issues:
        return ReviewVerdict(
            approved=True,
            verdict_summary="三方输出质量达标，依据引用充分、结论结构完整。",
            issues=[],
            next_action="approve",
            attempt=attempt,
        )

    has_high = any(issue.severity in {"high", "critical"} for issue in issues)
    if attempt >= max_retries and has_high:
        next_action: NextAction = "escalate_to_human"
        summary = f"经 {attempt + 1} 轮复核仍存在高风险问题，升级人工复核。"
    else:
        next_action = "revise"
        summary = f"识别 {len(issues)} 项问题需修订 (本轮 attempt={attempt})。"

    return ReviewVerdict(
        approved=False,
        verdict_summary=summary,
        issues=issues,
        next_action=next_action,
        attempt=attempt,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers for orchestrator
# ──────────────────────────────────────────────────────────────────────────────


def verdict_to_dict(verdict: ReviewVerdict) -> dict:
    """For JSON serialization in reports / telemetry."""
    return {
        **asdict(verdict),
        "issues": [asdict(issue) for issue in verdict.issues],
    }
