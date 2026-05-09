"""
LLM-powered transaction classifier and audit analyst.
Uses Claude with prompt caching for efficiency on large datasets.
"""

import json
import logging
from typing import Optional
import anthropic
import pandas as pd

from .prompts import (
    CLASSIFY_TRANSACTIONS_PROMPT,
    ANOMALY_DETECTION_PROMPT,
    REPORT_GENERATION_PROMPT,
    RECONCILIATION_PROMPT,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 20  # transactions per LLM call


class LLMClassifier:
    """
    Classifies ambiguous transaction descriptions using Claude.
    Processes in batches with prompt caching to reduce API cost ~80%.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_read_tokens = 0

    def classify_unclassified(self, df: pd.DataFrame) -> pd.DataFrame:
        """Find 'Unclassified' rows and use Claude to assign categories."""
        mask = df["category"] == "Unclassified"
        unclassified = df[mask].copy()

        if len(unclassified) == 0:
            logger.info("No unclassified transactions — skipping LLM classification")
            return df

        logger.info(f"Classifying {len(unclassified)} unclassified transactions via LLM...")

        # Process in batches
        all_results = []
        for start in range(0, len(unclassified), BATCH_SIZE):
            batch = unclassified.iloc[start : start + BATCH_SIZE]
            batch_results = self._classify_batch(batch)
            all_results.extend(batch_results)

        # Apply results back to main dataframe
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

        classified_count = (df.loc[mask, "category"] != "Unclassified").sum()
        logger.info(
            f"LLM classified {classified_count}/{len(unclassified)} transactions. "
            f"Tokens used: input={self.total_input_tokens}, "
            f"cache_read={self.total_cache_read_tokens}, output={self.total_output_tokens}"
        )
        return df

    def _classify_batch(self, batch: pd.DataFrame) -> list[dict]:
        """Send one batch to Claude and parse results."""
        transactions_json = batch[["txn_id", "description", "amount_usd", "platform", "date"]].to_json(
            orient="records", indent=2
        )

        prompt_text = CLASSIFY_TRANSACTIONS_PROMPT.format(transactions_json=transactions_json)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=[
                    {
                        "type": "text",
                        "text": (
                            "You are a forensic accountant AI assistant. "
                            "Always return valid JSON exactly as specified. No markdown code blocks."
                        ),
                        # Cache the system prompt — it never changes across batches
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": prompt_text}],
            )

            # Track token usage
            usage = response.usage
            self.total_input_tokens += usage.input_tokens
            self.total_output_tokens += usage.output_tokens
            if hasattr(usage, "cache_read_input_tokens"):
                self.total_cache_read_tokens += usage.cache_read_input_tokens

            raw = response.content[0].text.strip()
            # Strip markdown code fences if model wrapped them
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)

        except (json.JSONDecodeError, anthropic.APIError) as e:
            logger.error(f"LLM batch classification failed: {e}")
            return []


class LLMAuditAnalyst:
    """
    Performs AI-powered audit analysis using Claude.
    Generates structured findings grounded in ISA standards.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def analyze_anomalies(
        self,
        summary_json: str,
        thresholds: dict,
    ) -> dict:
        """Run anomaly detection audit and return structured findings."""

        prompt = ANOMALY_DETECTION_PROMPT.format(
            summary_json=summary_json,
            single_txn_threshold=thresholds.get("single_txn_amount_usd", 50000),
            daily_outflow_pct=thresholds.get("daily_outflow_pct_change", 0.5),
            dso_threshold=thresholds.get("collection_days_upper", 45),
            fee_rate_threshold=thresholds.get("fee_rate_upper", 0.20),
            refund_rate_threshold=thresholds.get("refund_rate_upper", 0.15),
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": (
                        "You are a senior audit AI. Apply ISA 240 and ISA 520 analytical procedures. "
                        "Return valid JSON only. No markdown wrappers."
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse anomaly analysis response:\n{raw[:500]}")
            return {"error": "Parse failure", "raw": raw[:200]}

    def reconcile_settlements(self, schedule: dict) -> dict:
        """Compare expected vs actual settlements and flag discrepancies."""
        import json as _json
        reconciliation_data = _json.dumps(schedule, indent=2, ensure_ascii=False, default=str)
        prompt = RECONCILIATION_PROMPT.format(reconciliation_data=reconciliation_data)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=[{
                    "type": "text",
                    "text": (
                        "You are a forensic accountant performing fund flow reconciliation. "
                        "Return valid JSON only. No markdown wrappers."
                    ),
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return _json.loads(raw)
        except Exception as e:
            logger.error(f"Reconciliation analysis failed: {e}")
            return {"error": str(e), "reconciliation_status": "ERROR"}

    def generate_report(self, report_data: dict) -> str:
        """Generate a Markdown executive report using Claude."""

        report_data_json = json.dumps(report_data, indent=2, ensure_ascii=False, default=str)

        prompt = REPORT_GENERATION_PROMPT.format(report_data_json=report_data_json)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text
