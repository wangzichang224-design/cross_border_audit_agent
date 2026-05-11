# -*- coding: utf-8 -*-
"""Cell map for the clean C cash workpaper template.

The legacy ``cell_map.py`` targets the original C SWP workbook. This module
targets the rebuilt neutral workbook generated under ``outputs/clean_templates``.
It intentionally keeps sheet names and addresses explicit so the cash filler can
dispatch by template layout without guessing.
"""

from __future__ import annotations

from typing import Mapping


SHEET_SUMMARY = "汇总"
SHEET_LEAD = "货币资金主表"
SHEET_BKD = "货币资金明细"
SHEET_RECON = "银行余额调节"
SHEET_CUTOFF = "截止性测试"

ALL_SHEETS = (SHEET_SUMMARY, SHEET_LEAD, SHEET_BKD, SHEET_RECON, SHEET_CUTOFF)


# C.00 Lead
LEAD_COMPANY_NAME = "B3"
LEAD_PERIOD_END = "B4"
LEAD_ANALYSIS_DATE = "B5"
LEAD_TE = "B6"
LEAD_SAD = "B7"
LEAD_GAAP = "B8"
LEAD_AUDIT_STANDARD = "B9"
LEAD_CURRENCY = "B10"
LEAD_VARIATION_PCT = "B23"

ALLOWED_RISK_LEVELS = ("极低", "低", "中等", "高", "不适用")
RISK_LEVEL_TRANSLATION: Mapping[str, str] = {
    "Minimal": "极低",
    "Low": "低",
    "Moderate": "中等",
    "High": "高",
    "Significant": "高",
    "N/A": "不适用",
    "极低": "极低",
    "低": "低",
    "中等": "中等",
    "高": "高",
    "不适用": "不适用",
}

LEAD_RISK_COMPLETENESS = "B15"
LEAD_RISK_EXISTENCE = "B16"
LEAD_RISK_VALUATION = "B17"
LEAD_RISK_RIGHTS = "B18"
LEAD_RISK_PRESENTATION = "B19"

LEAD_RISK_CELLS = (
    LEAD_RISK_COMPLETENESS,
    LEAD_RISK_EXISTENCE,
    LEAD_RISK_VALUATION,
    LEAD_RISK_RIGHTS,
    LEAD_RISK_PRESENTATION,
)

LEAD_GL_ROWS: Mapping[str, int] = {
    "库存现金": 29,
    "银行存款": 30,
    "其他货币资金": 31,
}

LEAD_GL_COLS: Mapping[str, str] = {
    "bookkeeping_code": "A",
    "gl_account_code": "B",
    "account_name": "C",
    "index_ref": "D",
    "book_value_unaudited": "E",
    "book_adjustment": "F",
    "audit_adjustment": "H",
    "prior_year_audited": "J",
    "notes_tag": "N",
}

LEAD_RESTRICTED_CURRENT = "B45"
LEAD_RESTRICTED_PRIOR = "C45"
LEAD_RESTRICTED_NOTE = "F45"


# C.00 BKD
BKD_START_ROW = 12
BKD_MAX_ROWS = 100

BKD_COLS: Mapping[str, str] = {
    "company_name": "B",
    "account_name": "C",
    "bank_name": "D",
    "bank_account": "E",
    "currency": "F",
    "period_end_balance_fx": "G",
    "period_end_balance_local": "H",
    "account_usage": "I",
    "confirmation_required": "J",
    "alternative_procedure": "K",
    "notes": "L",
}


# C.02 银行余额调节
RECON_ACCOUNT_SUBJECT = "B10"
RECON_INDEX_REF = "D10"
RECON_STATEMENT_DATE = "F10"
RECON_BANK_NAME = "B11"
RECON_BANK_ACCOUNT = "D11"
RECON_CURRENCY = "F11"
RECON_ACCOUNT_NATURE = "B12"
RECON_HAS_ITEMS = "D12"
RECON_SOURCE = "F12"
RECON_SELECTION_RATIONALE = "B5"
RECON_CONCLUSION = "B6"

RECON_BOOK_BASE = "B19"
RECON_BANK_BASE = "E19"

RECON_BOOK_PLUS_ROWS = (21, 25)
RECON_BOOK_MINUS_ROWS = (27, 31)
RECON_BANK_PLUS_ROWS = (21, 25)
RECON_BANK_MINUS_ROWS = (27, 31)

RECON_BOOK_DESC_COL = "A"
RECON_BOOK_AMOUNT_COL = "B"
RECON_BOOK_INDEX_COL = "C"
RECON_BANK_DESC_COL = "D"
RECON_BANK_AMOUNT_COL = "E"
RECON_BANK_INDEX_COL = "F"

MAX_RECON_ITEMS_PER_CATEGORY = 5


# C.03 截止性测试
CUTOFF_WINDOW = "B4"
CUTOFF_WORKDAYS = "B5"
CUTOFF_REASON = "B6"
CUTOFF_CONCLUSION = "B7"

CUTOFF_PRE_PERIOD_ROW_RANGE = (13, 32)
CUTOFF_POST_PERIOD_ROW_RANGE = (38, 57)
MAX_CUTOFF_SAMPLES_PER_TABLE = 20

CUTOFF_SAMPLE_COLS: Mapping[str, str] = {
    "sample_id": "A",
    "company_name": "B",
    "out_bank_name": "C",
    "out_bank_account": "D",
    "out_time": "E",
    "txn_id": "F",
    "currency": "G",
    "out_amount": "H",
    "in_bank_name": "I",
    "in_bank_account": "J",
    "in_date": "K",
    "in_amount": "L",
    "is_in_reconciliation": "M",
    "accounting_ok": "N",
    "notes": "O",
}


def all_writable_cells() -> dict[str, set[str]]:
    cells: dict[str, set[str]] = {sheet: set() for sheet in ALL_SHEETS}

    cells[SHEET_LEAD].update(
        {
            LEAD_COMPANY_NAME,
            LEAD_PERIOD_END,
            LEAD_ANALYSIS_DATE,
            LEAD_TE,
            LEAD_SAD,
            LEAD_GAAP,
            LEAD_AUDIT_STANDARD,
            LEAD_CURRENCY,
            LEAD_VARIATION_PCT,
            *LEAD_RISK_CELLS,
            LEAD_RESTRICTED_CURRENT,
            LEAD_RESTRICTED_PRIOR,
            LEAD_RESTRICTED_NOTE,
        }
    )
    for row in LEAD_GL_ROWS.values():
        for col in LEAD_GL_COLS.values():
            cells[SHEET_LEAD].add(f"{col}{row}")

    for row in range(BKD_START_ROW, BKD_START_ROW + BKD_MAX_ROWS):
        for col in BKD_COLS.values():
            cells[SHEET_BKD].add(f"{col}{row}")

    cells[SHEET_RECON].update(
        {
            RECON_ACCOUNT_SUBJECT,
            RECON_INDEX_REF,
            RECON_STATEMENT_DATE,
            RECON_BANK_NAME,
            RECON_BANK_ACCOUNT,
            RECON_CURRENCY,
            RECON_ACCOUNT_NATURE,
            RECON_HAS_ITEMS,
            RECON_SOURCE,
            RECON_SELECTION_RATIONALE,
            RECON_CONCLUSION,
            RECON_BOOK_BASE,
            RECON_BANK_BASE,
        }
    )
    book_cols = (RECON_BOOK_DESC_COL, RECON_BOOK_AMOUNT_COL, RECON_BOOK_INDEX_COL)
    bank_cols = (RECON_BANK_DESC_COL, RECON_BANK_AMOUNT_COL, RECON_BANK_INDEX_COL)
    for start, end in (RECON_BOOK_PLUS_ROWS, RECON_BOOK_MINUS_ROWS):
        for row in range(start, end + 1):
            for col in book_cols:
                cells[SHEET_RECON].add(f"{col}{row}")
    for start, end in (RECON_BANK_PLUS_ROWS, RECON_BANK_MINUS_ROWS):
        for row in range(start, end + 1):
            for col in bank_cols:
                cells[SHEET_RECON].add(f"{col}{row}")

    cells[SHEET_CUTOFF].update({CUTOFF_WINDOW, CUTOFF_WORKDAYS, CUTOFF_REASON, CUTOFF_CONCLUSION})
    for start, end in (CUTOFF_PRE_PERIOD_ROW_RANGE, CUTOFF_POST_PERIOD_ROW_RANGE):
        for row in range(start, end + 1):
            for col in CUTOFF_SAMPLE_COLS.values():
                cells[SHEET_CUTOFF].add(f"{col}{row}")

    return cells


__all__ = [
    "SHEET_SUMMARY",
    "SHEET_LEAD",
    "SHEET_BKD",
    "SHEET_RECON",
    "SHEET_CUTOFF",
    "ALL_SHEETS",
    "LEAD_COMPANY_NAME",
    "LEAD_PERIOD_END",
    "LEAD_ANALYSIS_DATE",
    "LEAD_TE",
    "LEAD_SAD",
    "LEAD_GAAP",
    "LEAD_AUDIT_STANDARD",
    "LEAD_CURRENCY",
    "LEAD_VARIATION_PCT",
    "ALLOWED_RISK_LEVELS",
    "RISK_LEVEL_TRANSLATION",
    "LEAD_RISK_CELLS",
    "LEAD_GL_ROWS",
    "LEAD_GL_COLS",
    "LEAD_RESTRICTED_CURRENT",
    "LEAD_RESTRICTED_PRIOR",
    "LEAD_RESTRICTED_NOTE",
    "BKD_START_ROW",
    "BKD_MAX_ROWS",
    "BKD_COLS",
    "RECON_ACCOUNT_SUBJECT",
    "RECON_INDEX_REF",
    "RECON_STATEMENT_DATE",
    "RECON_BANK_NAME",
    "RECON_BANK_ACCOUNT",
    "RECON_CURRENCY",
    "RECON_ACCOUNT_NATURE",
    "RECON_HAS_ITEMS",
    "RECON_SOURCE",
    "RECON_SELECTION_RATIONALE",
    "RECON_CONCLUSION",
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
    "MAX_RECON_ITEMS_PER_CATEGORY",
    "CUTOFF_WINDOW",
    "CUTOFF_WORKDAYS",
    "CUTOFF_REASON",
    "CUTOFF_CONCLUSION",
    "CUTOFF_PRE_PERIOD_ROW_RANGE",
    "CUTOFF_POST_PERIOD_ROW_RANGE",
    "CUTOFF_SAMPLE_COLS",
    "MAX_CUTOFF_SAMPLES_PER_TABLE",
    "all_writable_cells",
]
