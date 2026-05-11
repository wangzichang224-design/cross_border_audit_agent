# tests/test_critic.py
import json
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_rag.agents import AgentTurn
from audit_rag.critic import (
    ReviewVerdict, parse_reviewer_output, run_mock_reviewer
)
from audit_rag.orchestrator import run_mock_review_loop


class TestParser(unittest.TestCase):
    def test_clean_json(self):
        raw = '{"approved": true, "verdict_summary": "ok", "issues": [], "next_action": "approve"}'
        v = parse_reviewer_output(raw)
        self.assertTrue(v.approved)

    def test_strips_markdown_fence(self):
        raw = '```json\n{"approved": false, "verdict_summary": "bad", "issues": [], "next_action": "revise"}\n```'
        v = parse_reviewer_output(raw)
        self.assertFalse(v.approved)

    def test_invariant_approved_with_issues(self):
        # approved=true 但有 issue → 强制改成 revise
        raw = '{"approved": true, "issues": [{"severity":"high","target_agent":"Audit_Partner","description":"x","required_revision":"y"}], "next_action":"approve", "verdict_summary":""}'
        v = parse_reviewer_output(raw)
        self.assertFalse(v.approved)

    def test_garbage_returns_escalation_or_revise(self):
        v = parse_reviewer_output("not json at all", attempt=0)
        self.assertFalse(v.approved)
        v2 = parse_reviewer_output("not json", attempt=1)
        self.assertEqual(v2.next_action, "escalate_to_human")


class TestMockReviewer(unittest.TestCase):
    def _turns_missing_evidence(self):
        return [
            AgentTurn("Data_Extractor", "异常凭证 100 万"),
            AgentTurn("Compliance_Checker", "合规分析（没有依据引用）"),
            AgentTurn("Audit_Partner", "已识别事实: x\n推断风险: y\n待补充证据: z"),
        ]

    def test_flags_missing_evidence_citation(self):
        v = run_mock_reviewer(self._turns_missing_evidence(), "fixed_asset", attempt=0, max_retries=2)
        self.assertFalse(v.approved)
        self.assertIn("Compliance_Checker", v.target_agents)

    def test_cross_border_requires_currency(self):
        turns = [
            AgentTurn("Data_Extractor", "异常凭证 100 万元"),
            AgentTurn("Compliance_Checker", "见 [依据 1]"),
            AgentTurn("Audit_Partner", "已识别事实 推断风险 待补充证据"),
        ]
        v = run_mock_reviewer(turns, "cross_border", attempt=0, max_retries=2)
        self.assertIn("Data_Extractor", v.target_agents)


class TestReviewLoop(unittest.TestCase):
    def test_converges_within_max_retries(self):
        # mock reviewer 在第二轮一般会通过 (因为 rerun_maker 会注入修订)
        turns = [
            AgentTurn("Data_Extractor", "USD 100 @7.12 折人民币 712"),
            AgentTurn("Compliance_Checker", "见 [依据 1]"),
            AgentTurn("Audit_Partner", "已识别事实\n推断风险\n待补充证据"),
        ]
        result = run_mock_review_loop(turns, "cross_border", max_retries=2)
        self.assertIn(result.final_status, {"approved", "max_retries_exhausted", "escalated"})
        self.assertGreaterEqual(result.iteration_count, 1)
        self.assertEqual(len([v for v in result.verdicts]), result.iteration_count)

    def test_escalation_when_no_budget(self):
        result = run_mock_review_loop([], "fixed_asset", max_retries=0)
        # max_retries=0 且有问题 → exhausted
        self.assertEqual(result.iteration_count, 1)


if __name__ == "__main__":
    unittest.main()
