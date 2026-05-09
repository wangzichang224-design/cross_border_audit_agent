"""
DeepSeek LLM client — OpenAI-compatible API wrapper.
Mirrors LLMClassifier / LLMAuditAnalyst interfaces so orchestrator
can swap providers without touching business logic.
"""

import json
import logging

import pandas as pd
from openai import OpenAI

from .prompts import CLASSIFY_TRANSACTIONS_PROMPT, ANOMALY_DETECTION_PROMPT

logger = logging.getLogger(__name__)

BATCH_SIZE = 20


class DeepSeekClassifier:
    """Classifies ambiguous transactions using DeepSeek (deepseek-chat)."""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.model = model

    def classify_unclassified(self, df: pd.DataFrame) -> pd.DataFrame:
        mask = df["category"] == "Unclassified"
        unclassified = df[mask].copy()

        if unclassified.empty:
            logger.info("No unclassified transactions — skipping DeepSeek classification")
            return df

        logger.info(f"Classifying {len(unclassified)} transactions via DeepSeek...")

        all_results = []
        for start in range(0, len(unclassified), BATCH_SIZE):
            batch = unclassified.iloc[start: start + BATCH_SIZE]
            all_results.extend(self._classify_batch(batch))

        results_map = {r["txn_id"]: r for r in all_results}
        for idx, row in unclassified.iterrows():
            result = results_map.get(row["txn_id"])
            if result:
                df.at[idx, "category"] = result.get("predicted_category", "Unclassified")
                df.at[idx, "llm_confidence"] = result.get("confidence", "LOW")
                df.at[idx, "llm_rationale"] = result.get("rationale", "")
                df.at[idx, "llm_risk_flag"] = result.get("risk_flag", False)
            else:
                df.at[idx, "llm_confidence"] = "FAILED"
                df.at[idx, "llm_risk_flag"] = False

        classified = (df.loc[mask, "category"] != "Unclassified").sum()
        logger.info(f"DeepSeek classified {classified}/{len(unclassified)} transactions")
        return df

    def _classify_batch(self, batch: pd.DataFrame) -> list[dict]:
        txn_json = batch[["txn_id", "description", "amount_usd", "platform", "date"]].to_json(
            orient="records", indent=2
        )
        prompt = CLASSIFY_TRANSACTIONS_PROMPT.format(transactions_json=txn_json)

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a forensic accountant AI assistant. "
                            "Always return valid JSON exactly as specified. No markdown code blocks."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            logger.error(f"DeepSeek classification batch failed: {e}")
            return []


class DeepSeekAuditAnalyst:
    """AI audit analyst powered by DeepSeek, applying ISA 240/520 procedures."""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.model = model

    def analyze_anomalies(self, summary_json: str, thresholds: dict) -> dict:
        prompt = ANOMALY_DETECTION_PROMPT.format(
            summary_json=summary_json,
            single_txn_threshold=thresholds.get("single_txn_amount_usd", 50_000),
            daily_outflow_pct=thresholds.get("daily_outflow_pct_change", 0.5),
            dso_threshold=thresholds.get("collection_days_upper", 45),
            fee_rate_threshold=thresholds.get("fee_rate_upper", 0.20),
            refund_rate_threshold=thresholds.get("refund_rate_upper", 0.15),
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=2048,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior audit AI. Apply ISA 240 and ISA 520 analytical procedures. "
                            "Return valid JSON only. No markdown wrappers."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            logger.error(f"DeepSeek audit analysis failed: {e}")
            return {"error": str(e), "summary_narrative": f"AI 分析暂时不可用: {e}"}
