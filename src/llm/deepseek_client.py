"""
DeepSeek LLM client — OpenAI-compatible API wrapper.
Mirrors LLMClassifier / LLMAuditAnalyst interfaces so orchestrator
can swap providers without touching business logic.
"""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from openai import OpenAI

from .prompts import CLASSIFY_TRANSACTIONS_PROMPT, ANOMALY_DETECTION_PROMPT, RECONCILIATION_PROMPT

logger = logging.getLogger(__name__)

BATCH_SIZE = 20
MAX_WORKERS = 10  # concurrent API calls (rate-limit semaphore)
MAX_RETRIES = 3   # attempts before giving up on a batch


class DeepSeekClassifier:
    """Classifies ambiguous transactions using DeepSeek (deepseek-chat)."""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_hit_tokens = 0
        self.total_cache_miss_tokens = 0
        self._token_lock = threading.Lock()

    def classify_unclassified(self, df: pd.DataFrame) -> pd.DataFrame:
        mask = df["category"] == "Unclassified"
        unclassified = df[mask].copy()

        if unclassified.empty:
            logger.info("No unclassified transactions — skipping DeepSeek classification")
            return df

        logger.info(f"Classifying {len(unclassified)} transactions via DeepSeek...")

        batches = [
            unclassified.iloc[i : i + BATCH_SIZE].copy()
            for i in range(0, len(unclassified), BATCH_SIZE)
        ]

        all_results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(self._classify_batch, b) for b in batches]
            for future in as_completed(futures):
                all_results.extend(future.result())

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
        total = self.total_cache_hit_tokens + self.total_cache_miss_tokens
        hit_rate = self.total_cache_hit_tokens / total if total else 0
        logger.info(
            f"DeepSeek classified {classified}/{len(unclassified)} transactions. "
            f"Tokens: input={self.total_input_tokens}, output={self.total_output_tokens} | "
            f"Cache hit rate: {hit_rate:.1%}"
        )
        return df

    def _classify_batch(self, batch: pd.DataFrame) -> list[dict]:
        """Send one batch to DeepSeek and parse results. Retries up to MAX_RETRIES times."""
        txn_json = batch[["txn_id", "description", "amount_usd", "platform", "date"]].to_json(
            orient="records", indent=2
        )
        prompt = CLASSIFY_TRANSACTIONS_PROMPT.format(transactions_json=txn_json)

        last_error = None
        for attempt in range(MAX_RETRIES):
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

                usage = resp.usage
                with self._token_lock:
                    self.total_input_tokens += usage.prompt_tokens
                    self.total_output_tokens += usage.completion_tokens
                    if hasattr(usage, "prompt_cache_hit_tokens"):
                        self.total_cache_hit_tokens += usage.prompt_cache_hit_tokens
                    if hasattr(usage, "prompt_cache_miss_tokens"):
                        self.total_cache_miss_tokens += usage.prompt_cache_miss_tokens

                raw = resp.choices[0].message.content.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                return json.loads(raw)

            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(f"DeepSeek batch parse failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"DeepSeek API error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")

        logger.error(f"_classify_batch failed after {MAX_RETRIES} attempts: {last_error}")
        return []


class DeepSeekAuditAnalyst:
    """AI audit analyst powered by DeepSeek, applying ISA 240/520 procedures."""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.model = model

    def _call_and_parse(self, messages: list, max_tokens: int) -> str:
        """Shared helper: call API with retry, strip markdown, return raw JSON string."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=messages,
                )
                raw = resp.choices[0].message.content.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                json.loads(raw)  # validate before returning
                return raw
            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(f"Parse failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"API error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
        raise RuntimeError(f"All {MAX_RETRIES} attempts failed: {last_error}")

    def analyze_anomalies(self, summary_json: str, thresholds: dict) -> dict:
        prompt = ANOMALY_DETECTION_PROMPT.format(
            summary_json=summary_json,
            single_txn_threshold=thresholds.get("single_txn_amount_usd", 50_000),
            daily_outflow_pct=thresholds.get("daily_outflow_pct_change", 0.5),
            dso_threshold=thresholds.get("collection_days_upper", 45),
            fee_rate_threshold=thresholds.get("fee_rate_upper", 0.20),
            refund_rate_threshold=thresholds.get("refund_rate_upper", 0.15),
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior audit AI. Apply ISA 240 and ISA 520 analytical procedures. "
                    "Return valid JSON only. No markdown wrappers."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        try:
            return json.loads(self._call_and_parse(messages, max_tokens=2048))
        except RuntimeError as e:
            logger.error(f"analyze_anomalies failed: {e}")
            return {"error": str(e), "findings": [], "summary_narrative": "AI 分析暂时不可用"}

    def reconcile_settlements(self, schedule: dict) -> dict:
        reconciliation_data = json.dumps(schedule, indent=2, ensure_ascii=False, default=str)
        prompt = RECONCILIATION_PROMPT.format(reconciliation_data=reconciliation_data)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a forensic accountant performing fund flow reconciliation. "
                    "Return valid JSON only. No markdown wrappers."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        try:
            return json.loads(self._call_and_parse(messages, max_tokens=2048))
        except RuntimeError as e:
            logger.error(f"reconcile_settlements failed: {e}")
            return {"error": str(e), "reconciliation_status": "ERROR"}
