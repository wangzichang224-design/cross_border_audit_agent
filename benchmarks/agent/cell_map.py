# -*- coding: utf-8 -*-
"""
Cell mapping for the C 货币资金 audit workpaper (3 core sheets).

This module is the single source of truth for **which Excel cells the Agent
writes into**, what each cell means in audit terms, and which cells are
pre-computed formulas that must NOT be touched.

Design choices
--------------
- Constants over JSON: cell addresses are Python constants so IDEs can
  jump-to-definition and type-checkers can catch typos. JSON is great for
  user-editable configs but cell maps are developer-internal.
- Sheet name spelling matches the xlsx verbatim (case- and space-sensitive),
  because openpyxl looks them up exactly.
- Repeated row structures (GL accounts, recon items, cutoff samples) use
  ``@dataclass(frozen=True)`` so the Agent passes typed objects, not dicts.

What's an "input cell"?
-----------------------
The C workpaper has three classes of cells:

1. **Input cells** (Agent writes): company name, period-end, base balances,
   risk-level dropdowns, reconciliation items, cutoff sample rows.
2. **Formula cells** (template pre-fills): threshold = IF(risk=...,$C$5*x,…),
   ΣSum cells, Check cells that should equal 0, =MIN cross-sheet refs.
   Agent must NOT overwrite these or the workpaper breaks.
3. **Label / decorative cells** (template pre-fills): row headers like
   "客户名称", section titles, the "返回汇总页" hyperlink texts. Agent
   never touches these either.

This module enumerates (1). ``all_writable_cells()`` returns the full
allowlist used for testing and for the pre-commit guard against the Agent
accidentally writing outside its lane.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping


# ──────────────────────────────────────────────────────────────────────────────
# Sheet names — MUST match the xlsx verbatim (no normalization)
# ──────────────────────────────────────────────────────────────────────────────

SHEET_LEAD = "C.00 Lead"
SHEET_RECON = "C.02 Bank reconciliations"
SHEET_CUTOFF = "C.03 Cutoff"

ALL_SHEETS = (SHEET_LEAD, SHEET_RECON, SHEET_CUTOFF)


# ──────────────────────────────────────────────────────────────────────────────
# C.00 Lead — Header block (rows 2-8)
# ──────────────────────────────────────────────────────────────────────────────
# This block tells the auditor (and downstream formulas) the basic scope of
# the cash workpaper: client, period, materiality thresholds, and reporting
# currency. Threshold formulas in D15:D19 reference $C$5, so LEAD_TE must be
# filled before risk levels make sense.

LEAD_COMPANY_NAME = "C2"
"""客户名称 — 被审计单位全称（例：星辰跨境科技(深圳)有限公司）"""

LEAD_PERIOD_END = "C3"
"""期末日期 — Excel 日期（例：2025-12-31）。被 K36 引用做 YoY 对比。"""

LEAD_ANALYSIS_DATE = "C4"
"""分析日期 — 本次审计程序执行日期"""

LEAD_TE = "C5"
"""可容忍误差 (Tolerable Error)，绝对金额，本位币。
驱动 D15:D19 阈值公式。例：5,000,000"""

LEAD_SAD = "C6"
"""名义金额 (Summary of Audit Differences threshold)，绝对金额。
低于此值的错报放弃进一步调查。例：250,000"""

LEAD_GAAP = "C7"
"""适用会计准则。例：'企业会计准则' / 'IFRS'"""

LEAD_CURRENCY = "C8"
"""记账本位币。例：'CNY' / 'USD'。被 B31 引用拼成图表标题。"""


# ──────────────────────────────────────────────────────────────────────────────
# C.00 Lead — Assertion risk levels (rows 15-19, column C)
# ──────────────────────────────────────────────────────────────────────────────
# These dropdown cells drive the D-column threshold formulas. Each must be
# one of ALLOWED_RISK_LEVELS or the IF chain breaks.

ALLOWED_RISK_LEVELS = ("Minimal", "Low", "Moderate", "High", "Significant")

LEAD_RISK_COMPLETENESS = "C15"   # 完整性 (C)
LEAD_RISK_EXISTENCE = "C16"      # 存在性 (E)
LEAD_RISK_VALUATION = "C17"      # 计价 (V)
LEAD_RISK_RIGHTS = "C18"         # 权利和义务 (R&O)
LEAD_RISK_PRESENTATION = "C19"   # 列报和披露 (P&D)


# ──────────────────────────────────────────────────────────────────────────────
# C.00 Lead — 波动幅度阈值 (row 32)
# ──────────────────────────────────────────────────────────────────────────────

LEAD_VARIATION_PCT = "C32"
"""波动幅度% — 默认 0.1 (即 10%)。
驱动 O38:O40 的 IF 判断："本年 vs 上年变动 ≥ 此值 AND 金额 ≥ 波动金额 → 标记进一步调查"。"""


# ──────────────────────────────────────────────────────────────────────────────
# C.00 Lead — 表1 总账科目余额 (rows 37-42)
# ──────────────────────────────────────────────────────────────────────────────
# Three fixed account rows (库存现金/银行存款/其他货币资金) + sum row 42.
# Pre-filled formulas (DO NOT OVERWRITE):
#   H{row} = F+G        (期末未审数)
#   J{row} = H+I        (期末审定数)
#   L{row} = J-K        (变动金额)
#   M{row} = L/K        (变动%)
#   O{row} = IF(...)    (是否进一步调查)
#   F42:O42 = SUM/...   (合计行)

LEAD_GL_ROWS: Mapping[str, int] = {
    "库存现金": 38,
    "银行存款": 39,
    "其他货币资金": 40,
}


@dataclass(frozen=True)
class LeadGLRow:
    """One row in C.00 Lead's main GL balance table.

    Columns the Agent writes (others are formulas or pre-filled labels):
    """

    bookkeeping_code: str = ""         # B — 账套名称/账套编码 (可选)
    gl_account_code: str = ""          # C — 总账科目编码 (例：'1001')
    index_ref: str = ""                # E — 索引号 (例：'C.00 BKD/')
    book_value_unaudited: float = 0.0  # F — 期末账面数
    book_adjustment: float = 0.0       # G — 账表调整数
    audit_adjustment: float = 0.0      # I — 审计调整数
    prior_year_audited: float = 0.0    # K — 上期末审定数
    notes_tag: str = ""                # N — Notes 标签 (例：'[A]')


# Column-letter map for one LeadGLRow. Keys match LeadGLRow field names.
LEAD_GL_COLS: Mapping[str, str] = {
    "bookkeeping_code": "B",
    "gl_account_code": "C",
    # D is the fixed account name label (pre-filled by template)
    "index_ref": "E",
    "book_value_unaudited": "F",
    "book_adjustment": "G",
    # H is formula =F+G
    "audit_adjustment": "I",
    # J is formula =H+I
    "prior_year_audited": "K",
    # L, M are formulas
    "notes_tag": "N",
    # O is formula
}


# ──────────────────────────────────────────────────────────────────────────────
# C.00 Lead — 表2 For Disclosure (rows 63-66)
# ──────────────────────────────────────────────────────────────────────────────
# Reconciliation against 表1: C{row} (current) and D{row} (prior).
# C67/D67 are SUM formulas; E67/F67 are Check formulas (vs J42/K42).

LEAD_DISCLOSURE_ROWS: Mapping[str, int] = {
    "库存现金": 63,
    "银行存款": 64,
    "其他货币资金": 65,
    "存放财务公司款项": 66,
}

LEAD_DISCLOSURE_CURRENT_COL = "C"  # 期末数
LEAD_DISCLOSURE_PRIOR_COL = "D"    # 上期末数


# ──────────────────────────────────────────────────────────────────────────────
# C.00 Lead — 受限货币资金 (rows 73+, free-form list)
# ──────────────────────────────────────────────────────────────────────────────
# The template leaves space below row 72 ("所有权或使用权受到限制的货币资金")
# for the Agent to enumerate restricted balances. We treat row 73 as the
# starting row and write one item per row.

LEAD_RESTRICTED_START_ROW = 73


@dataclass(frozen=True)
class LeadRestrictedItem:
    """One restricted-cash line item."""

    description: str       # B — 描述（例："票据保证金 - 招行"）
    amount: float = 0.0    # C — 金额 (本位币)
    nature: str = ""       # D — 受限性质 (例："质押"/"冻结"/"专款专用")
    index: str = ""        # E — 索引号 (例："C.01 第3行")


LEAD_RESTRICTED_COLS: Mapping[str, str] = {
    "description": "B",
    "amount": "C",
    "nature": "D",
    "index": "E",
}


# ──────────────────────────────────────────────────────────────────────────────
# C.02 Bank reconciliations — Account header block (rows 17-21)
# ──────────────────────────────────────────────────────────────────────────────
# The template ships with 表1.1 for ONE account. Multi-account scenarios
# duplicate the whole block downward; for MVP we fill account #1 only.

RECON_ACCOUNT_SUBJECT = "C17"     # 科目 (例："银行存款")
RECON_BANK_NAME = "C18"           # 银行名称
RECON_BANK_ACCOUNT = "C19"        # 银行账号
RECON_CURRENCY = "C20"            # 原币币种
RECON_STATEMENT_DATE = "C21"      # 余额调节表编制日期


# ──────────────────────────────────────────────────────────────────────────────
# C.02 — Base balances (row 24) — the "starting point" for reconciliation
# ──────────────────────────────────────────────────────────────────────────────

RECON_BOOK_BASE = "C24"   # 期末账面数 (原币) — GL 期末余额
RECON_BANK_BASE = "F24"   # 银行对账单金额 (原币) — 对账单期末余额


# ──────────────────────────────────────────────────────────────────────────────
# C.02 — Reconciling items (rows 26-29 and 31-34, four per category)
# ──────────────────────────────────────────────────────────────────────────────
# Four categories, each with 4 rows max:
#   书侧 (book side, columns B/C/D):
#     row 25 label "加：银收企未收"  (book +) → items rows 26-29
#     row 30 label "减：银付企未付"  (book -) → items rows 31-34
#   行侧 (bank side, columns E/F/G):
#     row 25 label "加：企收银未收"  (bank +) → items rows 26-29
#     row 30 label "减：企付银未付"  (bank -) → items rows 31-34
#
# C25/F25/C30/F30 are SUM formulas (DO NOT overwrite).
# C35/F35 = =base + plus - minus  (调节后金额合计, formula)
# C36 = F35-C35  (Check, should equal 0)

# Inclusive row ranges (start, end) for each category's item rows
RECON_BOOK_PLUS_ROWS = (26, 29)    # 加：银收企未收
RECON_BOOK_MINUS_ROWS = (31, 34)   # 减：银付企未付
RECON_BANK_PLUS_ROWS = (26, 29)    # 加：企收银未收 (same rows, different cols)
RECON_BANK_MINUS_ROWS = (31, 34)   # 减：企付银未付

# Column letters per side
RECON_BOOK_DESC_COL = "B"
RECON_BOOK_AMOUNT_COL = "C"
RECON_BOOK_INDEX_COL = "D"
RECON_BANK_DESC_COL = "E"
RECON_BANK_AMOUNT_COL = "F"
RECON_BANK_INDEX_COL = "G"


@dataclass(frozen=True)
class ReconItem:
    """One reconciliation item line.

    Categories use the SAME shape — the side (book/bank) and sign (+/-) come
    from where you place the item, not from the item itself.
    """

    description: str       # 摘要
    amount: float          # 金额（正数；正负号由所在的分类决定）
    index: str = ""        # 索引号（例："C.01 第 12 行"或"GL #487"）


# ──────────────────────────────────────────────────────────────────────────────
# C.03 Cutoff — Two inter-bank transfer test sample tables
# ──────────────────────────────────────────────────────────────────────────────
# Pre-period (rows 20-24): 5 sample rows for transfers initiated near
#   period-end that may straddle the cutoff.
# Post-period (rows 29-33): 5 sample rows for transfers initiated just
#   after period-end that may have been pre-dated.
#
# P-column is a formula (=M+I) that should equal 0 for a matched transfer.

CUTOFF_PRE_PERIOD_ROW_RANGE = (20, 24)   # inclusive
CUTOFF_POST_PERIOD_ROW_RANGE = (29, 33)  # inclusive

CUTOFF_WINDOW = "C8"
"""使用的截止期间（例："期末前后 5 个工作日" 或 "期末前后 3 天"）。
影响哪些转账被纳入样本范围。"""


@dataclass(frozen=True)
class CutoffSample:
    """One inter-bank transfer cutoff test sample."""

    sample_id: str            # B — 样本编号 (例："S1")
    company_name: str         # C — 公司名称
    out_bank_name: str        # D — 转出方银行
    out_bank_account: str     # E — 转出方账号
    out_time: str             # F — 收款/付款时间
    txn_id: str               # G — 交易编号
    currency: str             # H — 币种
    out_amount: float         # I — 转出方金额（付款填负数）
    in_bank_name: str         # J — 转入方银行
    in_bank_account: str      # K — 转入方账号
    in_date: str              # L — 转入方交易日期
    in_amount: float          # M — 转入方金额（收款填正数）
    is_in_reconciliation: str = ""  # N — 跨期是否在余调节表中体现 (是/否)
    notes: str = ""           # O — 备注
    # P is formula =M+I (Check)


CUTOFF_SAMPLE_COLS: Mapping[str, str] = {
    "sample_id": "B",
    "company_name": "C",
    "out_bank_name": "D",
    "out_bank_account": "E",
    "out_time": "F",
    "txn_id": "G",
    "currency": "H",
    "out_amount": "I",
    "in_bank_name": "J",
    "in_bank_account": "K",
    "in_date": "L",
    "in_amount": "M",
    "is_in_reconciliation": "N",
    "notes": "O",
}


# ──────────────────────────────────────────────────────────────────────────────
# Allowlist of writable cells (for testing isolation + pre-commit guards)
# ──────────────────────────────────────────────────────────────────────────────


def all_writable_cells() -> dict[str, set[str]]:
    """Return ``{sheet_name: {cell_addr, ...}}`` — every cell the Agent may
    write into. Used by:

    - Unit tests: assert the Agent didn't write outside this set
    - Pre-commit guard: future audit-tool to verify cell_map drift
    - Documentation: a single grep tells you the Agent's full footprint
    """
    cells: dict[str, set[str]] = {sheet: set() for sheet in ALL_SHEETS}

    # ── C.00 Lead ──────────────────────────────────────────────
    cells[SHEET_LEAD].update(
        [
            LEAD_COMPANY_NAME,
            LEAD_PERIOD_END,
            LEAD_ANALYSIS_DATE,
            LEAD_TE,
            LEAD_SAD,
            LEAD_GAAP,
            LEAD_CURRENCY,
            LEAD_VARIATION_PCT,
            LEAD_RISK_COMPLETENESS,
            LEAD_RISK_EXISTENCE,
            LEAD_RISK_VALUATION,
            LEAD_RISK_RIGHTS,
            LEAD_RISK_PRESENTATION,
        ]
    )
    # GL table rows
    for row in LEAD_GL_ROWS.values():
        for col in LEAD_GL_COLS.values():
            cells[SHEET_LEAD].add(f"{col}{row}")
    # Disclosure table rows
    for row in LEAD_DISCLOSURE_ROWS.values():
        cells[SHEET_LEAD].add(f"{LEAD_DISCLOSURE_CURRENT_COL}{row}")
        cells[SHEET_LEAD].add(f"{LEAD_DISCLOSURE_PRIOR_COL}{row}")
    # Restricted-cash rows: assume up to 10 items
    for row in range(LEAD_RESTRICTED_START_ROW, LEAD_RESTRICTED_START_ROW + 10):
        for col in LEAD_RESTRICTED_COLS.values():
            cells[SHEET_LEAD].add(f"{col}{row}")

    # ── C.02 Bank reconciliations ──────────────────────────────
    cells[SHEET_RECON].update(
        [
            RECON_ACCOUNT_SUBJECT,
            RECON_BANK_NAME,
            RECON_BANK_ACCOUNT,
            RECON_CURRENCY,
            RECON_STATEMENT_DATE,
            RECON_BOOK_BASE,
            RECON_BANK_BASE,
        ]
    )
    # Reconciliation items: book and bank sides
    book_cols = (RECON_BOOK_DESC_COL, RECON_BOOK_AMOUNT_COL, RECON_BOOK_INDEX_COL)
    bank_cols = (RECON_BANK_DESC_COL, RECON_BANK_AMOUNT_COL, RECON_BANK_INDEX_COL)
    for start, end in (RECON_BOOK_PLUS_ROWS, RECON_BOOK_MINUS_ROWS):
        for row in range(start, end + 1):
            for col in book_cols + bank_cols:
                cells[SHEET_RECON].add(f"{col}{row}")

    # ── C.03 Cutoff ────────────────────────────────────────────
    cells[SHEET_CUTOFF].add(CUTOFF_WINDOW)
    for start, end in (CUTOFF_PRE_PERIOD_ROW_RANGE, CUTOFF_POST_PERIOD_ROW_RANGE):
        for row in range(start, end + 1):
            for col in CUTOFF_SAMPLE_COLS.values():
                cells[SHEET_CUTOFF].add(f"{col}{row}")

    return cells


# ──────────────────────────────────────────────────────────────────────────────
# Capacity limits — useful for filler validation
# ──────────────────────────────────────────────────────────────────────────────

MAX_RECON_ITEMS_PER_CATEGORY = 4   # rows 26-29 or 31-34
MAX_CUTOFF_SAMPLES_PER_TABLE = 5   # rows 20-24 or 29-33
MAX_RESTRICTED_ITEMS = 10          # rows 73-82 (heuristic; expand if needed)


__all__ = [
    # Sheet names
    "SHEET_LEAD",
    "SHEET_RECON",
    "SHEET_CUTOFF",
    "ALL_SHEETS",
    # Lead header
    "LEAD_COMPANY_NAME",
    "LEAD_PERIOD_END",
    "LEAD_ANALYSIS_DATE",
    "LEAD_TE",
    "LEAD_SAD",
    "LEAD_GAAP",
    "LEAD_CURRENCY",
    "LEAD_VARIATION_PCT",
    # Lead risk
    "ALLOWED_RISK_LEVELS",
    "LEAD_RISK_COMPLETENESS",
    "LEAD_RISK_EXISTENCE",
    "LEAD_RISK_VALUATION",
    "LEAD_RISK_RIGHTS",
    "LEAD_RISK_PRESENTATION",
    # Lead GL table
    "LEAD_GL_ROWS",
    "LEAD_GL_COLS",
    "LeadGLRow",
    # Lead disclosure
    "LEAD_DISCLOSURE_ROWS",
    "LEAD_DISCLOSURE_CURRENT_COL",
    "LEAD_DISCLOSURE_PRIOR_COL",
    # Lead restricted
    "LEAD_RESTRICTED_START_ROW",
    "LEAD_RESTRICTED_COLS",
    "LeadRestrictedItem",
    # Recon
    "RECON_ACCOUNT_SUBJECT",
    "RECON_BANK_NAME",
    "RECON_BANK_ACCOUNT",
    "RECON_CURRENCY",
    "RECON_STATEMENT_DATE",
    "RECON_BOOK_BASE",
    "RECON_BANK_BASE",
    "RECON_BOOK_PLUS_ROWS",
    "RECON_BOOK_MINUS_ROWS",
    "RECON_BANK_PLUS_ROWS",
    "RECON_BANK_MINUS_ROWS",
    "RECON_BOOK_DESC_COL",
    "RECON_BOOK_AMOUNT_COL",
    "RECON_BOOK_INDEX_COL",
    "RECON_BANK_DESC_COL",
    "RECON_BANK_AMOUNT_COL",
    "RECON_BANK_INDEX_COL",
    "ReconItem",
    # Cutoff
    "CUTOFF_WINDOW",
    "CUTOFF_PRE_PERIOD_ROW_RANGE",
    "CUTOFF_POST_PERIOD_ROW_RANGE",
    "CUTOFF_SAMPLE_COLS",
    "CutoffSample",
    # Allowlist + limits
    "all_writable_cells",
    "MAX_RECON_ITEMS_PER_CATEGORY",
    "MAX_CUTOFF_SAMPLES_PER_TABLE",
    "MAX_RESTRICTED_ITEMS",
]
