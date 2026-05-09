"""
Streamlit frontend for the Cross-border E-commerce AI Audit Agent.

Run:
    streamlit run streamlit_app.py
"""

import sys
import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# ── UTF-8 safety (Windows) ──────────────────────────────────────────────────
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    ANOMALY_THRESHOLDS,
    DEEPSEEK_API_KEY as _CFG_DEEPSEEK_KEY,
    RAW_DATA_DIR,
    REPORTS_DIR,
)
from src.data_ingestion import generate_transactions, save_raw_data
from src.cleaning import DataCleaner
from src.audit import RuleBasedAnomalyDetector
from src.reporting import ReportGenerator, ReportVisualizer
from src.llm.deepseek_client import DeepSeekClassifier, DeepSeekAuditAnalyst

logging.basicConfig(level=logging.INFO)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="跨境电商 AI 审计系统",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Resolve API key: Streamlit Cloud secrets > environment variable > empty
try:
    DEEPSEEK_API_KEY = st.secrets.get("DEEPSEEK_API_KEY", _CFG_DEEPSEEK_KEY)
except Exception:
    DEEPSEEK_API_KEY = _CFG_DEEPSEEK_KEY

st.markdown("""
<style>
/* KPI cards */
[data-testid="metric-container"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px 16px;
}
/* Finding cards */
.finding-card {
    padding: 10px 14px;
    margin: 6px 0;
    border-radius: 6px;
    font-size: 0.92rem;
    line-height: 1.5;
}
/* Stage badge */
.stage-ok  { color: #16a34a; font-weight: 600; }
.stage-run { color: #2563eb; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 审计配置")

    st.subheader("数据来源")
    demo_mode = st.radio(
        "选择数据来源",
        ["📊 演示数据（自动生成）", "📁 上传 CSV 文件"],
        index=0,
    )

    uploaded_file = None
    n_days = 90

    if demo_mode == "📊 演示数据（自动生成）":
        n_days = st.slider("模拟天数", 30, 180, 90, step=30)
        st.info(
            f"生成 **2024-10-01** 起 **{n_days} 天**数据\n\n"
            "**审计主体:** 星辰跨境科技（深圳）\n\n"
            "**内置异常场景:**\n"
            "- 🛍️ 黑五大额结算批次\n"
            "- 📢 双11广告投放超支\n"
            "- 📦 SKU质量召回退款浪潮\n"
            "- 💱 未授权FX转换操作\n"
            "- 🗄️ ERP迁移数据缺口\n"
            "- 📋 会计系统重复入账"
        )
    else:
        uploaded_file = st.file_uploader(
            "上传交易 CSV",
            type=["csv"],
            help=(
                "必要列: txn_id, date, platform, currency, "
                "amount_local, amount_usd, category, description"
            ),
        )

    st.divider()
    st.subheader("AI 分析")
    enable_ai = st.toggle("启用 DeepSeek AI 分析", value=True)
    api_key_input = st.text_input(
        "DeepSeek API Key",
        value=DEEPSEEK_API_KEY,
        type="password",
        disabled=not enable_ai,
    )

    st.divider()
    st.caption("📜 合规声明")
    st.caption("本系统遵循 ISA 240（舞弊风险）及 ISA 520（分析程序）审计准则")
    st.caption("所有 CRITICAL/HIGH 级别发现均需人工复核")

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🔍 跨境电商资金流 AI 审计系统")

# Company profile card
st.markdown("""
<div style="background:#f0f4ff;border:1px solid #c7d7ff;border-radius:8px;padding:12px 20px;margin-bottom:8px;">
<b>审计主体：</b>星辰跨境科技（深圳）有限公司 &nbsp;·&nbsp;
<b>业务范围：</b>Amazon US / EU · TikTok Shop · Shopify · eBay 五平台跨境销售 &nbsp;·&nbsp;
<b>合规框架：</b>ISA 240（舞弊风险）· ISA 520（分析程序）
</div>
""", unsafe_allow_html=True)

col_info, col_badge, col_btn = st.columns([3, 1, 1])
with col_info:
    st.markdown(
        "演示数据覆盖 **2024 Q4**，内置 6 类真实异常场景：\n"
        "黑五大额结算 · 双11广告超支 · 产品召回退款浪潮 · 未授权FX转换 · ERP数据缺口 · 会计重复入账"
    )
with col_badge:
    if enable_ai:
        st.success("🤖 DeepSeek 已启用")
    else:
        st.warning("⚠️ 离线模式")
with col_btn:
    run_clicked = st.button("🚀 开始审计", type="primary", use_container_width=True)

st.divider()

# ── Pipeline ─────────────────────────────────────────────────────────────────
RISK_STYLE = {
    "CRITICAL": ("#c62828", "#ffebee", "🔴"),
    "HIGH":     ("#d84315", "#fff3e0", "🟠"),
    "MEDIUM":   ("#f9a825", "#fffde7", "🟡"),
    "LOW":      ("#2e7d32", "#e8f5e9", "🟢"),
}

if run_clicked:
    # Input validation
    if demo_mode == "📁 上传 CSV 文件" and uploaded_file is None:
        st.error("请先上传 CSV 文件，或切换为演示数据模式。")
        st.stop()

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = REPORTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    with st.status("🔄 正在运行审计流水线...", expanded=True) as pipeline_status:

        # Stage 1 ── Ingest
        st.write("📥 **Stage 1/5** — 数据摄入...")
        if demo_mode == "📊 演示数据（自动生成）":
            df_raw = generate_transactions(n_days=n_days)
            save_raw_data(df_raw, str(RAW_DATA_DIR))
        else:
            df_raw = pd.read_csv(uploaded_file)
        st.write(f"   ✅ 载入 **{len(df_raw):,}** 条原始交易记录")

        # Stage 2 ── Clean
        st.write("🧹 **Stage 2/5** — 数据清洗与质量评分...")
        cleaner = DataCleaner()
        df_clean, quality_report = cleaner.clean(df_raw)
        dq = quality_report.stats.get("completeness_pct", 0)
        st.write(f"   ✅ 清洗完成，数据质量得分: **{dq:.1f}%**")

        # Stage 3 ── Rules
        st.write("📋 **Stage 3/5** — 规则引擎审计（ISA 240/520）...")
        detector = RuleBasedAnomalyDetector(thresholds=ANOMALY_THRESHOLDS)
        findings = detector.run_all_checks(df_clean)
        rc = Counter(f.risk_level for f in findings)
        st.write(
            f"   ✅ 发现 **{len(findings)}** 条审计线索 "
            f"（{rc.get('CRITICAL',0)} CRITICAL · {rc.get('HIGH',0)} HIGH · "
            f"{rc.get('MEDIUM',0)} MEDIUM · {rc.get('LOW',0)} LOW）"
        )

        # Stage 4 ── AI
        ai_narrative = ""
        ai_result = {}
        if enable_ai and api_key_input:
            st.write("🤖 **Stage 4/5** — DeepSeek AI 深度分析（可能需 30–60 秒）...")
            try:
                classifier = DeepSeekClassifier(api_key=api_key_input)
                df_clean = classifier.classify_unclassified(df_clean)

                analyst = DeepSeekAuditAnalyst(api_key=api_key_input)
                summary_json = json.dumps(
                    detector.to_summary_dict(df_clean), indent=2, default=str
                )
                ai_result = analyst.analyze_anomalies(summary_json, ANOMALY_THRESHOLDS)

                if "error" not in ai_result:
                    overall = ai_result.get("overall_risk", "N/A")
                    ai_narrative = ai_result.get("summary_narrative", "")
                    st.write(f"   ✅ AI 分析完成，综合风险评级: **{overall}**")
                else:
                    st.warning(f"   ⚠️ AI 返回错误: {ai_result.get('error')} — 继续规则报告")
                    ai_narrative = "_AI 分析遇到问题，以下为规则引擎报告。_"
            except Exception as e:
                st.warning(f"   ⚠️ AI 调用失败: {e}")
                ai_narrative = f"_AI 分析暂时不可用（{e}）。以下为规则引擎报告。_"
        else:
            st.write("   ⏭️ **Stage 4/5** — AI 分析已跳过（离线模式）")
            ai_narrative = "_未启用 AI 分析。在侧边栏开启 DeepSeek 可获得 AI 叙述报告。_"

        # Stage 5 ── Report
        st.write("📊 **Stage 5/5** — 生成可视化图表与报告...")
        viz = ReportVisualizer(output_dir=str(run_dir))
        chart_paths = viz.generate_all(df_clean, findings)

        report_gen = ReportGenerator(output_dir=str(run_dir))
        report_path = report_gen.generate(
            df=df_clean,
            findings=findings,
            chart_paths=chart_paths,
            ai_narrative=ai_narrative,
            quality_stats=quality_report.stats,
        )
        # Save processed CSV alongside report
        proc_path = run_dir / f"clean_transactions_{run_id}.csv"
        df_clean.to_csv(proc_path, index=False, encoding="utf-8-sig")
        st.write(f"   ✅ 报告已保存至 `{run_dir.name}/`")

        pipeline_status.update(label="✅ 审计完成！", state="complete")

    st.session_state["audit"] = {
        "df": df_clean,
        "findings": findings,
        "quality_report": quality_report,
        "chart_paths": chart_paths,
        "report_path": report_path,
        "proc_path": str(proc_path),
        "ai_narrative": ai_narrative,
        "ai_result": ai_result,
        "run_id": run_id,
    }

# ── Results display ──────────────────────────────────────────────────────────
if "audit" not in st.session_state:
    # Landing placeholder
    st.info(
        "👈 在左侧选择数据来源并点击 **🚀 开始审计** 启动流水线。\n\n"
        "演示模式开箱即用，无需上传文件，约 **5–10 秒**出结果。"
    )
    st.stop()

audit = st.session_state["audit"]
df          = audit["df"]
findings    = audit["findings"]
quality_report = audit["quality_report"]
chart_paths = audit["chart_paths"]
report_path = audit["report_path"]
proc_path   = audit["proc_path"]
ai_narrative = audit["ai_narrative"]
ai_result   = audit["ai_result"]
run_id      = audit["run_id"]

# ── KPI row ──────────────────────────────────────────────────────────────────
st.subheader("📈 关键财务指标")

revenue  = df[df["category"] == "Product Revenue"]["amount_usd"].sum()
outflows = df[df["is_outflow"]]["abs_amount_usd"].sum()
net      = revenue - outflows
margin   = net / revenue * 100 if revenue > 0 else 0
rc       = Counter(f.risk_level for f in findings)

k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
k1.metric("💰 总收入", f"${revenue/1e6:.2f}M")
k2.metric("📤 总支出", f"${outflows/1e6:.2f}M")
k3.metric("📊 净利润率", f"{margin:.1f}%")
k4.metric("🔴 CRITICAL", rc.get("CRITICAL", 0))
k5.metric("🟠 HIGH",     rc.get("HIGH", 0))
k6.metric("🟡 MEDIUM",   rc.get("MEDIUM", 0))
k7.metric("✅ 数据质量", f"{quality_report.stats.get('completeness_pct', 0):.0f}%")

st.divider()

# ── Main content: findings + AI narrative ────────────────────────────────────
left, right = st.columns([3, 2])

with left:
    st.subheader(f"🚨 审计发现清单（共 {len(findings)} 条）")

    if not findings:
        st.success("未发现异常，数据质量良好。")
    else:
        for f in sorted(
            findings,
            key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(x.risk_level, 4),
        ):
            border, bg, icon = RISK_STYLE.get(f.risk_level, ("#666", "#f5f5f5", "⚪"))
            impact = f"${f.amount_impact_usd:,.0f}"
            st.markdown(
                f"""<div class="finding-card" style="background:{bg};border-left:4px solid {border};">
                <b>{icon} [{f.finding_id}] {f.risk_level} &nbsp;·&nbsp; {f.rule_name}</b>
                &nbsp;&nbsp;<span style="color:#555;font-size:0.85em;">影响金额: <b>{impact}</b></span><br>
                {f.description}
                </div>""",
                unsafe_allow_html=True,
            )

with right:
    # AI narrative
    st.subheader("🤖 AI 审计叙述 (DeepSeek)")
    if ai_narrative.startswith("_"):
        st.markdown(ai_narrative)
    else:
        st.info(ai_narrative)

    # AI supplemental findings
    ai_extra = ai_result.get("findings", [])
    if ai_extra:
        with st.expander(f"📋 AI 补充发现（{len(ai_extra)} 条）", expanded=True):
            for af in ai_extra:
                rl = af.get("risk_level", "MEDIUM")
                border2, bg2, icon2 = RISK_STYLE.get(rl, ("#666", "#f5f5f5", "⚪"))
                st.markdown(
                    f"""<div class="finding-card" style="background:{bg2};border-left:3px solid {border2};font-size:0.87rem;">
                    <b>{icon2} {af.get('finding_id','?')}: {af.get('category','')}</b><br>
                    {af.get('description','')}<br>
                    <i style="color:#555;">📌 建议: {af.get('recommended_procedure','')}</i>
                    </div>""",
                    unsafe_allow_html=True,
                )

    # Data quality
    st.subheader("📋 数据质量摘要")
    sev_icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}
    for issue in quality_report.issues:
        icon_q = sev_icon.get(issue["severity"], "⚪")
        st.markdown(
            f"{icon_q} **{issue['severity']}** — `{issue['field']}`: "
            f"{issue['description']} （n={issue['count']}）"
        )

st.divider()

# ── Charts ───────────────────────────────────────────────────────────────────
st.subheader("📊 可视化图表")

tab_cf, tab_pr, tab_cs, tab_sl, tab_ah, tab_rs = st.tabs([
    "📈 日现金流", "🏪 平台收入", "💸 成本结构",
    "⏱️ 结算周期", "🌡️ 异常热力图", "⚖️ 风险汇总",
])

chart_tab_map = {
    "01_daily_cashflow":       tab_cf,
    "02_platform_revenue":     tab_pr,
    "03_cost_structure":       tab_cs,
    "04_settlement_lag":       tab_sl,
    "05_anomaly_heatmap":      tab_ah,
    "06_risk_summary":         tab_rs,
}
for key, tab in chart_tab_map.items():
    with tab:
        path = chart_paths.get(key)
        if path and Path(path).exists():
            st.image(path, use_container_width=True)
        else:
            st.caption("图表未生成")

st.divider()

# ── Platform revenue table ────────────────────────────────────────────────────
st.subheader("🏪 平台收入分布")
platform_rev = (
    df[df["category"] == "Product Revenue"]
    .groupby("platform")["amount_usd"]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)
total_r = platform_rev["amount_usd"].sum()
platform_rev["占比"] = (platform_rev["amount_usd"] / total_r * 100).map("{:.1f}%".format)
platform_rev["收入 (USD)"] = platform_rev["amount_usd"].map("${:,.0f}".format)
st.dataframe(
    platform_rev[["platform", "收入 (USD)", "占比"]].rename(columns={"platform": "平台"}),
    use_container_width=True,
    hide_index=True,
)

# ── Data preview ─────────────────────────────────────────────────────────────
with st.expander("🔎 清洗后交易数据预览（前 100 行）"):
    display_cols = ["txn_id", "date", "platform", "currency", "amount_usd", "category", "description"]
    avail = [c for c in display_cols if c in df.columns]
    # Highlight anomaly rows
    flag_cols = [c for c in df.columns if c.startswith("flag_")]
    df_view = df[avail].head(100).copy()
    if flag_cols:
        df_view["⚠️ 异常标记"] = df[flag_cols].any(axis=1).head(100).map(
            lambda x: "⚠️" if x else ""
        )
    st.dataframe(df_view, use_container_width=True, hide_index=True)

st.divider()

# ── Download buttons ─────────────────────────────────────────────────────────
st.subheader("📥 下载")
dl1, dl2, dl3 = st.columns(3)

with dl1:
    report_text = Path(report_path).read_text(encoding="utf-8")
    st.download_button(
        label="📄 下载审计报告 (Markdown)",
        data=report_text,
        file_name=f"audit_report_{run_id}.md",
        mime="text/markdown",
        use_container_width=True,
    )

with dl2:
    csv_data = df.to_csv(index=False, encoding="utf-8")
    st.download_button(
        label="📊 下载清洗后数据 (CSV)",
        data=csv_data,
        file_name=f"clean_transactions_{run_id}.csv",
        mime="text/csv",
        use_container_width=True,
    )

with dl3:
    if ai_result:
        ai_json = json.dumps(ai_result, indent=2, ensure_ascii=False)
        st.download_button(
            label="🤖 下载 AI 分析 JSON",
            data=ai_json,
            file_name=f"ai_analysis_{run_id}.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.button("🤖 AI JSON（未启用）", disabled=True, use_container_width=True)

st.caption(f"Run ID: `{run_id}` · 报告路径: `{report_path}`")
