# -*- coding: utf-8 -*-
"""Minimal Streamlit UI for generating a clean C cash workpaper.

Run:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_TEMPLATE_ROOT = PROJECT_ROOT / "outputs" / "clean_templates"
DEFAULT_TEMPLATE_KEYWORD = "核心优化版"
UPLOAD_MATERIALS_DIR = PROJECT_ROOT / "output" / "uploaded_materials"


st.set_page_config(
    page_title="货币资金底稿生成",
    page_icon=None,
    layout="centered",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
<style>
    :root {
        --ink: #111827;
        --muted: #667085;
        --line: #d9e2ec;
        --surface: #ffffff;
        --soft: #f6f8fb;
        --accent: #0f766e;
        --accent-dark: #115e59;
        --warn: #a16207;
    }
    .stApp {
        background: var(--soft);
        color: var(--ink);
    }
    .block-container {
        max-width: 980px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    .hero {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 24px 28px;
        margin-bottom: 18px;
    }
    .hero h1 {
        margin: 0 0 8px 0;
        font-size: 30px;
        line-height: 1.2;
        letter-spacing: 0;
    }
    .hero p {
        color: var(--muted);
        font-size: 15px;
        line-height: 1.7;
        margin: 0;
    }
    .panel {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 14px;
    }
    .mini-title {
        font-size: 16px;
        font-weight: 750;
        margin-bottom: 10px;
    }
    .hint {
        color: var(--muted);
        font-size: 13px;
        line-height: 1.6;
    }
    .ok {
        color: #047857;
        font-weight: 700;
    }
    .warn {
        color: var(--warn);
        font-weight: 700;
    }
    div[data-testid="stFileUploader"] {
        background: #fbfcfe;
        border: 1px solid #e5eaf0;
        border-radius: 8px;
        padding: 8px 10px;
    }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 10px 12px;
    }
</style>
""",
    unsafe_allow_html=True,
)


TRIAL_BALANCE_ALIASES = {
    "account_name": ["account_name", "科目", "科目名称", "账户类型", "报表项目"],
    "bank_name": ["bank_name", "银行", "银行名称", "开户行"],
    "bank_account": ["bank_account", "银行账号", "账号", "账户", "银行账户"],
    "currency": ["currency", "币种", "货币"],
    "period_end_balance_local": [
        "period_end_balance_local",
        "期末余额",
        "期末本币余额",
        "本币余额",
        "余额",
    ],
    "period_end_balance_fx": [
        "period_end_balance_fx",
        "期末原币余额",
        "原币余额",
        "期末余额原币",
    ],
    "fx_rate": ["fx_rate", "汇率"],
    "is_restricted": ["is_restricted", "是否受限", "受限"],
    "restriction_note": ["restriction_note", "受限说明", "受限原因", "备注"],
    "prior_year_balance": ["prior_year_balance", "上年余额", "上期余额", "上年审定数"],
}

JOURNAL_ALIASES = {
    "date": ["date", "日期", "凭证日期", "记账日期"],
    "voucher_id": ["voucher_id", "凭证号", "凭证编号", "字号"],
    "account_code": ["account_code", "科目编码", "会计科目编码"],
    "account_name": ["account_name", "科目", "科目名称", "会计科目"],
    "debit": ["debit", "借方", "借方金额"],
    "credit": ["credit", "贷方", "贷方金额"],
    "summary": ["summary", "摘要", "说明"],
    "counterparty": ["counterparty", "对方科目", "对手方", "往来单位"],
    "bank_name": ["bank_name", "银行", "银行名称", "开户行"],
    "bank_account": ["bank_account", "银行账号", "账号", "银行账户"],
    "currency": ["currency", "币种", "货币"],
}

CONFIRMATION_ALIASES = {
    "bank_name": ["bank_name", "银行", "银行名称", "开户行"],
    "bank_account": ["bank_account", "银行账号", "账号", "银行账户"],
    "currency": ["currency", "币种", "货币"],
    "confirmed_balance": ["confirmed_balance", "回函余额", "确认余额", "银行确认余额"],
    "restricted_amount": ["restricted_amount", "受限金额", "冻结金额", "保证金金额"],
    "restriction_nature": ["restriction_nature", "受限性质", "受限原因", "备注"],
    "confirmation_date": ["confirmation_date", "回函日期", "函证日期"],
    "confirmation_index": ["confirmation_index", "索引", "索引号"],
}


def _normalize_name(value: object) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("（", "(")
        .replace("）", ")")
    )


def _read_uploaded_table(uploaded_file) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file, encoding="utf-8-sig")


def _canonicalize_columns(df: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    normalized = {_normalize_name(col): col for col in df.columns}
    out = pd.DataFrame(index=df.index)
    for canonical, candidates in aliases.items():
        found = None
        for candidate in candidates:
            found = normalized.get(_normalize_name(candidate))
            if found is not None:
                break
        if found is not None:
            out[canonical] = df[found]
    return out


def _ensure_columns(
    df: pd.DataFrame,
    required: Iterable[str],
    optional_defaults: dict[str, object],
    label: str,
) -> pd.DataFrame:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{label}缺少列：{', '.join(missing)}")
    for col, default in optional_defaults.items():
        if col not in df.columns:
            df[col] = default
    return df


def _clean_amount(value: object, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    text = str(value).replace(",", "").strip()
    if not text:
        return default
    return float(text)


def _clean_bool(value: object) -> bool:
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "是", "受限"}


def _safe_path_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value)).strip(" ._")
    return cleaned or fallback


def _prepare_trial_balance(df: pd.DataFrame, currency: str) -> pd.DataFrame:
    df = _canonicalize_columns(df, TRIAL_BALANCE_ALIASES)
    df = _ensure_columns(
        df,
        required=["account_name", "period_end_balance_local"],
        optional_defaults={
            "bank_name": "",
            "bank_account": "",
            "currency": currency,
            "period_end_balance_fx": None,
            "fx_rate": 1.0,
            "is_restricted": False,
            "restriction_note": "",
            "prior_year_balance": 0.0,
        },
        label="试算平衡表",
    )
    df["currency"] = df["currency"].fillna(currency).replace("", currency)
    df["period_end_balance_local"] = df["period_end_balance_local"].map(_clean_amount)
    df["period_end_balance_fx"] = df.apply(
        lambda row: _clean_amount(
            row["period_end_balance_fx"],
            default=float(row["period_end_balance_local"]),
        ),
        axis=1,
    )
    df["fx_rate"] = df["fx_rate"].map(lambda value: _clean_amount(value, 1.0))
    df["is_restricted"] = df["is_restricted"].map(_clean_bool)
    df["prior_year_balance"] = df["prior_year_balance"].map(_clean_amount)
    return df[
        [
            "account_name",
            "bank_name",
            "bank_account",
            "currency",
            "period_end_balance_local",
            "period_end_balance_fx",
            "fx_rate",
            "is_restricted",
            "restriction_note",
            "prior_year_balance",
        ]
    ]


def _prepare_journal(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = _canonicalize_columns(df, JOURNAL_ALIASES)
    gl = _ensure_columns(
        raw.copy(),
        required=["date", "account_code", "account_name", "debit", "credit", "summary"],
        optional_defaults={"voucher_id": "", "counterparty": ""},
        label="序时账",
    )
    gl["voucher_id"] = [
        value if str(value).strip() else f"JV{idx + 1:05d}"
        for idx, value in enumerate(gl["voucher_id"])
    ]
    gl["debit"] = gl["debit"].map(_clean_amount)
    gl["credit"] = gl["credit"].map(_clean_amount)
    gl_out = gl[
        [
            "date",
            "voucher_id",
            "account_code",
            "account_name",
            "debit",
            "credit",
            "summary",
            "counterparty",
        ]
    ]

    bank_headers = [
        "date",
        "bank_name",
        "bank_account",
        "currency",
        "debit",
        "credit",
        "balance",
        "description",
        "counterparty",
        "txn_id",
    ]
    if {"bank_name", "bank_account"}.issubset(raw.columns):
        bank = raw.copy()
        bank["currency"] = bank.get("currency", "CNY")
        bank["balance"] = 0.0
        bank["description"] = bank.get("summary", "")
        bank["txn_id"] = gl["voucher_id"]
        bank["debit"] = gl["credit"]
        bank["credit"] = gl["debit"]
        bank["counterparty"] = gl["counterparty"]
        bank_out = bank[bank_headers]
    else:
        bank_out = pd.DataFrame(columns=bank_headers)
    return gl_out, bank_out


def _prepare_confirmations(df: pd.DataFrame, currency: str) -> pd.DataFrame:
    df = _canonicalize_columns(df, CONFIRMATION_ALIASES)
    df = _ensure_columns(
        df,
        required=["bank_name", "bank_account", "confirmed_balance"],
        optional_defaults={
            "currency": currency,
            "restricted_amount": 0.0,
            "restriction_nature": "",
            "confirmation_date": "",
            "confirmation_index": "",
        },
        label="询证函回函",
    )
    df["currency"] = df["currency"].fillna(currency).replace("", currency)
    df["confirmed_balance"] = df["confirmed_balance"].map(_clean_amount)
    df["restricted_amount"] = df["restricted_amount"].map(_clean_amount)
    return df[
        [
            "bank_name",
            "bank_account",
            "currency",
            "confirmed_balance",
            "restricted_amount",
            "restriction_nature",
            "confirmation_date",
            "confirmation_index",
        ]
    ]


def _build_reconciliation(period_summary: pd.DataFrame, confirmations: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ps_by_account = {
        str(row.bank_account): row
        for row in period_summary.itertuples(index=False)
        if str(row.bank_account).strip()
    }
    for conf in confirmations.itertuples(index=False):
        ps = ps_by_account.get(str(conf.bank_account))
        if ps is None:
            continue
        diff = float(conf.confirmed_balance) - float(ps.period_end_balance_fx)
        if abs(diff) < 0.01:
            continue
        rows.append(
            {
                "category": "book_plus" if diff > 0 else "book_minus",
                "description": "回函余额与账面余额差异，待进一步核对",
                "amount": abs(diff),
                "index": "函证/银行回函",
            }
        )
    return pd.DataFrame(rows, columns=["category", "description", "amount", "index"])


def _write_materials_package(
    *,
    client_name: str,
    period_end: date,
    analysis_date: date,
    te: float,
    sad: float,
    currency: str,
    trial_balance_file,
    journal_file,
    confirmation_file,
) -> tuple[Path, dict[str, int]]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_client = _safe_path_part(client_name, "uploaded_case")
    materials_dir = UPLOAD_MATERIALS_DIR / f"{stamp}_{safe_client}"
    materials_dir.mkdir(parents=True, exist_ok=True)

    trial_balance = _prepare_trial_balance(_read_uploaded_table(trial_balance_file), currency)
    gl_bank, bank_statement = _prepare_journal(_read_uploaded_table(journal_file))
    confirmations = _prepare_confirmations(_read_uploaded_table(confirmation_file), currency)
    reconciliation = _build_reconciliation(trial_balance, confirmations)

    metadata = {
        "case_id": materials_dir.name,
        "client_name": client_name or "未命名客户",
        "period_end": period_end.isoformat(),
        "analysis_date": analysis_date.isoformat(),
        "te": float(te),
        "sad": float(sad),
        "gaap": "企业会计准则",
        "currency": currency,
        "variation_pct": 0.1,
    }
    (materials_dir / "case_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    trial_balance.to_csv(materials_dir / "period_summary.csv", index=False, encoding="utf-8-sig")
    gl_bank.to_csv(materials_dir / "gl_bank.csv", index=False, encoding="utf-8-sig")
    bank_statement.to_csv(materials_dir / "bank_statement.csv", index=False, encoding="utf-8-sig")
    confirmations.to_csv(materials_dir / "confirmations.csv", index=False, encoding="utf-8-sig")
    reconciliation.to_csv(materials_dir / "reconciliation.csv", index=False, encoding="utf-8-sig")

    counts = {
        "试算平衡表": len(trial_balance),
        "序时账": len(gl_bank),
        "询证函回函": len(confirmations),
    }
    return materials_dir, counts


def _find_template() -> Path:
    from scripts.generate_workpaper import find_template

    return find_template(DEFAULT_TEMPLATE_ROOT, DEFAULT_TEMPLATE_KEYWORD)


def _api_key_configured() -> bool:
    from audit_rag.config import get_settings

    return bool(get_settings().deepseek_api_key)


def _run_cash_workpaper(materials_dir: Path, use_llm: bool) -> Path:
    from benchmarks.agent.cash_workpaper_filler import fill_cash_workpaper
    from benchmarks.agent.materials_loader import load_case_materials
    from scripts.generate_workpaper import _build_cash_output_path

    materials = load_case_materials(materials_dir)
    template_path = _find_template()
    output_path = _build_cash_output_path(
        template_path,
        materials.meta.client_name,
        materials.meta.case_id,
    )
    fill_cash_workpaper(
        materials_dir=materials_dir,
        template_path=template_path,
        output_path=output_path,
        llm_enhance=use_llm,
    )
    return output_path


def _download_button(path: Path) -> None:
    st.download_button(
        "下载已生成的底稿",
        data=path.read_bytes(),
        file_name=path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        width="stretch",
    )


st.markdown(
    """
<div class="hero">
    <h1>货币资金审计底稿自动生成</h1>
    <p>上传试算平衡表、序时账、询证函回函，系统会整理为审计材料包，写入无品牌 C 货币资金底稿，并生成可下载的 Excel 文件。</p>
</div>
""",
    unsafe_allow_html=True,
)


with st.form("workpaper_form", clear_on_submit=False):
    st.markdown('<div class="panel"><div class="mini-title">1. 上传关键文件</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        trial_balance_file = st.file_uploader(
            "试算平衡表",
            type=["csv", "xlsx", "xls"],
            help="至少包含：科目/账户、期末余额；有银行、账号、币种会更完整。",
        )
    with col2:
        journal_file = st.file_uploader(
            "序时账",
            type=["csv", "xlsx", "xls"],
            help="至少包含：日期、科目编码、科目、借方、贷方、摘要。",
        )
    with col3:
        confirmation_file = st.file_uploader(
            "询证函回函",
            type=["csv", "xlsx", "xls"],
            help="至少包含：银行、账号、回函余额。",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel"><div class="mini-title">2. 案件参数</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        client_name = st.text_input("客户名称", value="星辰跨境科技(深圳)有限公司")
        period_end = st.date_input("期末日", value=date(2025, 12, 31))
        currency = st.selectbox("记账本位币", ["CNY", "USD", "EUR", "HKD"], index=0)
    with c2:
        analysis_date = st.date_input("编制日期", value=date.today())
        te = st.number_input("TE", min_value=0.0, value=5_000_000.0, step=100_000.0)
        sad = st.number_input("SAD", min_value=0.0, value=250_000.0, step=10_000.0)

    use_llm = st.checkbox(
        "使用 API 增强风险等级和说明文字",
        value=False,
        disabled=not _api_key_configured(),
        help="默认关闭，避免未脱敏资料离开本机。开启前请确认 .env 已配置 API Key 且资料可外发。",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    submitted = st.form_submit_button("生成底稿", type="primary", width="stretch")


if submitted:
    missing_uploads = [
        label
        for label, file in (
            ("试算平衡表", trial_balance_file),
            ("序时账", journal_file),
            ("询证函回函", confirmation_file),
        )
        if file is None
    ]
    if missing_uploads:
        st.error(f"请先上传：{'、'.join(missing_uploads)}")
    else:
        try:
            with st.spinner("正在整理材料并生成底稿..."):
                materials_dir, counts = _write_materials_package(
                    client_name=client_name,
                    period_end=period_end,
                    analysis_date=analysis_date,
                    te=te,
                    sad=sad,
                    currency=currency,
                    trial_balance_file=trial_balance_file,
                    journal_file=journal_file,
                    confirmation_file=confirmation_file,
                )
                output_path = _run_cash_workpaper(materials_dir, use_llm=use_llm)

            st.session_state["last_output_path"] = str(output_path)
            st.session_state["last_materials_dir"] = str(materials_dir)
            st.session_state["last_counts"] = counts
            st.success("底稿已生成")
        except Exception as exc:
            st.error(f"生成失败：{exc}")


if "last_output_path" in st.session_state:
    output = Path(st.session_state["last_output_path"])
    counts = st.session_state.get("last_counts", {})
    st.markdown('<div class="panel"><div class="mini-title">3. 下载结果</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("试算平衡表", f"{counts.get('试算平衡表', 0)} 行")
    c2.metric("序时账", f"{counts.get('序时账', 0)} 行")
    c3.metric("询证函回函", f"{counts.get('询证函回函', 0)} 行")
    st.caption(f"输出文件：{output}")
    _download_button(output)
    st.markdown("</div>", unsafe_allow_html=True)


with st.expander("支持的列名"):
    st.markdown(
        """
系统会自动识别常见中文列名。最小要求：

- 试算平衡表：`科目`、`期末余额`
- 序时账：`日期`、`科目编码`、`科目`、`借方`、`贷方`、`摘要`
- 询证函回函：`银行`、`银行账号`、`回函余额`

如果文件已经使用英文列名，也支持项目内部字段名，如 `account_name`、`period_end_balance_local`、`confirmed_balance`。
""",
    )
