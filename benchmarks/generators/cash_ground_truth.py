# -*- coding: utf-8 -*-
"""
Ground-truth writer for C (货币资金) benchmarks.

Each call to ``write_ground_truth()`` produces a JSON file that records:
- The scenario metadata (seed, client, period)
- Every error injected into the materials
- The expected findings the Agent should produce
- The "answer key": what every writable cell in the 3 C-sheets should contain
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .cash_client_profile import ClientProfile
from .cash_error_injector import STANDARD_RECIPES


def _expected_cells(
    profile: ClientProfile,
    gl_df: pd.DataFrame,
    recon_df: pd.DataFrame,
    cutoff_df: pd.DataFrame,
    errors: list[dict],
    scenario: str,
) -> dict[str, dict[str, Any]]:
    """Build the expected cell-value mapping for all 3 C-sheets.

    This is the answer key: what the Agent *should* write if it performs
    the audit correctly (including flagging injected errors).
    """
    cells: dict[str, dict[str, Any]] = {}

    # ── C.00 Lead ────────────────────────────────────────────────────
    lead: dict[str, Any] = {}
    lead["C2"] = profile.company_name
    lead["C3"] = profile.period_end
    lead["C4"] = "2026-01-15"  # Analysis date (proxy)
    lead["C5"] = profile.te
    lead["C6"] = profile.sad
    lead["C7"] = profile.gaap
    lead["C8"] = profile.currency
    lead["C15"] = profile.risk_levels.completeness
    lead["C16"] = profile.risk_levels.existence
    lead["C17"] = profile.risk_levels.valuation
    lead["C18"] = profile.risk_levels.rights
    lead["C19"] = profile.risk_levels.presentation
    lead["C32"] = 0.1

    # GL table
    for _, row in gl_df.iterrows():
        sheet_row = _gl_sheet_row(row["account_name"])
        if sheet_row is None:
            continue
        lead[f"B{sheet_row}"] = row["bookkeeping_code"]
        lead[f"C{sheet_row}"] = row["gl_account_code"]
        lead[f"F{sheet_row}"] = row["book_value"]
        lead[f"G{sheet_row}"] = row["book_adjustment"]
        lead[f"I{sheet_row}"] = row["audit_adjustment"]
        lead[f"K{sheet_row}"] = row["prior_year"]
        lead[f"N{sheet_row}"] = row["notes_tag"]

    cells["C.00 Lead"] = lead

    # ── C.02 Bank reconciliations ────────────────────────────────────
    recon: dict[str, Any] = {}
    recon["C17"] = "银行存款"
    recon["C18"] = profile.bank_accounts[0].bank_name if profile.bank_accounts else ""
    recon["C19"] = profile.bank_accounts[0].account_no if profile.bank_accounts else ""
    recon["C20"] = "CNY"
    recon["C21"] = "2026-01-10"
    recon["C24"] = profile.bank_accounts[0].book_balance if profile.bank_accounts else 0.0
    recon["F24"] = profile.bank_accounts[0].statement_balance if profile.bank_accounts else 0.0

    # Recon items (book side only for display purposes — full fill in future)
    book_plus = recon_df[recon_df["side"] == "book_plus"]
    book_minus = recon_df[recon_df["side"] == "book_minus"]
    for i, (_, item) in enumerate(book_plus.iterrows()):
        if i >= 4:
            break
        row = 26 + i
        recon[f"B{row}"] = item["description"]
        recon[f"C{row}"] = item["amount"]
    for i, (_, item) in enumerate(book_minus.iterrows()):
        if i >= 4:
            break
        row = 31 + i
        recon[f"B{row}"] = item["description"]
        recon[f"C{row}"] = item["amount"]

    cells["C.02 Bank reconciliations"] = recon

    # ── C.03 Cutoff ─────────────────────────────────────────────────
    cutoff: dict[str, Any] = {}
    cutoff["C8"] = "期末前后 5 个工作日"

    pre = cutoff_df.head(5)
    post = cutoff_df.tail(5) if len(cutoff_df) > 5 else pd.DataFrame()

    for i, (_, s) in enumerate(pre.iterrows()):
        row = 20 + i
        _write_cutoff_row(cutoff, row, s)
    for i, (_, s) in enumerate(post.iterrows()):
        row = 29 + i
        _write_cutoff_row(cutoff, row, s)

    cells["C.03 Cutoff"] = cutoff

    return cells


def write_ground_truth(
    scenario: str,
    seed: int,
    profile: ClientProfile,
    gl_df: pd.DataFrame,
    recon_df: pd.DataFrame,
    cutoff_df: pd.DataFrame,
    errors: list[dict],
    output_dir: Path,
) -> Path:
    """Write the ground-truth JSON and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build expected findings from errors
    expected_findings = []
    for err in errors:
        expected_findings.append({
            "finding_type": err.get("finding_type", ""),
            "severity": err.get("severity", "medium"),
            "description": err.get("description", ""),
            "expected_flag": err.get("expected_flag", True),
        })

    cells = _expected_cells(profile, gl_df, recon_df, cutoff_df, errors, scenario)

    doc = {
        "scenario_id": f"cash_{scenario}_{seed:03d}",
        "scenario": scenario,
        "seed": seed,
        "client": profile.company_name,
        "period_end": profile.period_end,
        "errors_injected": errors,
        "expected_findings": expected_findings,
        "writable_cells": cells,
    }

    path = output_dir / f"scenario_{scenario}_{seed:03d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _gl_sheet_row(account_name: str) -> int | None:
    if "库存现金" in account_name:
        return 38
    if "银行存款" in account_name:
        return 39
    if "其他货币资金" in account_name:
        return 40
    return None


def _write_cutoff_row(cells: dict, row: int, s: pd.Series) -> None:
    cells[f"B{row}"] = s.get("sample_id", "")
    cells[f"C{row}"] = s.get("company_name", "")
    cells[f"D{row}"] = s.get("out_bank_name", "")
    cells[f"E{row}"] = s.get("out_bank_account", "")
    cells[f"F{row}"] = s.get("out_time", "")
    cells[f"G{row}"] = s.get("txn_id", "")
    cells[f"H{row}"] = s.get("currency", "")
    cells[f"I{row}"] = s.get("out_amount", 0.0)
    cells[f"J{row}"] = s.get("in_bank_name", "")
    cells[f"K{row}"] = s.get("in_bank_account", "")
    cells[f"L{row}"] = s.get("in_date", "")
    cells[f"M{row}"] = s.get("in_amount", 0.0)
    cells[f"N{row}"] = s.get("is_in_reconciliation", "")
    cells[f"O{row}"] = s.get("notes", "")
