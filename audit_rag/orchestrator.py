# -*- coding: utf-8 -*-
"""
Maker-Checker review loop orchestrator.

Replaces the pure round-robin in ``audit_rag.agents`` with a layered workflow:

    Data_Extractor → Compliance_Checker → Audit_Partner → Reviewer
                                                              │
                                ┌─────────────────────────────┴────┐
                                │                                  │
                            approved                           needs revision
                                │                                  │
                              DONE             rerun flagged agent(s) with
                                                  Reviewer's required_revisions
                                                  injected as context
                                                  │
                                          bounded by max_retries
                                                  │
                                                final pass
                                                  │
                                                 DONE / escalate_to_human

Design notes
------------
- The orchestrator is **mode-agnostic**: it takes pluggable callables for
  "rerun this maker" and "run reviewer", so the same loop logic works in
  mock mode, openai-compatible mode, and real autogen mode.
- Maker reruns are **scoped**: only the agents named by ``verdict.target_agents``
  are re-executed. Other turns are preserved verbatim (faster, cheaper,
  and prevents reviewer drift).
- After ``max_retries`` we surface the last verdict with
  ``next_action='escalate_to_human'`` and stop, instead of silently approving.
  This is the audit-safe failure mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from .agents import AgentTurn
from .critic import (
    ReviewVerdict,
    run_mock_reviewer,
)


REVIEWER_SPEAKER = "Reviewer"


# ──────────────────────────────────────────────────────────────────────────────
# Result container
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ReviewLoopResult:
    """Bundles the final turns + the full review trail."""

    turns: list[AgentTurn]
    """Final conversation including Reviewer turns interleaved after each pass."""

    verdicts: list[ReviewVerdict]
    """Every Reviewer verdict in chronological order."""

    iteration_count: int
    """How many review cycles ran (1 = approved on first try)."""

    final_status: str
    """One of: 'approved', 'escalated', 'max_retries_exhausted'."""

    revised_agents: list[str] = field(default_factory=list)
    """De-duplicated list of agents that had to redo their work at any point."""


# ──────────────────────────────────────────────────────────────────────────────
# Type aliases for injected callables
# ──────────────────────────────────────────────────────────────────────────────

# Given (agent_name, base_turns, reviewer_feedback) → fresh AgentTurn.
# Implementations rerun a single maker with the critic's required_revisions
# folded into its prompt context.
RerunMakerFn = Callable[[str, list[AgentTurn], ReviewVerdict], AgentTurn]

# Given (turns_so_far, attempt, prior_verdicts) → ReviewVerdict.
ReviewerFn = Callable[[list[AgentTurn], int, list[ReviewVerdict]], ReviewVerdict]


# ──────────────────────────────────────────────────────────────────────────────
# Core loop
# ──────────────────────────────────────────────────────────────────────────────


def run_review_loop(
    initial_turns: list[AgentTurn],
    *,
    reviewer: ReviewerFn,
    rerun_maker: RerunMakerFn,
    max_retries: int = 2,
) -> ReviewLoopResult:
    """Execute the Reviewer loop until approval, escalation, or retry exhaustion.

    Parameters
    ----------
    initial_turns:
        The output of the three maker agents from a regular round-robin pass.
        Must include exactly one ``AgentTurn`` per maker speaker.
    reviewer:
        Function that produces a ``ReviewVerdict`` given current turns,
        attempt index, and the list of prior verdicts. Inject the mock or
        LLM-backed reviewer here.
    rerun_maker:
        Function that re-executes a single maker agent, given its name,
        the current turns, and the verdict explaining what to fix.
    max_retries:
        Maximum number of revision rounds *after* the initial review.
        ``max_retries=0`` means single review with no revisions.

    Returns
    -------
    ReviewLoopResult
        Final turns (with Reviewer entries appended) + full audit trail.
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")

    turns: list[AgentTurn] = list(initial_turns)
    verdicts: list[ReviewVerdict] = []
    revised: list[str] = []

    # Attempt 0 = the initial review; attempts 1..max_retries are revision rounds.
    for attempt in range(max_retries + 1):
        verdict = reviewer(turns, attempt, verdicts)
        verdicts.append(verdict)
        turns.append(AgentTurn(REVIEWER_SPEAKER, verdict.to_markdown()))

        if verdict.approved:
            return ReviewLoopResult(
                turns=turns,
                verdicts=verdicts,
                iteration_count=attempt + 1,
                final_status="approved",
                revised_agents=revised,
            )

        if verdict.next_action == "escalate_to_human":
            return ReviewLoopResult(
                turns=turns,
                verdicts=verdicts,
                iteration_count=attempt + 1,
                final_status="escalated",
                revised_agents=revised,
            )

        if attempt == max_retries:
            # No budget left to rerun; surface the unresolved state.
            return ReviewLoopResult(
                turns=turns,
                verdicts=verdicts,
                iteration_count=attempt + 1,
                final_status="max_retries_exhausted",
                revised_agents=revised,
            )

        # Re-run each flagged agent in workflow order
        # (extractor → checker → partner) so downstream agents see upstream fixes.
        order = ["Data_Extractor", "Compliance_Checker", "Audit_Partner"]
        flagged = [name for name in order if name in verdict.target_agents]
        for agent_name in flagged:
            new_turn = rerun_maker(agent_name, turns, verdict)
            turns = _replace_turn(turns, agent_name, new_turn)
            if agent_name not in revised:
                revised.append(agent_name)

    # The for-loop always returns from inside; this line is defensive.
    return ReviewLoopResult(
        turns=turns,
        verdicts=verdicts,
        iteration_count=len(verdicts),
        final_status="max_retries_exhausted",
        revised_agents=revised,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _replace_turn(turns: list[AgentTurn], speaker: str, new_turn: AgentTurn) -> list[AgentTurn]:
    """Return a new list with the *first* turn matching ``speaker`` replaced.

    We replace rather than append so that the Reviewer-facing snapshot
    of "what the maker agents said" reflects the latest revision.
    Earlier Reviewer turns are preserved as the audit trail.
    """
    out: list[AgentTurn] = []
    replaced = False
    for turn in turns:
        if not replaced and turn.speaker == speaker:
            out.append(new_turn)
            replaced = True
        else:
            out.append(turn)
    if not replaced:
        out.append(new_turn)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Built-in mock orchestration (for mock mode end-to-end demos)
# ──────────────────────────────────────────────────────────────────────────────


def make_mock_reviewer(case_type: str, max_retries: int) -> ReviewerFn:
    """Return a ``ReviewerFn`` backed by the deterministic mock reviewer."""

    def _reviewer(turns: list[AgentTurn], attempt: int, prior: list[ReviewVerdict]) -> ReviewVerdict:
        # Only inspect turns from the maker agents (drop Reviewer noise).
        maker_turns = [t for t in turns if t.speaker != REVIEWER_SPEAKER]
        return run_mock_reviewer(maker_turns, case_type=case_type, attempt=attempt, max_retries=max_retries)

    return _reviewer


def make_mock_rerun_maker() -> RerunMakerFn:
    """Return a ``RerunMakerFn`` that simulates a revision in mock mode.

    The simulated revision appends a short "revised per Reviewer" addendum
    so the report visibly demonstrates that the maker responded to feedback
    without needing an LLM call.
    """

    def _rerun(agent_name: str, turns: list[AgentTurn], verdict: ReviewVerdict) -> AgentTurn:
        original = next((t for t in turns if t.speaker == agent_name), None)
        original_content = original.content if original else "(原始输出缺失)"
        relevant_issues = [
            issue for issue in verdict.issues if issue.target_agent == agent_name
        ]
        addendum_lines = ["", "---", f"**修订说明 (按 Reviewer 第 {verdict.attempt} 轮要求):**"]
        for i, issue in enumerate(relevant_issues, 1):
            addendum_lines.append(f"{i}. {issue.required_revision}")
            addendum_lines.append(_mock_revision_response(agent_name, issue))
        addendum = "\n".join(addendum_lines)
        return AgentTurn(speaker=agent_name, content=original_content + "\n" + addendum)

    return _rerun


def _mock_revision_response(agent_name: str, issue) -> str:
    """Canned revision text used by the mock rerun helper."""
    if agent_name == "Compliance_Checker":
        return (
            "   → 已补充: 对每项准则判断回填 [依据 X] 引用，并明确说明依据来源页码。"
        )
    if agent_name == "Audit_Partner":
        if "结构化" in issue.description:
            return "   → 已补充: 按'已识别事实 / 推断风险 / 待补充证据'三段重组结论。"
        if "金额" in issue.description or "影响" in issue.description:
            return "   → 已补充: 对每项高风险增加 ±10% 敏感性分析的金额影响区间。"
        return "   → 已补充: 针对 Reviewer 关切点补强论据。"
    if agent_name == "Data_Extractor":
        return "   → 已补充: 对每笔外币金额标注币种与折算汇率依据 (BOC 中间价)。"
    return "   → 已根据 Reviewer 要求补充。"


def run_mock_review_loop(
    initial_turns: list[AgentTurn],
    case_type: str,
    max_retries: int = 2,
) -> ReviewLoopResult:
    """Convenience wrapper: full review loop in mock mode, no callables required."""
    return run_review_loop(
        initial_turns=initial_turns,
        reviewer=make_mock_reviewer(case_type, max_retries=max_retries),
        rerun_maker=make_mock_rerun_maker(),
        max_retries=max_retries,
    )


# ──────────────────────────────────────────────────────────────────────────────
# LLM-backed orchestration (autogen / openai-compatible mode)
# ──────────────────────────────────────────────────────────────────────────────


def make_llm_reviewer(
    client,
    settings,
    case_description: str,
    case_type: str,
    max_retries: int,
) -> ReviewerFn:
    """Build a ``ReviewerFn`` that calls an OpenAI-compatible chat endpoint.

    Importing here (lazy) so mock mode never requires the openai package.
    """
    from .critic import (
        build_reviewer_system_prompt,
        build_reviewer_user_message,
        parse_reviewer_output,
    )

    def _reviewer(
        turns: list[AgentTurn], attempt: int, prior: list[ReviewVerdict]
    ) -> ReviewVerdict:
        system_prompt = build_reviewer_system_prompt(case_type, attempt, max_retries)
        user_msg = build_reviewer_user_message(
            case_description=case_description,
            turns_so_far=[t for t in turns if t.speaker != REVIEWER_SPEAKER],
            revision_history=prior,
        )
        try:
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,  # Determinism for the critic role.
            )
            raw = response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 — never crash audit on critic API error
            return parse_reviewer_output(
                f'{{"approved": false, "verdict_summary": "Reviewer API 调用失败: {exc}", '
                f'"issues": [], "next_action": "escalate_to_human"}}',
                attempt=attempt,
            )
        return parse_reviewer_output(raw, attempt=attempt)

    return _reviewer


def make_llm_rerun_maker(
    client,
    settings,
    case_description: str,
    case_type: str,
    agent_prompts: dict[str, str],
    rag_context: str,
    findings_text: str,
) -> RerunMakerFn:
    """Build a ``RerunMakerFn`` that re-invokes a maker agent via LLM API.

    The revision context includes:
    - The agent's original system prompt
    - Reviewer's specific required_revisions
    - The current snapshot of other agents' turns (for coherence)
    """

    def _rerun(agent_name: str, turns: list[AgentTurn], verdict: ReviewVerdict) -> AgentTurn:
        system_prompt = agent_prompts.get(agent_name, "")
        relevant_issues = [
            issue for issue in verdict.issues if issue.target_agent == agent_name
        ]
        revision_block = "\n".join(
            f"- [{issue.severity}] {issue.description}\n  要求修订: {issue.required_revision}"
            for issue in relevant_issues
        )
        peer_outputs = "\n\n".join(
            f"--- {t.speaker} ---\n{t.content}"
            for t in turns
            if t.speaker not in {agent_name, REVIEWER_SPEAKER}
        )
        user_msg = (
            f"[审计任务]\n{case_description}\n\n"
            f"[数据提取发现]\n{findings_text}\n\n"
            f"[RAG 检索依据]\n{rag_context}\n\n"
            f"[其他 Agent 的当前输出]\n{peer_outputs}\n\n"
            f"[Reviewer 要求 (你必须按此修订)]\n{revision_block}\n\n"
            "请输出修订后的完整版本（不要只写差异）。"
        )
        try:
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=settings.temperature,
            )
            content = (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            content = f"(修订失败: {exc}; 保留原始输出)"
        if not content:
            content = "(空响应; 保留原始输出)"
        return AgentTurn(speaker=agent_name, content=content)

    return _rerun
