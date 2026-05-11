# -*- coding: utf-8 -*-
"""Streamlit project console for Cross-Border Audit Agent.

Run:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_MATERIALS_DIR = PROJECT_ROOT / "benchmarks" / "materials" / "case_001_minimal"
DEFAULT_TEMPLATE_ROOT = PROJECT_ROOT / "outputs" / "clean_templates"
DEFAULT_TEMPLATE_KEYWORD = "核心优化版"
WORKPAPERS_DIR = PROJECT_ROOT / "output" / "workpapers"


st.set_page_config(
    page_title="Cross-Border Audit Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
<style>
    :root {
        --ink: #111827;
        --muted: #667085;
        --line: #d9e2ec;
        --surface: #ffffff;
        --soft: #f5f7fb;
        --navy: #17324d;
        --teal: #0f766e;
        --amber: #b7791f;
    }
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2.5rem;
        max-width: 1240px;
    }
    .stApp {
        background: #f7f9fc;
        color: var(--ink);
    }
    [data-testid="stSidebar"] {
        background: #102033;
    }
    [data-testid="stSidebar"] * {
        color: #f8fafc;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stTextInput label {
        color: #dbe7f3 !important;
    }
    .hero {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 26px 30px;
        margin-bottom: 16px;
    }
    .eyebrow {
        color: var(--teal);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .hero h1 {
        font-size: 34px;
        line-height: 1.18;
        margin: 0 0 10px 0;
        letter-spacing: 0;
    }
    .hero p {
        color: #475467;
        font-size: 16px;
        line-height: 1.7;
        margin: 0;
        max-width: 980px;
    }
    .card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 16px 18px;
        height: 100%;
    }
    .card h3 {
        font-size: 16px;
        margin: 0 0 8px 0;
        color: var(--ink);
    }
    .card p {
        margin: 0;
        color: var(--muted);
        line-height: 1.6;
        font-size: 14px;
    }
    .stat {
        border-left: 4px solid var(--teal);
        background: #ffffff;
        border-radius: 8px;
        border-top: 1px solid var(--line);
        border-right: 1px solid var(--line);
        border-bottom: 1px solid var(--line);
        padding: 14px 16px;
    }
    .stat .num {
        font-size: 24px;
        font-weight: 760;
        color: var(--navy);
        margin-bottom: 2px;
    }
    .stat .label {
        color: var(--muted);
        font-size: 13px;
    }
    .section-title {
        font-size: 20px;
        font-weight: 750;
        color: var(--ink);
        margin: 18px 0 10px 0;
    }
    .step {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px 16px;
        min-height: 112px;
    }
    .step .idx {
        font-size: 12px;
        color: var(--amber);
        font-weight: 780;
        margin-bottom: 6px;
    }
    .step b {
        display: block;
        margin-bottom: 6px;
        color: var(--ink);
    }
    .step span {
        color: var(--muted);
        font-size: 13px;
        line-height: 1.55;
    }
    .status-pill {
        display: inline-block;
        border: 1px solid #b7e4dc;
        background: #ecfdf5;
        color: #065f46;
        border-radius: 999px;
        padding: 3px 10px;
        font-size: 12px;
        font-weight: 700;
    }
    .warn-pill {
        display: inline-block;
        border: 1px solid #f7d99c;
        background: #fffbeb;
        color: #92400e;
        border-radius: 999px;
        padding: 3px 10px;
        font-size: 12px;
        font-weight: 700;
    }
    code {
        white-space: pre-wrap !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


def _read_case_metadata(materials_dir: Path) -> dict:
    path = materials_dir / "case_metadata.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def _load_period_summary(path: str) -> pd.DataFrame:
    csv_path = Path(path) / "period_summary.csv"
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def _recent_workpapers(limit: int = 8) -> pd.DataFrame:
    if not WORKPAPERS_DIR.exists():
        return pd.DataFrame(columns=["file", "modified", "size_kb"])
    rows = []
    for path in sorted(WORKPAPERS_DIR.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        rows.append(
            {
                "file": path.name,
                "modified": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size_kb": round(path.stat().st_size / 1024, 1),
            }
        )
    return pd.DataFrame(rows)


def _path_status(path: Path) -> str:
    return "存在" if path.exists() else "缺失"


def _money(value: float | int | str) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


def _find_template(template_root: Path, keyword: str) -> Path:
    from scripts.generate_workpaper import find_template

    return find_template(template_root, keyword)


def _api_key_configured() -> bool:
    from audit_rag.config import get_settings

    return bool(get_settings().deepseek_api_key)


def _run_cash_workpaper(materials_dir: Path, template_root: Path, template_keyword: str, mode: str) -> Path:
    from benchmarks.agent.cash_workpaper_filler import fill_cash_workpaper
    from benchmarks.agent.materials_loader import load_case_materials
    from scripts.generate_workpaper import _build_cash_output_path

    materials = load_case_materials(materials_dir)
    template_path = _find_template(template_root, template_keyword)
    output_path = _build_cash_output_path(template_path, materials.meta.client_name, materials.meta.case_id)
    fill_cash_workpaper(
        materials_dir=materials_dir,
        template_path=template_path,
        output_path=output_path,
        llm_enhance=(mode == "autogen"),
    )
    return output_path


def _metric_cards() -> None:
    c1, c2, c3, c4 = st.columns(4)
    cards = [
        ("3", "核心 Agent 角色"),
        ("5", "C 底稿核心工作表"),
        ("25", "货币资金填表测试"),
        ("0", "干净模板外链与隐藏页"),
    ]
    for col, (num, label) in zip((c1, c2, c3, c4), cards):
        col.markdown(f'<div class="stat"><div class="num">{num}</div><div class="label">{label}</div></div>', unsafe_allow_html=True)


def _pipeline_steps() -> None:
    cols = st.columns(5)
    steps = [
        ("01", "数据摄入", "凭证、银行流水、函证、调节表、试算平衡表进入材料层。"),
        ("02", "规则扫描", "本地规则完成金额、期间、账户、调节项等基础识别。"),
        ("03", "RAG 检索", "从准则片段和项目知识库中检索可引用依据。"),
        ("04", "Agent 复核", "Data Extractor、Compliance Checker、Audit Partner 形成审计判断。"),
        ("05", "底稿输出", "写入 Excel 输入区，保留公式区、check 行和 tie-out 逻辑。"),
    ]
    for col, (idx, title, text) in zip(cols, steps):
        col.markdown(
            f'<div class="step"><div class="idx">{idx}</div><b>{title}</b><span>{text}</span></div>',
            unsafe_allow_html=True,
        )


def _repo_tree() -> str:
    return """cross_border_audit_agent/
├─ audit_rag/                  核心 RAG + 多 Agent 审计流水线
│  ├─ pipeline.py              主编排：数据、规则、RAG、Agent、报告
│  ├─ agents.py                Data Extractor / Compliance Checker / Audit Partner
│  ├─ critic.py                Reviewer Agent，结构化复核结论
│  ├─ orchestrator.py          Maker-Checker 有界重试状态机
│  ├─ rag.py                   知识库与检索入口
│  ├─ hybrid_retriever.py      BM25 + 向量 + RRF 混合检索
│  └─ reporting.py             Markdown 审计报告生成
├─ benchmarks/                 货币资金底稿评测与材料隔离区
│  ├─ agent/                   Agent 只能读取材料、不能读取 ground truth
│  ├─ materials/               客户交付包与合成材料
│  ├─ generators/              银行流水、函证、GL、错误注入生成器
│  ├─ ground_truth/            标准答案与错误清单
│  └─ evaluator/               后续 P/R/F1 评测器
├─ outputs/clean_templates/    无品牌 C 货币资金干净模板
├─ scripts/                    工作底稿、知识库、演示脚本
├─ sample_data/                固定资产与跨境电商样本凭证
├─ sample_knowledge/           CPA / 跨境审计知识片段
├─ tests/                      复核、检索、底稿填表测试
├─ cli.py                      统一命令行入口
└─ streamlit_app.py            项目展示与底稿生成前端"""


with st.sidebar:
    st.markdown("### Cross-Border Audit Agent")
    st.caption("项目展示、结构说明、货币资金底稿生成入口")
    st.divider()

    mode = st.selectbox("运行模式", ["mock", "autogen"], index=0, help="autogen 会调用 .env 中配置的 API。")
    materials_dir_text = st.text_input("材料目录", value=str(DEFAULT_MATERIALS_DIR))
    template_root_text = st.text_input("模板目录", value=str(DEFAULT_TEMPLATE_ROOT))
    template_keyword = st.text_input("模板关键词", value=DEFAULT_TEMPLATE_KEYWORD)

    materials_dir = Path(materials_dir_text)
    template_root = Path(template_root_text)

    st.divider()
    st.write("环境状态")
    st.write(f"材料目录：{_path_status(materials_dir)}")
    st.write(f"模板目录：{_path_status(template_root)}")
    key_status = "已配置" if _api_key_configured() else "未配置"
    pill_class = "status-pill" if key_status == "已配置" else "warn-pill"
    st.markdown(f'<span class="{pill_class}">DEEPSEEK_API_KEY：{key_status}</span>', unsafe_allow_html=True)


st.markdown(
    """
<div class="hero">
  <div class="eyebrow">Audit Agent Console</div>
  <h1>跨境电商审计 Agent 与货币资金底稿工厂</h1>
  <p>
    这个前端按 CrossAgent 式项目展台组织：先说明系统价值，再展示 Agent 流程、Benchmark 隔离设计、
    C 货币资金干净底稿模板，以及可直接运行的本地命令。适合放在 GitHub 仓库作为面试官或同行的第一入口。
  </p>
</div>
""",
    unsafe_allow_html=True,
)

_metric_cards()

tab_overview, tab_workpaper, tab_pipeline, tab_benchmark, tab_structure, tab_runbook = st.tabs(
    ["项目概览", "底稿生成", "Agent 流水线", "Benchmark", "项目结构", "运行指南"]
)


with tab_overview:
    st.markdown('<div class="section-title">项目定位</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.markdown(
        '<div class="card"><h3>审计推理内核</h3><p>围绕跨境电商和固定资产场景，整合规则扫描、RAG、三 Agent 讨论与 Reviewer 复核回路。</p></div>',
        unsafe_allow_html=True,
    )
    c2.markdown(
        '<div class="card"><h3>货币资金底稿工厂</h3><p>从材料目录读取银行流水、函证、GL、调节项，写入无品牌 C 底稿输入区，保留公式区。</p></div>',
        unsafe_allow_html=True,
    )
    c3.markdown(
        '<div class="card"><h3>可评测 Benchmark</h3><p>材料、标准答案、Agent 输出物理隔离，后续可量化 Precision、Recall、F1，而不是只做演示。</p></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">当前能力边界</div>', unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame(
            [
                ["跨境电商审计", "可运行", "凭证规则扫描、RAG、Agent 讨论、Markdown 报告"],
                ["固定资产底稿", "可运行", "K1 模板复制与 AI 审计说明页写入"],
                ["货币资金 C 底稿", "可运行", "干净模板、材料填表、mock/autogen 双模式"],
                ["评测器", "规划中", "已有隔离目录和 ground truth 设计，待接 P/R/F1"],
            ],
            columns=["模块", "状态", "说明"],
        ),
        width="stretch",
        hide_index=True,
    )


with tab_workpaper:
    st.markdown('<div class="section-title">C 货币资金底稿生成</div>', unsafe_allow_html=True)
    meta = _read_case_metadata(materials_dir)
    summary_df = _load_period_summary(str(materials_dir))

    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    with c1:
        st.markdown("**案例信息**")
        st.write(f"客户名称：{meta.get('client_name', '-')}")
        st.write(f"期末日：{meta.get('period_end', '-')}")
        st.write(f"TE：{_money(meta.get('te'))}")
        st.write(f"SAD：{_money(meta.get('sad'))}")
    with c2:
        st.markdown("**输入材料**")
        files = ["case_metadata.json", "period_summary.csv", "gl_bank.csv", "confirmations.csv", "bank_statement.csv", "reconciliation.csv"]
        for filename in files:
            st.write(f"{filename}：{_path_status(materials_dir / filename)}")
    with c3:
        st.markdown("**模板状态**")
        try:
            found_template = _find_template(template_root, template_keyword)
            st.success(found_template.name)
        except Exception as exc:
            st.warning(str(exc))

    if not summary_df.empty:
        display_cols = [col for col in ["company_name", "account_name", "bank_name", "bank_account", "currency", "period_end_balance_local"] if col in summary_df.columns]
        st.dataframe(summary_df[display_cols].head(20), width="stretch", hide_index=True)

    generate = st.button("生成货币资金底稿", type="primary", width="stretch")
    if generate:
        try:
            output_path = _run_cash_workpaper(materials_dir, template_root, template_keyword, mode)
            st.success("底稿已生成")
            st.code(str(output_path), language="text")
        except Exception as exc:
            st.error(f"生成失败：{exc}")

    st.markdown('<div class="section-title">最近生成文件</div>', unsafe_allow_html=True)
    st.dataframe(_recent_workpapers(), width="stretch", hide_index=True)


with tab_pipeline:
    st.markdown('<div class="section-title">从材料到审计结论</div>', unsafe_allow_html=True)
    _pipeline_steps()
    st.markdown('<div class="section-title">Mermaid 架构图</div>', unsafe_allow_html=True)
    st.code(
        """flowchart LR
    A[客户材料 CSV/PDF/XLSX] --> B[规则扫描与结构化解析]
    B --> C[RAG 检索 CAS/CPA 知识]
    C --> D[三 Agent 审计讨论]
    D --> E[Reviewer 复核回路]
    E --> F[Markdown 报告]
    E --> G[Excel 标准底稿]
    G --> H[Check 行与公式 tie-out]""",
        language="mermaid",
    )


with tab_benchmark:
    st.markdown('<div class="section-title">隔离评测设计</div>', unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame(
            [
                ["benchmarks/materials/", "Agent 可见", "客户交付包、CSV、PDF、XLSX"],
                ["benchmarks/agent/", "Agent 可见", "材料加载、上下文构建、Excel 写入"],
                ["benchmarks/ground_truth/", "Agent 禁止读取", "错误清单、标准答案、评分基准"],
                ["benchmarks/generators/", "开发期使用", "拟真材料和错误注入生成器"],
                ["benchmarks/evaluator/", "后续扩展", "Precision / Recall / F1 报告"],
            ],
            columns=["路径", "访问规则", "作用"],
        ),
        width="stretch",
        hide_index=True,
    )
    st.info("设计重点是防止 Agent 看到答案，同时让填表结果可以被自动评分。")


with tab_structure:
    st.markdown('<div class="section-title">仓库结构</div>', unsafe_allow_html=True)
    st.code(_repo_tree(), language="text")
    st.markdown('<div class="section-title">核心文件速查</div>', unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame(
            [
                ["cli.py", "统一 CLI：run / workpaper / search / doctor / paysim"],
                ["audit_rag/pipeline.py", "审计流水线主编排"],
                ["audit_rag/orchestrator.py", "Maker-Checker 复核状态机"],
                ["benchmarks/agent/cash_workpaper_filler.py", "C 货币资金底稿填表引擎"],
                ["benchmarks/agent/llm_enhancer.py", "可选 API 增强：风险等级与说明文本"],
                ["outputs/clean_templates/", "无品牌、无外链、无隐藏页的 C 底稿模板"],
                ["tests/test_cash_workpaper_filler.py", "货币资金填表回归测试"],
            ],
            columns=["文件", "职责"],
        ),
        width="stretch",
        hide_index=True,
    )


with tab_runbook:
    st.markdown('<div class="section-title">本地启动</div>', unsafe_allow_html=True)
    st.code(
        """git clone https://github.com/wangzichang224-design/cross_border_audit_agent.git
cd cross_border_audit_agent
pip install -r requirements-phase1.txt
streamlit run streamlit_app.py""",
        language="powershell",
    )
    st.markdown('<div class="section-title">CLI 示例</div>', unsafe_allow_html=True)
    st.code(
        """python cli.py doctor
python cli.py run --case-type cross_border --mode mock
python cli.py workpaper --case-type cash --mode mock --materials-dir benchmarks\\materials\\case_001_minimal --template-root outputs\\clean_templates --template-keyword 核心优化版
python cli.py workpaper --case-type cash --mode autogen --materials-dir benchmarks\\materials\\case_001_minimal --template-root outputs\\clean_templates --template-keyword 核心优化版""",
        language="powershell",
    )
    st.warning("autogen 会调用远端 API，真实客户数据请先脱敏，或者接入私有化模型。")
