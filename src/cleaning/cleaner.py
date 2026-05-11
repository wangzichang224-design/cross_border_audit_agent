"""
Multi-source data cleaning pipeline.
Handles missing values, deduplication, currency normalization,
date parsing, and data quality scoring.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# Reference FX rates (mid-market, as of reporting period)
REFERENCE_FX = {
    "USD": 1.0000,
    "EUR": 1.0823,
    "GBP": 1.2741,
    "JPY": 0.0067,
    "BRL": 0.1954,
    "SGD": 0.7421,
}


class DataQualityReport:
    def __init__(self):
        self.issues: list[dict] = []
        self.stats: dict = {}

    def add_issue(self, severity: str, field: str, description: str, count: int = 1):
        self.issues.append({
            "severity": severity,
            "field": field,
            "description": description,
            "count": count,
        })

    def summary(self) -> str:
        critical = sum(1 for i in self.issues if i["severity"] == "CRITICAL")
        warnings = sum(1 for i in self.issues if i["severity"] == "WARNING")
        info = sum(1 for i in self.issues if i["severity"] == "INFO")
        lines = [
            f"Data Quality Report -- {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"  CRITICAL: {critical}  WARNING: {warnings}  INFO: {info}",
            "",
        ]
        for issue in self.issues:
            icon = {"CRITICAL": "[CRIT]", "WARNING": "[WARN]", "INFO": "[INFO]"}.get(issue["severity"], "-")
            lines.append(f"  {icon} [{issue['severity']}] {issue['field']}: {issue['description']} (n={issue['count']})")
        return "\n".join(lines)


class DataCleaner:
    """
    Cleans raw cross-border e-commerce transaction data.

    Pipeline:
    1. Schema validation & type casting
    2. Deduplication (exact + near-duplicate detection)
    3. Missing value imputation / flagging
    4. Currency normalization to USD
    5. Outlier detection (statistical)
    6. Data quality scoring
    """

    def __init__(self, fx_rates: dict = None):
        self.fx_rates = fx_rates or REFERENCE_FX
        self.quality_report = DataQualityReport()

    def clean(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, DataQualityReport]:
        df = df.copy()
        original_len = len(df)

        df = self._cast_types(df)
        df = self._deduplicate(df, original_len)
        df = self._handle_missing(df)
        df = self._normalize_currency(df)
        df = self._validate_amounts(df)
        df = self._add_derived_fields(df)
        df = self._score_data_quality(df)

        self.quality_report.stats = {
            "original_rows": original_len,
            "cleaned_rows": len(df),
            "removed_rows": original_len - len(df),
            "completeness_pct": round(df["dq_score"].mean() * 100, 1),
        }

        logger.info(f"Cleaning complete: {original_len} → {len(df)} rows")
        return df, self.quality_report

    def _cast_types(self, df: pd.DataFrame) -> pd.DataFrame:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["settlement_date"] = pd.to_datetime(df["settlement_date"], errors="coerce")

        bad_dates = df["date"].isna().sum()
        if bad_dates:
            self.quality_report.add_issue("CRITICAL", "date", f"{bad_dates} unparseable dates", bad_dates)

        df["amount_local"] = pd.to_numeric(df["amount_local"], errors="coerce")
        df["amount_usd"] = pd.to_numeric(df["amount_usd"], errors="coerce")
        df["currency"] = df["currency"].str.upper().str.strip()
        df["platform"] = df["platform"].str.strip()

        return df

    def _deduplicate(self, df: pd.DataFrame, original_len: int) -> pd.DataFrame:
        # Exact duplicate: same txn_id
        exact_dups = df.duplicated(subset=["txn_id"], keep="first").sum()
        if exact_dups:
            self.quality_report.add_issue(
                "CRITICAL", "txn_id",
                f"{exact_dups} exact duplicate transaction IDs removed", exact_dups
            )
        df = df.drop_duplicates(subset=["txn_id"], keep="first")

        # Near-duplicate: same date + platform + amount_usd (different txn_id)
        near_dup_mask = df.duplicated(
            subset=["date", "platform", "amount_usd", "category"], keep="first"
        )
        near_dups = near_dup_mask.sum()
        if near_dups:
            self.quality_report.add_issue(
                "WARNING", "amount_usd",
                f"{near_dups} near-duplicate entries (same date/platform/amount/category) flagged",
                near_dups
            )
            df.loc[near_dup_mask, "flag_near_duplicate"] = True
        else:
            df["flag_near_duplicate"] = False

        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        missing_amount = df["amount_local"].isna().sum()
        if missing_amount:
            self.quality_report.add_issue(
                "WARNING", "amount_local",
                f"{missing_amount} rows with missing amounts — imputed to 0 and flagged",
                missing_amount
            )
            df["flag_missing_amount"] = df["amount_local"].isna()
            df["amount_local"] = df["amount_local"].fillna(0)
            df["amount_usd"] = df["amount_usd"].fillna(0)
        else:
            df["flag_missing_amount"] = False

        missing_desc = df["description"].isna().sum()
        if missing_desc:
            df["description"] = df["description"].fillna("Unknown")
            self.quality_report.add_issue(
                "INFO", "description",
                f"{missing_desc} missing descriptions set to 'Unknown'", missing_desc
            )

        missing_counterparty = df["counterparty"].isna().sum()
        if missing_counterparty:
            df["counterparty"] = df["counterparty"].fillna("Unknown")

        return df

    def _normalize_currency(self, df: pd.DataFrame) -> pd.DataFrame:
        """Re-compute amount_usd from amount_local using reference FX rates.
        Flag rows where the implied FX rate deviates >5% from reference."""

        def implied_rate(row):
            if row["amount_local"] == 0 or row["currency"] == "USD":
                return None
            if row["amount_usd"] == 0:
                return None
            return row["amount_usd"] / row["amount_local"]

        df["implied_fx_rate"] = df.apply(implied_rate, axis=1)
        df["reference_fx_rate"] = df["currency"].map(self.fx_rates).fillna(1.0)

        # Flag FX deviations
        non_usd = df["currency"] != "USD"
        non_zero = df["implied_fx_rate"].notna()
        mask = non_usd & non_zero
        if mask.any():
            deviation = (
                (df.loc[mask, "implied_fx_rate"] - df.loc[mask, "reference_fx_rate"]).abs()
                / df.loc[mask, "reference_fx_rate"]
            )
            fx_anomalies = (deviation > 0.05).sum()
            df["flag_fx_deviation"] = False
            df.loc[mask & (deviation > 0.05), "flag_fx_deviation"] = True

            if fx_anomalies:
                self.quality_report.add_issue(
                    "CRITICAL", "fx_rate",
                    f"{fx_anomalies} transactions with FX rate deviation >5% from reference",
                    fx_anomalies
                )
        else:
            df["flag_fx_deviation"] = False

        # Re-normalize amount_usd using reference FX
        df["amount_usd_normalized"] = df["amount_local"] * df["reference_fx_rate"]

        return df

    def _validate_amounts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Statistical outlier detection using IQR per category."""
        df["flag_outlier_amount"] = False

        for cat in df["category"].unique():
            mask = (df["category"] == cat) & (df["amount_usd"].abs() > 0)
            if mask.sum() < 4:
                continue
            amounts = df.loc[mask, "amount_usd"].abs()
            q1, q3 = amounts.quantile(0.25), amounts.quantile(0.75)
            iqr = q3 - q1
            upper = q3 + 3 * iqr
            outliers = mask & (df["amount_usd"].abs() > upper)
            df.loc[outliers, "flag_outlier_amount"] = True

        n_outliers = df["flag_outlier_amount"].sum()
        if n_outliers:
            self.quality_report.add_issue(
                "WARNING", "amount_usd",
                f"{n_outliers} statistical outliers detected (IQR method, 3×)", n_outliers
            )

        return df

    def _add_derived_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        df["settlement_lag_days"] = (df["settlement_date"] - df["date"]).dt.days
        df["week"] = df["date"].dt.isocalendar().week.astype(int)
        df["month"] = df["date"].dt.to_period("M").astype(str)
        df["is_outflow"] = df["amount_usd"] < 0
        df["abs_amount_usd"] = df["amount_usd"].abs()
        return df

    def _score_data_quality(self, df: pd.DataFrame) -> pd.DataFrame:
        """Assign a completeness score [0,1] per row."""
        required_fields = ["txn_id", "date", "platform", "currency", "amount_local", "category", "description"]
        present = df[required_fields].notna().astype(int)
        df["dq_score"] = present.mean(axis=1)
        return df
