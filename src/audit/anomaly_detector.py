"""
Rule-based anomaly detection engine.
Runs deterministic checks before calling the LLM layer,
so the LLM receives a pre-filtered summary rather than raw rows.
This reduces token usage and keeps the LLM focused on interpretation.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import logging

from config import ANOMALY_THRESHOLDS

logger = logging.getLogger(__name__)


@dataclass
class AnomalyFinding:
    finding_id: str
    rule_name: str
    risk_level: str          # CRITICAL / HIGH / MEDIUM / LOW
    category: str
    description: str
    affected_txn_ids: list[str] = field(default_factory=list)
    amount_impact_usd: float = 0.0
    date_range: Optional[str] = None
    platform: Optional[str] = None


class RuleBasedAnomalyDetector:
    """
    Implements deterministic audit rules modeled after:
    - ISA 520: Analytical Procedures
    - ISA 240: Fraud Risk Assessment
    - Internal controls for e-commerce fund flows
    """

    def __init__(self, thresholds: dict = None):
        self.thresholds = thresholds or ANOMALY_THRESHOLDS
        self.findings: list[AnomalyFinding] = []
        self._finding_counter = 0

    def _next_id(self) -> str:
        self._finding_counter += 1
        return f"R{self._finding_counter:03d}"

    def run_all_checks(self, df: pd.DataFrame) -> list[AnomalyFinding]:
        """Run the full audit ruleset and return all findings."""
        self.findings = []

        self._check_large_single_transactions(df)
        self._check_daily_outflow_spikes(df)
        self._check_days_sales_outstanding(df)
        self._check_fee_rates(df)
        self._check_refund_rates(df)
        self._check_platform_concentration(df)
        self._check_fx_deviations(df)
        self._check_settlement_delays(df)
        self._check_weekend_large_payments(df)
        self._check_round_number_transactions(df)

        n_critical = sum(1 for f in self.findings if f.risk_level == "CRITICAL")
        n_high = sum(1 for f in self.findings if f.risk_level == "HIGH")
        logger.info(f"Rule-based checks: {len(self.findings)} findings ({n_critical} CRITICAL, {n_high} HIGH)")
        return self.findings

    def _check_large_single_transactions(self, df: pd.DataFrame):
        threshold = self.thresholds["single_txn_amount_usd"]
        large = df[df["amount_usd"].abs() > threshold]
        if large.empty:
            return

        for _, row in large.iterrows():
            direction = "inflow" if row["amount_usd"] > 0 else "outflow"
            self.findings.append(AnomalyFinding(
                finding_id=self._next_id(),
                rule_name="LARGE_SINGLE_TXN",
                risk_level="HIGH" if abs(row["amount_usd"]) < threshold * 3 else "CRITICAL",
                category=row.get("category", "Unknown"),
                description=(
                    f"Single {direction} of USD {abs(row['amount_usd']):,.0f} "
                    f"on {row['date'].strftime('%Y-%m-%d') if pd.notna(row['date']) else 'N/A'} "
                    f"via {row['platform']} — exceeds materiality threshold of USD {threshold:,.0f}"
                ),
                affected_txn_ids=[row["txn_id"]],
                amount_impact_usd=float(abs(row["amount_usd"])),
                platform=row["platform"],
            ))

    def _check_daily_outflow_spikes(self, df: pd.DataFrame):
        threshold = self.thresholds["daily_outflow_pct_change"]
        daily_out = (
            df[df["is_outflow"]]
            .groupby("date")["abs_amount_usd"]
            .sum()
            .sort_index()
        )
        if len(daily_out) < 2:
            return

        pct_change = daily_out.pct_change().abs()
        spikes = pct_change[pct_change > threshold]

        for date, pct in spikes.items():
            self.findings.append(AnomalyFinding(
                finding_id=self._next_id(),
                rule_name="OUTFLOW_SPIKE",
                risk_level="HIGH" if pct < 1.0 else "CRITICAL",
                category="Cash Flow",
                description=(
                    f"Daily outflow on {date.strftime('%Y-%m-%d')} spiked "
                    f"{pct:.1%} vs prior day — "
                    f"USD {daily_out.get(date, 0):,.0f} outflow"
                ),
                amount_impact_usd=float(daily_out.get(date, 0)),
                date_range=str(date.date()),
            ))

    def _check_days_sales_outstanding(self, df: pd.DataFrame):
        threshold = self.thresholds["collection_days_upper"]
        revenue = df[df["category"] == "Product Revenue"].copy()
        if revenue.empty:
            return

        avg_lag = revenue["settlement_lag_days"].mean()
        max_lag = revenue["settlement_lag_days"].max()
        delayed = revenue[revenue["settlement_lag_days"] > threshold]

        if not delayed.empty:
            self.findings.append(AnomalyFinding(
                finding_id=self._next_id(),
                rule_name="HIGH_DSO",
                risk_level="MEDIUM",
                category="Collections",
                description=(
                    f"{len(delayed)} revenue transactions with settlement lag > {threshold} days. "
                    f"Avg lag: {avg_lag:.1f} days, Max: {max_lag:.0f} days. "
                    f"Possible payment hold or dispute."
                ),
                affected_txn_ids=delayed["txn_id"].tolist()[:10],
                amount_impact_usd=float(delayed["amount_usd"].sum()),
            ))

    def _check_fee_rates(self, df: pd.DataFrame):
        threshold = self.thresholds["fee_rate_upper"]
        fee_categories = [
            "Amazon FBA Fee", "Platform Commission", "Advertising Spend",
            "Payment Processing Fee", "Logistics & Freight",
        ]

        revenue_by_platform = (
            df[df["category"] == "Product Revenue"]
            .groupby("platform")["amount_usd"]
            .sum()
        )

        for platform in df["platform"].unique():
            rev = revenue_by_platform.get(platform, 0)
            if rev <= 0:
                continue

            platform_fees = df[
                (df["platform"] == platform) & (df["category"].isin(fee_categories))
            ]
            for cat in fee_categories:
                cat_fees = platform_fees[platform_fees["category"] == cat]["amount_usd"].abs().sum()
                rate = cat_fees / rev
                if rate > threshold:
                    self.findings.append(AnomalyFinding(
                        finding_id=self._next_id(),
                        rule_name="HIGH_FEE_RATE",
                        risk_level="HIGH",
                        category=cat,
                        description=(
                            f"{platform} — {cat} rate = {rate:.1%} of revenue "
                            f"(threshold: {threshold:.0%}). "
                            f"Total fees: USD {cat_fees:,.0f}"
                        ),
                        amount_impact_usd=float(cat_fees),
                        platform=platform,
                    ))

    def _check_refund_rates(self, df: pd.DataFrame):
        threshold = self.thresholds["refund_rate_upper"]
        refunds = df[df["category"] == "Refund & Chargeback"]["amount_usd"].abs().sum()
        revenue = df[df["category"] == "Product Revenue"]["amount_usd"].sum()

        if revenue <= 0:
            return

        refund_rate = refunds / revenue
        if refund_rate > threshold:
            self.findings.append(AnomalyFinding(
                finding_id=self._next_id(),
                rule_name="HIGH_REFUND_RATE",
                risk_level="CRITICAL" if refund_rate > 0.20 else "HIGH",
                category="Refund & Chargeback",
                description=(
                    f"Aggregate refund/chargeback rate = {refund_rate:.1%} "
                    f"(threshold: {threshold:.0%}). "
                    f"Total refunds: USD {refunds:,.0f}. "
                    f"Investigate for product quality issues or potential fraud."
                ),
                amount_impact_usd=float(refunds),
            ))

    def _check_platform_concentration(self, df: pd.DataFrame):
        threshold = self.thresholds["concentration_risk_pct"]
        revenue = df[df["category"] == "Product Revenue"]
        total_rev = revenue["amount_usd"].sum()

        if total_rev <= 0:
            return

        by_platform = revenue.groupby("platform")["amount_usd"].sum()
        concentration = by_platform / total_rev

        for platform, pct in concentration.items():
            if pct > threshold:
                self.findings.append(AnomalyFinding(
                    finding_id=self._next_id(),
                    rule_name="CONCENTRATION_RISK",
                    risk_level="MEDIUM",
                    category="Business Risk",
                    description=(
                        f"{platform} accounts for {pct:.1%} of total revenue "
                        f"(threshold: {threshold:.0%}). "
                        f"High dependency — platform policy changes could be material."
                    ),
                    amount_impact_usd=float(by_platform[platform]),
                    platform=platform,
                ))

    def _check_fx_deviations(self, df: pd.DataFrame):
        if "flag_fx_deviation" not in df.columns:
            return

        flagged = df[df["flag_fx_deviation"] == True]
        if flagged.empty:
            return

        total_impact = flagged["abs_amount_usd"].sum()
        self.findings.append(AnomalyFinding(
            finding_id=self._next_id(),
            rule_name="FX_DEVIATION",
            risk_level="CRITICAL",
            category="FX / Treasury",
            description=(
                f"{len(flagged)} transactions with FX rate >5% from reference mid-rate. "
                f"Total exposure: USD {total_impact:,.0f}. "
                f"May indicate unauthorized FX conversion or rate manipulation."
            ),
            affected_txn_ids=flagged["txn_id"].tolist()[:20],
            amount_impact_usd=float(total_impact),
        ))

    def _check_settlement_delays(self, df: pd.DataFrame):
        """Flag platforms with unusual settlement delays (> 14 days for non-Amazon)."""
        non_amazon = df[
            (df["category"] == "Product Revenue") &
            (~df["platform"].str.contains("Amazon", na=False))
        ]
        delayed = non_amazon[non_amazon["settlement_lag_days"] > 14]
        if not delayed.empty:
            self.findings.append(AnomalyFinding(
                finding_id=self._next_id(),
                rule_name="SETTLEMENT_DELAY",
                risk_level="MEDIUM",
                category="Collections",
                description=(
                    f"{len(delayed)} non-Amazon settlements delayed >14 days. "
                    f"Affected platforms: {delayed['platform'].unique().tolist()}. "
                    f"Verify platform payment holds."
                ),
                affected_txn_ids=delayed["txn_id"].tolist()[:10],
                amount_impact_usd=float(delayed["amount_usd"].sum()),
            ))

    def _check_weekend_large_payments(self, df: pd.DataFrame):
        """Large outflows on weekends can indicate unauthorized payments (ISA 240 red flag)."""
        weekend_mask = df["date"].dt.weekday >= 5
        large_weekend = df[weekend_mask & (df["amount_usd"] < -10_000)]
        if not large_weekend.empty:
            self.findings.append(AnomalyFinding(
                finding_id=self._next_id(),
                rule_name="WEEKEND_LARGE_PAYMENT",
                risk_level="HIGH",
                category="Fraud Indicator",
                description=(
                    f"{len(large_weekend)} outflows > USD 10,000 on weekends. "
                    f"Total: USD {large_weekend['amount_usd'].abs().sum():,.0f}. "
                    f"Weekend large payments are a known fraud indicator (ISA 240)."
                ),
                affected_txn_ids=large_weekend["txn_id"].tolist()[:10],
                amount_impact_usd=float(large_weekend["amount_usd"].abs().sum()),
            ))

    def _check_round_number_transactions(self, df: pd.DataFrame):
        """Round-number transactions (e.g., exactly $10,000) can indicate structuring."""
        round_mask = (df["amount_usd"].abs() % 1000 == 0) & (df["amount_usd"].abs() >= 5000)
        round_txns = df[round_mask & df["is_outflow"]]
        if len(round_txns) > 10:  # Only flag if there's a pattern
            self.findings.append(AnomalyFinding(
                finding_id=self._next_id(),
                rule_name="ROUND_NUMBER_PATTERN",
                risk_level="LOW",
                category="Fraud Indicator",
                description=(
                    f"{len(round_txns)} outflows with exact round-number amounts (multiples of $1,000). "
                    f"Potential structuring pattern — review individually."
                ),
                affected_txn_ids=round_txns["txn_id"].tolist()[:10],
                amount_impact_usd=float(round_txns["amount_usd"].abs().sum()),
            ))

    def to_summary_dict(self, df: pd.DataFrame) -> dict:
        """Build the summary dict passed to the LLM audit analyst."""
        revenue = df[df["category"] == "Product Revenue"]["amount_usd"].sum()
        total_outflows = df[df["is_outflow"]]["abs_amount_usd"].sum()

        by_category = (
            df.groupby("category")["amount_usd"]
            .sum()
            .round(2)
            .to_dict()
        )
        by_platform_rev = (
            df[df["category"] == "Product Revenue"]
            .groupby("platform")["amount_usd"]
            .sum()
            .round(2)
            .to_dict()
        )

        daily_net = (
            df.groupby(df["date"].dt.strftime("%Y-%m-%d"))["amount_usd"]
            .sum()
            .round(2)
            .to_dict()
        )

        rule_findings = [
            {
                "id": f.finding_id,
                "rule": f.rule_name,
                "risk": f.risk_level,
                "description": f.description,
                "amount_usd": f.amount_impact_usd,
            }
            for f in self.findings
        ]

        return {
            "period": {
                "start": str(df["date"].min().date()),
                "end": str(df["date"].max().date()),
                "total_days": df["date"].nunique(),
            },
            "financials": {
                "total_revenue_usd": round(revenue, 2),
                "total_outflows_usd": round(total_outflows, 2),
                "net_cash_flow_usd": round(revenue - total_outflows, 2),
                "avg_daily_revenue_usd": round(revenue / max(df["date"].nunique(), 1), 2),
            },
            "by_category": by_category,
            "by_platform_revenue": by_platform_rev,
            "daily_net_cashflow_sample": dict(list(daily_net.items())[-14:]),  # Last 14 days
            "rule_based_findings": rule_findings,
            "data_quality": {
                "total_transactions": len(df),
                "missing_amount_count": int(df.get("flag_missing_amount", pd.Series([False] * len(df))).sum()),
                "fx_deviation_count": int(df.get("flag_fx_deviation", pd.Series([False] * len(df))).sum()),
                "near_duplicate_count": int(df.get("flag_near_duplicate", pd.Series([False] * len(df))).sum()),
            },
        }
