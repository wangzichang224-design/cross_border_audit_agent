# -*- coding: utf-8 -*-
"""
Generate bank reconciliation items and cutoff test samples.

Input:  ``materials/cash/client_profile.json``
Output: ``materials/cash/reconciliation_items.csv``,
        ``materials/cash/cutoff_samples.csv``

Reconciliation items ensure::

    book_base + book_plus - book_minus ≈ statement_base

(practically: the |check| < 0.01 rounding tolerance).  Cutoff samples are
inter-bank transfers that straddle period-end, with P-column check = 0.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .cash_client_profile import ClientProfile

RECON_COLUMNS = [
    "account_row",       # which GL account this belongs to (1-based)
    "side",              # "book_plus" | "book_minus" | "bank_plus" | "bank_minus"
    "description",
    "amount",
    "index_ref",
]

CUTOFF_COLUMNS = [
    "sample_id",
    "company_name",
    "out_bank_name",
    "out_bank_account",
    "out_time",
    "txn_id",
    "currency",
    "out_amount",
    "in_bank_name",
    "in_bank_account",
    "in_date",
    "in_amount",
    "is_in_reconciliation",
    "notes",
]


def generate_reconciliation_items(
    profile: ClientProfile,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate reconciling items that make book ≈ statement for each account.

    For each bank account, we inject 2-4 items per side (book_plus,
    book_minus) such that book + plus - minus roughly equals the
    statement balance.
    """
    rng = np.random.RandomState(seed)
    rows: list[dict] = []

    for idx, acct in enumerate(profile.bank_accounts, start=1):
        diff = acct.statement_balance - acct.book_balance

        # Distribute the diff across plus/minus items
        # If diff > 0: more book-plus items (银收企未收)
        # If diff < 0: more book-minus items (银付企未付)
        n_plus = int(rng.choice([2, 3, 4], p=[0.3, 0.5, 0.2]))
        n_minus = int(rng.choice([2, 3, 4], p=[0.3, 0.5, 0.2]))

        # We want: book + plus_sum - minus_sum ≈ stmt
        # so: plus_sum - minus_sum = diff
        # We'll set up a random split
        if diff >= 0:
            plus_total = abs(diff) * rng.uniform(1.5, 3.0)
            minus_total = plus_total - abs(diff)
        else:
            minus_total = abs(diff) * rng.uniform(1.5, 3.0)
            plus_total = minus_total - abs(diff)

        plus_amounts = _split_positive(plus_total, n_plus, rng)
        minus_amounts = _split_positive(minus_total, n_minus, rng)

        desc_pool_plus = ["银行已收企业未收-销售回款", "银行已收企业未收-利息收入", "银行已收企业未收-汇兑收益", "银行已收企业未收-理财到期"]
        desc_pool_minus = ["银行已付企业未付-手续费", "银行已付企业未付-代扣税款", "银行已付企业未付-汇兑损失", "银行已付企业未付-对外支付"]

        for amt in plus_amounts:
            rows.append({
                "account_row": idx,
                "side": "book_plus",
                "description": rng.choice(desc_pool_plus),
                "amount": round(amt, 2),
                "index_ref": "",
            })
        for amt in minus_amounts:
            rows.append({
                "account_row": idx,
                "side": "book_minus",
                "description": rng.choice(desc_pool_minus),
                "amount": round(amt, 2),
                "index_ref": "",
            })

    return pd.DataFrame(rows, columns=RECON_COLUMNS)


def generate_cutoff_samples(
    profile: ClientProfile,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate 5 pre-period + 5 post-period inter-bank transfer samples.

    Each sample has ``out_amount = -in_amount`` so that the P-column
    check formula (``=M + I``) equals 0.
    """
    rng = np.random.RandomState(seed + 100)
    rows: list[dict] = []

    accounts = [a for a in profile.bank_accounts]
    if len(accounts) < 2:
        # Duplicate first account for a second side
        accounts.append(accounts[0])

    company = profile.company_name
    base_amounts = rng.uniform(10000, 500000, size=10)

    for i in range(10):
        period = "pre" if i < 5 else "post"
        from_acct = accounts[i % len(accounts)]
        to_acct = accounts[(i + 1) % len(accounts)]
        amt = round(float(base_amounts[i]), 2)

        day_offset = rng.randint(-5, -1) if period == "pre" else rng.randint(1, 5)
        out_date = f"2025-12-{31 + day_offset:02d}" if day_offset < 0 else f"2026-01-{day_offset:02d}"
        in_date = f"2026-01-{abs(day_offset) + 1:02d}" if day_offset < 0 else f"2025-12-{31 - abs(day_offset):02d}"

        rows.append({
            "sample_id": f"S{i + 1}",
            "company_name": company,
            "out_bank_name": from_acct.bank_name,
            "out_bank_account": from_acct.account_no,
            "out_time": out_date,
            "txn_id": f"TXN-{2025000 + i}",
            "currency": "CNY",
            "out_amount": -amt,  # Negative = payment out
            "in_bank_name": to_acct.bank_name,
            "in_bank_account": to_acct.account_no,
            "in_date": in_date,
            "in_amount": amt,  # Positive = receipt in
            "is_in_reconciliation": "是" if i % 3 == 0 else "否",
            "notes": "",
        })

    return pd.DataFrame(rows, columns=CUTOFF_COLUMNS)


def save_transactions(
    recon_df: pd.DataFrame,
    cutoff_df: pd.DataFrame,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write both CSVs to *output_dir* and return ``(recon_path, cutoff_path)``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    recon_path = output_dir / "reconciliation_items.csv"
    cutoff_path = output_dir / "cutoff_samples.csv"
    recon_df.to_csv(recon_path, index=False, encoding="utf-8-sig")
    cutoff_df.to_csv(cutoff_path, index=False, encoding="utf-8-sig")
    return recon_path, cutoff_path


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _split_positive(total: float, n: int, rng: np.random.RandomState) -> list[float]:
    """Split *total* into *n* positive amounts that sum to *total*.

    Clamps to 0 if total is negative.
    """
    total = max(total, 0.0)
    if n <= 0:
        return []
    if n == 1:
        return [total]
    ratios = rng.dirichlet(np.ones(n))
    amounts = [round(total * r, 2) for r in ratios[:-1]]
    amounts.append(round(total - sum(amounts), 2))
    return amounts
