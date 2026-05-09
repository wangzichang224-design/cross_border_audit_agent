"""
Visualization module — generates all charts for the weekly report.
Outputs PNG files to the reports/ directory.
"""

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server/CI use

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Style
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
})

COLORS = {
    "positive": "#2196F3",
    "negative": "#F44336",
    "neutral": "#9E9E9E",
    "warning": "#FF9800",
    "critical": "#D32F2F",
    "platform_palette": ["#1976D2", "#388E3C", "#F57C00", "#7B1FA2", "#0097A7"],
}


class ReportVisualizer:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chart_paths: dict[str, str] = {}

    def generate_all(self, df: pd.DataFrame, findings: list) -> dict[str, str]:
        """Generate all report charts. Returns dict of chart_name → file_path."""
        self._chart_daily_cashflow(df)
        self._chart_platform_revenue_breakdown(df)
        self._chart_cost_structure(df)
        self._chart_settlement_lag_distribution(df)
        self._chart_anomaly_heatmap(df)
        self._chart_risk_summary(findings)
        return self.chart_paths

    def _save(self, fig, name: str):
        path = self.output_dir / f"{name}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        self.chart_paths[name] = str(path)
        logger.debug(f"Saved chart: {path}")

    def _chart_daily_cashflow(self, df: pd.DataFrame):
        daily = (
            df.groupby("date")["amount_usd"]
            .sum()
            .reset_index()
            .sort_values("date")
        )
        daily["rolling_7d"] = daily["amount_usd"].rolling(7, min_periods=1).mean()

        fig, ax = plt.subplots(figsize=(12, 4))
        colors = [COLORS["positive"] if v >= 0 else COLORS["negative"] for v in daily["amount_usd"]]
        ax.bar(daily["date"], daily["amount_usd"], color=colors, alpha=0.6, width=0.8, label="Daily Net")
        ax.plot(daily["date"], daily["rolling_7d"], color="#212121", linewidth=1.8,
                label="7-Day Rolling Avg", zorder=5)
        ax.axhline(0, color="#757575", linewidth=0.8, linestyle="--")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
        plt.xticks(rotation=30)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
        ax.set_title("Daily Net Cash Flow (USD)")
        ax.legend(loc="upper left", fontsize=9)
        ax.set_ylabel("Net Cash Flow (USD)")
        self._save(fig, "01_daily_cashflow")

    def _chart_platform_revenue_breakdown(self, df: pd.DataFrame):
        rev = (
            df[df["category"] == "Product Revenue"]
            .groupby(["month", "platform"])["amount_usd"]
            .sum()
            .reset_index()
        )
        pivot = rev.pivot(index="month", columns="platform", values="amount_usd").fillna(0)

        fig, axes = plt.subplots(1, 2, figsize=(13, 5))

        # Stacked bar by month
        pivot.plot(
            kind="bar", stacked=True, ax=axes[0],
            color=COLORS["platform_palette"][:len(pivot.columns)],
            alpha=0.85,
        )
        axes[0].set_title("Revenue by Platform & Month")
        axes[0].set_ylabel("Revenue (USD)")
        axes[0].yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
        axes[0].tick_params(axis="x", rotation=30)
        axes[0].legend(fontsize=8, loc="upper left")

        # Pie chart — total share
        total_by_platform = (
            df[df["category"] == "Product Revenue"]
            .groupby("platform")["amount_usd"]
            .sum()
        )
        wedge_props = {"linewidth": 1, "edgecolor": "white"}
        axes[1].pie(
            total_by_platform,
            labels=total_by_platform.index,
            autopct="%1.1f%%",
            colors=COLORS["platform_palette"][:len(total_by_platform)],
            wedgeprops=wedge_props,
            startangle=140,
        )
        axes[1].set_title("Platform Revenue Share (Full Period)")

        plt.tight_layout()
        self._save(fig, "02_platform_revenue")

    def _chart_cost_structure(self, df: pd.DataFrame):
        cost_cats = [
            "Amazon FBA Fee", "Platform Commission", "Advertising Spend",
            "Logistics & Freight", "Customs & Duties", "Payment Processing Fee",
            "VAT / Tax Remittance", "Refund & Chargeback",
        ]
        costs = (
            df[df["category"].isin(cost_cats)]
            .groupby("category")["amount_usd"]
            .sum()
            .abs()
            .sort_values(ascending=True)
        )
        total_revenue = df[df["category"] == "Product Revenue"]["amount_usd"].sum()
        cost_pct = (costs / total_revenue * 100).round(1)

        fig, ax = plt.subplots(figsize=(9, 5))
        bars = ax.barh(costs.index, costs.values,
                       color=COLORS["negative"], alpha=0.75)
        # Annotate with % of revenue
        for bar, (cat, pct) in zip(bars, cost_pct.items()):
            ax.text(
                bar.get_width() + costs.max() * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{pct:.1f}% of rev",
                va="center", fontsize=8.5, color="#555",
            )
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
        ax.set_title("Cost Structure by Category (Full Period)")
        ax.set_xlabel("Total Amount (USD)")
        plt.tight_layout()
        self._save(fig, "03_cost_structure")

    def _chart_settlement_lag_distribution(self, df: pd.DataFrame):
        revenue = df[df["category"] == "Product Revenue"].copy()
        if revenue.empty:
            return

        fig, ax = plt.subplots(figsize=(9, 4))
        for i, platform in enumerate(revenue["platform"].unique()):
            lags = revenue[revenue["platform"] == platform]["settlement_lag_days"].dropna()
            if len(lags) > 1:
                ax.hist(lags, bins=15, alpha=0.55,
                        label=platform,
                        color=COLORS["platform_palette"][i % len(COLORS["platform_palette"])])

        ax.axvline(x=45, color=COLORS["critical"], linewidth=1.5,
                   linestyle="--", label="DSO Alert (45d)")
        ax.set_xlabel("Settlement Lag (days)")
        ax.set_ylabel("Transaction Count")
        ax.set_title("Settlement Lag Distribution by Platform")
        ax.legend(fontsize=8)
        plt.tight_layout()
        self._save(fig, "04_settlement_lag")

    def _chart_anomaly_heatmap(self, df: pd.DataFrame):
        """Weekly anomaly intensity heatmap across platforms."""
        flag_cols = [c for c in df.columns if c.startswith("flag_")]
        if not flag_cols:
            return

        df_copy = df.copy()
        df_copy["anomaly_score"] = df_copy[flag_cols].fillna(False).astype(int).sum(axis=1)
        pivot = (
            df_copy.groupby(["week", "platform"])["anomaly_score"]
            .sum()
            .unstack(fill_value=0)
        )

        if pivot.empty:
            return

        fig, ax = plt.subplots(figsize=(11, 4))
        sns.heatmap(
            pivot.T, ax=ax, cmap="YlOrRd",
            linewidths=0.3, annot=True, fmt="d",
            annot_kws={"size": 7},
            cbar_kws={"label": "Anomaly Flags"},
        )
        ax.set_title("Weekly Anomaly Flag Heatmap (by Platform)")
        ax.set_xlabel("ISO Week")
        ax.set_ylabel("Platform")
        plt.tight_layout()
        self._save(fig, "05_anomaly_heatmap")

    def _chart_risk_summary(self, findings: list):
        """Bar chart of risk findings by level."""
        if not findings:
            return

        from collections import Counter
        counts = Counter(getattr(f, "risk_level", "UNKNOWN") for f in findings)
        order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        labels = [r for r in order if r in counts]
        values = [counts[r] for r in labels]
        colors_map = {
            "CRITICAL": COLORS["critical"],
            "HIGH": COLORS["warning"],
            "MEDIUM": "#FDD835",
            "LOW": "#66BB6A",
        }
        bar_colors = [colors_map.get(r, "#9E9E9E") for r in labels]

        fig, ax = plt.subplots(figsize=(6, 3.5))
        bars = ax.bar(labels, values, color=bar_colors, alpha=0.85, width=0.5)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                    str(val), ha="center", fontsize=11, fontweight="bold")
        ax.set_title("Audit Findings by Risk Level")
        ax.set_ylabel("Number of Findings")
        ax.set_ylim(0, max(values) * 1.3)
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout()
        self._save(fig, "06_risk_summary")
