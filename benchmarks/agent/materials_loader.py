# -*- coding: utf-8 -*-
"""
Phase 1 materials loader: CSV → typed dataclasses.

Layout of a Phase 1 materials directory
---------------------------------------
::

    benchmarks/materials/case_001_minimal/
    ├── case_metadata.json     # client name, period_end, TE, SAD, GAAP, currency
    ├── bank_statement.csv     # one row per bank txn (all accounts merged)
    ├── gl_bank.csv            # one row per GL entry hitting cash accounts
    ├── confirmations.csv      # one row per bank confirmation reply
    ├── period_summary.csv     # finance department's "期末余额表" (one row per account)
    └── reconciliation.csv     # pre-computed reconciling items (Phase 1 shortcut)

Why CSV in Phase 1 (and not PDF)?
---------------------------------
Phase 1 is about **proving the cell-writing logic works end-to-end**. PDF
parsing adds its own failure modes (table extraction, OCR, layout drift)
that would mask cell-map bugs. CSV gives us deterministic, debuggable
inputs. Phase 3 replaces this whole loader with PDF parsers behind the
same dataclass interface, and the rest of the Agent (context builder,
cell writer) stays unchanged.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable


# ──────────────────────────────────────────────────────────────────────────────
# File names (constants so callers can use them, e.g. for fixture generation)
# ──────────────────────────────────────────────────────────────────────────────

FILE_CASE_METADATA = "case_metadata.json"
FILE_BANK_STATEMENT = "bank_statement.csv"
FILE_GL_BANK = "gl_bank.csv"
FILE_CONFIRMATIONS = "confirmations.csv"
FILE_PERIOD_SUMMARY = "period_summary.csv"
FILE_RECONCILIATION = "reconciliation.csv"


# ──────────────────────────────────────────────────────────────────────────────
# Row dataclasses (one per CSV)
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CaseMetadata:
    """Top-level case info, parsed from case_metadata.json.

    All fields are required EXCEPT variation_pct, which has an audit-default
    of 10% if not specified.
    """

    case_id: str
    client_name: str
    period_end: date
    analysis_date: date
    te: float        # 可容忍误差 Tolerable Error
    sad: float       # 名义金额 Summary of Audit Differences threshold
    gaap: str        # 适用会计准则 (e.g. "企业会计准则")
    currency: str    # 记账本位币 (e.g. "CNY")
    variation_pct: float = 0.1


@dataclass(frozen=True)
class BankStatementRow:
    """One row from a bank statement (aggregated across accounts).

    `debit` = outflow / disbursement (从银行账户流出)
    `credit` = inflow / receipt (流入银行账户)
    `balance` = running balance after this txn
    """

    date: date
    bank_name: str
    bank_account: str
    currency: str
    debit: float
    credit: float
    balance: float
    description: str
    counterparty: str = ""
    txn_id: str = ""


@dataclass(frozen=True)
class GLBankRow:
    """One row of GL detail for any cash-side account.

    Note: Chinese accounting convention — '借' = debit, '贷' = credit.
    For a cash account, debit means **cash flowing IN** (e.g. customer
    payment recorded as 借:银行存款 贷:应收账款).
    """

    date: date
    voucher_id: str
    account_code: str     # 总账科目编码 (e.g. '1001', '1002')
    account_name: str     # 库存现金 / 银行存款 / 其他货币资金
    debit: float          # 借方金额
    credit: float         # 贷方金额
    summary: str
    counterparty: str = ""


@dataclass(frozen=True)
class ConfirmationRow:
    """One bank confirmation reply.

    `restricted_amount` and `restriction_nature` come from the confirmation
    footnote (e.g. "其中质押冻结 200,000 元用于银行承兑").
    """

    bank_name: str
    bank_account: str
    currency: str
    confirmed_balance: float
    restricted_amount: float = 0.0
    restriction_nature: str = ""   # 质押 / 冻结 / 专款专用 / 保证金 ...
    confirmation_date: date | None = None
    confirmation_index: str = ""   # 索引号 (e.g. "C.01 第3行")


@dataclass(frozen=True)
class PeriodSummaryRow:
    """One row from the finance department's period-end summary table
    ("期末余额表"). This is the client's representation and may contain
    classification errors (e.g. 受限资金 listed as 非受限) — those are
    what the Agent ultimately catches when comparing against confirmations.
    """

    account_name: str                  # 库存现金/银行存款/其他货币资金
    bank_name: str
    bank_account: str
    currency: str
    period_end_balance_local: float    # 折算后本位币金额
    period_end_balance_fx: float       # 原币金额
    fx_rate: float = 1.0               # 折算汇率 (本位币 / 原币)
    is_restricted: bool = False        # 客户标注的是否受限
    restriction_note: str = ""         # 客户标注的受限原因
    prior_year_balance: float = 0.0    # 上期末审定数 (本位币)


@dataclass(frozen=True)
class ReconciliationItem:
    """One pre-computed reconciling item (Phase 1 shortcut).

    In Phase 3 the Agent will compute these itself by diffing bank vs GL.
    For Phase 1 we accept them as pre-given so we can isolate cell-writing.

    Categories must be one of:
      'book_plus'   — 加：银收企未收 (book side, addition)
      'book_minus'  — 减：银付企未付 (book side, subtraction)
      'bank_plus'   — 加：企收银未收 (bank side, addition)
      'bank_minus'  — 减：企付银未付 (bank side, subtraction)
    """

    category: str
    description: str
    amount: float    # Always positive; sign comes from category
    index: str = ""  # e.g. 'GL #487' or 'Bank stmt p.4 r12'


VALID_RECON_CATEGORIES = ("book_plus", "book_minus", "bank_plus", "bank_minus")


# ──────────────────────────────────────────────────────────────────────────────
# Bundle
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CaseMaterials:
    """Everything the Agent reads for one case. All collections are
    immutable tuples once loaded.
    """

    meta: CaseMetadata
    bank_statements: tuple[BankStatementRow, ...]
    gl_bank: tuple[GLBankRow, ...]
    confirmations: tuple[ConfirmationRow, ...]
    period_summary: tuple[PeriodSummaryRow, ...]
    reconciliation_items: tuple[ReconciliationItem, ...]

    def by_bank_account(self) -> set[str]:
        """All distinct bank accounts mentioned in confirmations + summary."""
        accts: set[str] = set()
        accts.update(c.bank_account for c in self.confirmations)
        accts.update(p.bank_account for p in self.period_summary)
        return accts


# ──────────────────────────────────────────────────────────────────────────────
# Parsers
# ──────────────────────────────────────────────────────────────────────────────


def _parse_date(value: str | None) -> date:
    """Parse YYYY-MM-DD strictly. Raise on garbage so fixtures fail loud."""
    if value is None or not str(value).strip():
        raise ValueError("empty date value")
    s = str(value).strip()
    # Accept either YYYY-MM-DD or YYYY/MM/DD
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date format: {s!r}")


def _parse_float(value: str | None, default: float = 0.0) -> float:
    """Parse a float; empty string → default; non-numeric → raise."""
    if value is None:
        return default
    s = str(value).strip().replace(",", "")
    if not s:
        return default
    return float(s)


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    s = str(value).strip().lower()
    if not s:
        return default
    return s in {"1", "true", "yes", "y", "是", "受限"}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV with BOM tolerance. Returns list of dicts.

    Empty/missing files raise FileNotFoundError, which the caller can
    interpret (e.g. allow optional reconciliation.csv to be absent).
    """
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


# Field-by-field parsers


def parse_case_metadata(path: Path) -> CaseMetadata:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return CaseMetadata(
        case_id=str(data["case_id"]),
        client_name=str(data["client_name"]),
        period_end=_parse_date(data["period_end"]),
        analysis_date=_parse_date(data["analysis_date"]),
        te=float(data["te"]),
        sad=float(data["sad"]),
        gaap=str(data["gaap"]),
        currency=str(data["currency"]),
        variation_pct=float(data.get("variation_pct", 0.1)),
    )


def parse_bank_statement(path: Path) -> list[BankStatementRow]:
    out: list[BankStatementRow] = []
    for row in _read_csv_rows(path):
        out.append(
            BankStatementRow(
                date=_parse_date(row["date"]),
                bank_name=row["bank_name"].strip(),
                bank_account=row["bank_account"].strip(),
                currency=row["currency"].strip(),
                debit=_parse_float(row.get("debit")),
                credit=_parse_float(row.get("credit")),
                balance=_parse_float(row.get("balance")),
                description=row.get("description", "").strip(),
                counterparty=row.get("counterparty", "").strip(),
                txn_id=row.get("txn_id", "").strip(),
            )
        )
    return out


def parse_gl_bank(path: Path) -> list[GLBankRow]:
    out: list[GLBankRow] = []
    for row in _read_csv_rows(path):
        out.append(
            GLBankRow(
                date=_parse_date(row["date"]),
                voucher_id=row["voucher_id"].strip(),
                account_code=row["account_code"].strip(),
                account_name=row["account_name"].strip(),
                debit=_parse_float(row.get("debit")),
                credit=_parse_float(row.get("credit")),
                summary=row.get("summary", "").strip(),
                counterparty=row.get("counterparty", "").strip(),
            )
        )
    return out


def parse_confirmations(path: Path) -> list[ConfirmationRow]:
    out: list[ConfirmationRow] = []
    for row in _read_csv_rows(path):
        conf_date_str = row.get("confirmation_date", "").strip()
        out.append(
            ConfirmationRow(
                bank_name=row["bank_name"].strip(),
                bank_account=row["bank_account"].strip(),
                currency=row["currency"].strip(),
                confirmed_balance=_parse_float(row.get("confirmed_balance")),
                restricted_amount=_parse_float(row.get("restricted_amount")),
                restriction_nature=row.get("restriction_nature", "").strip(),
                confirmation_date=_parse_date(conf_date_str) if conf_date_str else None,
                confirmation_index=row.get("confirmation_index", "").strip(),
            )
        )
    return out


def parse_period_summary(path: Path) -> list[PeriodSummaryRow]:
    out: list[PeriodSummaryRow] = []
    for row in _read_csv_rows(path):
        out.append(
            PeriodSummaryRow(
                account_name=row["account_name"].strip(),
                bank_name=row.get("bank_name", "").strip(),
                bank_account=row.get("bank_account", "").strip(),
                currency=row.get("currency", "").strip(),
                period_end_balance_local=_parse_float(row.get("period_end_balance_local")),
                period_end_balance_fx=_parse_float(row.get("period_end_balance_fx")),
                fx_rate=_parse_float(row.get("fx_rate"), default=1.0),
                is_restricted=_parse_bool(row.get("is_restricted")),
                restriction_note=row.get("restriction_note", "").strip(),
                prior_year_balance=_parse_float(row.get("prior_year_balance")),
            )
        )
    return out


def parse_reconciliation(path: Path) -> list[ReconciliationItem]:
    out: list[ReconciliationItem] = []
    for row in _read_csv_rows(path):
        cat = row["category"].strip()
        if cat not in VALID_RECON_CATEGORIES:
            raise ValueError(
                f"invalid reconciliation category {cat!r} in {path}; "
                f"must be one of {VALID_RECON_CATEGORIES}"
            )
        out.append(
            ReconciliationItem(
                category=cat,
                description=row["description"].strip(),
                amount=_parse_float(row.get("amount")),
                index=row.get("index", "").strip(),
            )
        )
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Top-level loader
# ──────────────────────────────────────────────────────────────────────────────


def load_case_materials(materials_dir: Path | str) -> CaseMaterials:
    """Load all materials for one case from its directory.

    `reconciliation.csv` is optional — if missing, returns an empty tuple.
    All other files are required; a missing one is treated as a fixture
    error and raised loud.
    """
    materials_dir = Path(materials_dir)
    if not materials_dir.is_dir():
        raise NotADirectoryError(materials_dir)

    meta = parse_case_metadata(materials_dir / FILE_CASE_METADATA)
    bank = parse_bank_statement(materials_dir / FILE_BANK_STATEMENT)
    gl = parse_gl_bank(materials_dir / FILE_GL_BANK)
    confirmations = parse_confirmations(materials_dir / FILE_CONFIRMATIONS)
    period = parse_period_summary(materials_dir / FILE_PERIOD_SUMMARY)
    try:
        recon = parse_reconciliation(materials_dir / FILE_RECONCILIATION)
    except FileNotFoundError:
        recon = []

    return CaseMaterials(
        meta=meta,
        bank_statements=tuple(bank),
        gl_bank=tuple(gl),
        confirmations=tuple(confirmations),
        period_summary=tuple(period),
        reconciliation_items=tuple(recon),
    )


__all__ = [
    # File name constants
    "FILE_CASE_METADATA",
    "FILE_BANK_STATEMENT",
    "FILE_GL_BANK",
    "FILE_CONFIRMATIONS",
    "FILE_PERIOD_SUMMARY",
    "FILE_RECONCILIATION",
    # Row types
    "CaseMetadata",
    "BankStatementRow",
    "GLBankRow",
    "ConfirmationRow",
    "PeriodSummaryRow",
    "ReconciliationItem",
    "VALID_RECON_CATEGORIES",
    # Bundle + loader
    "CaseMaterials",
    "load_case_materials",
    # Individual parsers (exposed for tests / fixture generation)
    "parse_case_metadata",
    "parse_bank_statement",
    "parse_gl_bank",
    "parse_confirmations",
    "parse_period_summary",
    "parse_reconciliation",
]
