"""
Report generation module.
Combines structured data + AI narrative into a Markdown report.
"""

import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)

REPORT_TEMPLATE = """# 跨境电商资金流审计报告
**审计主体:** 星辰跨境科技（深圳）有限公司 / StarCross Technology (Shenzhen) Co., Ltd.
**报告周期:** {period_start} — {period_end}
**生成时间:** {generated_at}
**报告类型:** AI 自动化审计分析 | 模型: DeepSeek deepseek-chat
**合规框架:** ISA 240（舞弊风险）· ISA 520（分析程序）

---

{ai_narrative}

---

## 数据质量监控 (Data Quality Dashboard)

| 指标 | 数值 |
|------|------|
| 总交易笔数 | {total_txns:,} |
| 数据完整性得分 | {dq_score:.1f}% |
| 清洗移除行数 | {removed_rows:,} |
| FX 汇率异常笔数 | {fx_anomaly_count:,} |
| 缺失金额笔数 | {missing_amount_count:,} |
| 近似重复笔数 | {near_dup_count:,} |
| AI 分类笔数 (原 Unclassified) | {llm_classified_count:,} |

---

## 审计发现清单 (Audit Findings)

{findings_table}

---

## 关键财务指标 (KPIs)

| 指标 | 数值 |
|------|------|
| 总收入 (USD) | ${total_revenue:,.0f} |
| 总支出 (USD) | ${total_outflows:,.0f} |
| 净现金流 (USD) | ${net_cashflow:,.0f} |
| 日均收入 (USD) | ${avg_daily_revenue:,.0f} |
| 净利润率 | {net_margin:.1f}% |

### 平台收入分布

{platform_table}

### 成本结构

{cost_table}

---

## 图表附件
{chart_list}

---

*本报告由 AI Audit Agent 自动生成，仅供参考。所有 CRITICAL/HIGH 级别发现需人工复核。*
*合规声明: 本系统遵循 ISA 240 (舞弊风险) 及 ISA 520 (分析程序) 审计准则。*
"""


class ReportGenerator:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        df: pd.DataFrame,
        findings: list,
        chart_paths: dict,
        ai_narrative: str,
        quality_stats: dict,
    ) -> str:
        """Assemble the full Markdown report and write to disk."""

        revenue = df[df["category"] == "Product Revenue"]["amount_usd"].sum()
        outflows = df[df["is_outflow"]]["abs_amount_usd"].sum()
        net = revenue - outflows
        net_margin = (net / revenue * 100) if revenue > 0 else 0

        # Platform revenue table
        platform_rev = (
            df[df["category"] == "Product Revenue"]
            .groupby("platform")["amount_usd"]
            .sum()
            .sort_values(ascending=False)
        )
        total_rev = platform_rev.sum()
        platform_rows = "\n".join(
            f"| {p} | ${v:,.0f} | {v/total_rev:.1%} |"
            for p, v in platform_rev.items()
        )
        platform_table = (
            "| 平台 | 收入 (USD) | 占比 |\n"
            "|------|-----------|------|\n"
            + platform_rows
        )

        # Cost structure table
        cost_cats = [
            "Amazon FBA Fee", "Platform Commission", "Advertising Spend",
            "Logistics & Freight", "Customs & Duties", "Payment Processing Fee",
            "VAT / Tax Remittance", "Refund & Chargeback",
        ]
        cost_data = (
            df[df["category"].isin(cost_cats)]
            .groupby("category")["amount_usd"]
            .sum()
            .abs()
            .sort_values(ascending=False)
        )
        cost_rows = "\n".join(
            f"| {c} | ${v:,.0f} | {v/revenue:.1%} |"
            for c, v in cost_data.items()
        )
        cost_table = (
            "| 费用类别 | 金额 (USD) | 占收入比 |\n"
            "|---------|-----------|----------|\n"
            + cost_rows
        )

        # Findings table
        findings_rows = []
        for f in sorted(findings, key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(x.risk_level, 4)):
            risk_icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(f.risk_level, "⚪")
            findings_rows.append(
                f"| {f.finding_id} | {risk_icon} {f.risk_level} | {f.rule_name} | "
                f"${f.amount_impact_usd:,.0f} | {f.description[:80]}... |"
            )

        if findings_rows:
            findings_table = (
                "| ID | 风险级别 | 规则 | 金额影响 (USD) | 描述 |\n"
                "|----|---------|------|---------------|------|\n"
                + "\n".join(findings_rows)
            )
        else:
            findings_table = "_未发现异常_"

        # Chart list
        chart_list = "\n".join(
            f"- [{name}]({path})"
            for name, path in sorted(chart_paths.items())
        )

        # LLM classified count
        llm_cols = [c for c in df.columns if c == "llm_confidence"]
        llm_classified = len(df[df["llm_confidence"].notna()]) if llm_cols else 0

        report = REPORT_TEMPLATE.format(
            period_start=str(df["date"].min().date()),
            period_end=str(df["date"].max().date()),
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ai_narrative=ai_narrative,
            total_txns=len(df),
            dq_score=quality_stats.get("completeness_pct", 0),
            removed_rows=quality_stats.get("removed_rows", 0),
            fx_anomaly_count=int(df.get("flag_fx_deviation", pd.Series(dtype=bool)).sum()),
            missing_amount_count=int(df.get("flag_missing_amount", pd.Series(dtype=bool)).sum()),
            near_dup_count=int(df.get("flag_near_duplicate", pd.Series(dtype=bool)).sum()),
            llm_classified_count=llm_classified,
            findings_table=findings_table,
            total_revenue=revenue,
            total_outflows=outflows,
            net_cashflow=net,
            avg_daily_revenue=revenue / max(df["date"].nunique(), 1),
            net_margin=net_margin,
            platform_table=platform_table,
            cost_table=cost_table,
            chart_list=chart_list,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"audit_report_{timestamp}.md"
        report_path.write_text(report, encoding="utf-8")
        logger.info(f"Report saved: {report_path}")
        return str(report_path)
