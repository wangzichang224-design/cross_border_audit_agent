# -*- coding: utf-8 -*-
"""
Generate GL balance data for C.00 Lead sheet (table rows 38-40).

Input:  ``materials/cash/client_profile.json``
Output: ``materials/cash/gl_balances.csv``

Three fixed rows: 库存现金, 银行存款 (per account), 其他货币资金.
Prior-year amounts are generated at 85-115% of current to create realistic
fluctuation for the 变动% formula column.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .cash_client_profile import ClientProfile, generate_profile, load_profile, save_profile

GL_COLUMNS = [
    "voucher_id",
    "account_name",
    "bookkeeping_code",
    "gl_account_code",
    "index_ref",
    "book_value",
    "book_adjustment",
    "audit_adjustment",
    "prior_year",
    "notes_tag",
]


def generate_gl_ledger(
    profile: ClientProfile,
    seed: int = 42,
) -> pd.DataFrame:
    """Build the GL balance table from a client profile.

    Returns a DataFrame with one row per GL account, mirroring
    ``LeadGLRow`` from ``benchmarks/agent/cell_map.py``.
    """
    rng = np.random.RandomState(seed)
    rows = []

    # ── Row 1: 库存现金 ──────────────────────────────────────────────
    prior = round(profile.cash_on_hand * rng.uniform(0.88, 1.12), 2)
    rows.append({
        "voucher_id": "GL-001",
        "account_name": "库存现金",
        "bookkeeping_code": "01",
        "gl_account_code": "1001",
        "index_ref": "",
        "book_value": profile.cash_on_hand,
        "book_adjustment": 0.0,
        "audit_adjustment": 0.0,
        "prior_year": prior,
        "notes_tag": "[A]",
    })

    # ── Row 2: 银行存款 (one row per account, concatenated name) ─────
    for i, acct in enumerate(profile.bank_accounts):
        prior = round(acct.book_balance * rng.uniform(0.85, 1.15), 2)
        suffix = "USD" if acct.currency == "USD" else "CNY"
        rows.append({
            "voucher_id": f"GL-00{2 + i}",
            "account_name": f"银行存款-{suffix}",
            "bookkeeping_code": f"0{2 + i}",
            "gl_account_code": "1002",
            "index_ref": "",
            "book_value": acct.book_balance,
            "book_adjustment": 0.0,
            "audit_adjustment": 0.0,
            "prior_year": prior,
            "notes_tag": "[B]",
        })

    # ── Row 3: 其他货币资金 ──────────────────────────────────────────
    prior = round(profile.other_funds * rng.uniform(0.85, 1.15), 2)
    rows.append({
        "voucher_id": f"GL-00{2 + len(profile.bank_accounts) + 1}" if len(profile.bank_accounts) > 1 else "GL-004",
        "account_name": "其他货币资金",
        "bookkeeping_code": "04",
        "gl_account_code": "1015",
        "index_ref": "",
        "book_value": profile.other_funds,
        "book_adjustment": 0.0,
        "audit_adjustment": 0.0,
        "prior_year": prior,
        "notes_tag": "[C]",
    })

    return pd.DataFrame(rows, columns=GL_COLUMNS)


def save_gl_ledger(df: pd.DataFrame, output_dir: Path) -> Path:
    """Write GL ledger CSV to *output_dir* and return the path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "gl_balances.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path
