# -*- coding: utf-8 -*-
"""
Error injection framework for the C (货币资金) audit scenario.

An ErrorRecipe describes a single intentional error seeded into the
materials. The ground-truth module records every error and the expected
Agent response.

Standard error patterns implemented:

    1. BOOK_STMT_MISMATCH:  book base differs from statement balance
       by an unreconciled amount (omitted reconciling item).
    2. MISSING_CUTOFF:      a reconciling item that straddles period-end
       is NOT included in the cutoff sample table.
    3. UNDISCLOSED_RESTRICTED:  restricted cash is under-disclosed in
       the Lead sheet disclosure table.
    4. PRIOR_YEAR_MISMATCH:  prior-year audited amount is inconsistent
       with the fluctuation pattern (implausible swing).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Error recipe
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ErrorRecipe:
    """One intentional error to inject into generated materials.

    Attributes
    ----------
    name:
        Short unique identifier (e.g. ``"book_stmt_mismatch_acct_1"``).
    severity:
        ``"high"`` | ``"medium"`` | ``"low"``
    sheet:
        Which workpaper sheet is affected (``"C.00 Lead"``, ``"C.02"``, or
        ``"C.03"``).
    description:
        Human-readable explanation of the error.
    injection:
        Callable that modifies the material dicts/DataFrames in-place.
        Receives ``(profile_dict, gl_df, recon_df, cutoff_df)``.
    expected_flag:
        Whether the Agent is expected to flag this as a finding.
    finding_type:
        The audit finding category (e.g. ``"未达账项"``, ``"跨期"``).
    """

    name: str
    severity: str
    sheet: str
    description: str
    injection: Callable
    expected_flag: bool = True
    finding_type: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "severity": self.severity,
            "sheet": self.sheet,
            "description": self.description,
            "expected_flag": self.expected_flag,
            "finding_type": self.finding_type,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Built-in error recipes
# ──────────────────────────────────────────────────────────────────────────────


def _book_stmt_mismatch(profile_dict: dict, gl_df, recon_df, cutoff_df) -> None:
    """Modify the first account's book_balance so it's unreconciled by 30,000."""
    acct = profile_dict["bank_accounts"][0]
    diff = 30_000
    acct["book_balance"] = round(acct["book_balance"] - diff, 2)

    # Also adjust gl_balances to match
    idx = gl_df[gl_df["account_name"].str.contains("银行存款")].index[0]
    gl_df.at[idx, "book_value"] = acct["book_balance"]


def _missing_cutoff(profile_dict, gl_df, recon_df, cutoff_df) -> None:
    """Remove the first cutoff sample and mark the description accordingly."""
    if len(cutoff_df) > 0:
        cutoff_df.drop(index=0, inplace=True)
        cutoff_df.reset_index(drop=True, inplace=True)


def _undisclosed_restricted(profile_dict, gl_df, recon_df, cutoff_df) -> None:
    """Set ``other_funds`` to include a restricted component but note it as empty."""
    # The profile's other_funds is already there; we just make sure the
    # ground truth expects a disclosure. The profile already has the
    # other_funds amount — the "error" is that there's no restricted
    # cash breakdown. We'll mark this in expected_findings only.
    pass


def _prior_year_swing(profile_dict, gl_df, recon_df, cutoff_df) -> None:
    """Set prior_year to an implausible value (10x current year)."""
    idx = gl_df[gl_df["account_name"] == "库存现金"].index[0]
    gl_df.at[idx, "prior_year"] = round(gl_df.at[idx, "book_value"] * 10, 2)


# ──────────────────────────────────────────────────────────────────────────────
# Recipe registry
# ──────────────────────────────────────────────────────────────────────────────

STANDARD_RECIPES: dict[str, list[ErrorRecipe]] = {
    "normal": [],  # No errors — clean scenario
    "book_stmt_mismatch": [
        ErrorRecipe(
            name="book_stmt_mismatch",
            severity="high",
            sheet="C.00 Lead",
            description="银行存款账面余额与银行对账单差异 30,000 元，缺一笔银付企未付调节项",
            injection=_book_stmt_mismatch,
            finding_type="未达账项",
        ),
    ],
    "missing_cutoff": [
        ErrorRecipe(
            name="missing_cutoff_sample",
            severity="medium",
            sheet="C.03",
            description="一笔调节项跨期未纳入截止性测试样本",
            injection=_missing_cutoff,
            finding_type="跨期",
        ),
    ],
    "prior_year_swing": [
        ErrorRecipe(
            name="prior_year_swing",
            severity="medium",
            sheet="C.00 Lead",
            description="库存现金上年审定数异常波动（本年同比+900%）",
            injection=_prior_year_swing,
            finding_type="波动异常",
        ),
    ],
    "full": [  # All errors combined
        ErrorRecipe(
            name="book_stmt_mismatch",
            severity="high",
            sheet="C.00 Lead",
            description="银行存款账面余额与银行对账单差异 30,000 元，缺一笔银付企未付调节项",
            injection=_book_stmt_mismatch,
            finding_type="未达账项",
        ),
        ErrorRecipe(
            name="missing_cutoff_sample",
            severity="medium",
            sheet="C.03",
            description="一笔调节项跨期未纳入截止性测试样本",
            injection=_missing_cutoff,
            finding_type="跨期",
        ),
        ErrorRecipe(
            name="prior_year_swing",
            severity="medium",
            sheet="C.00 Lead",
            description="库存现金上年审定数异常波动（本年同比+900%）",
            injection=_prior_year_swing,
            finding_type="波动异常",
        ),
    ],
}


def get_recipes(scenario: str) -> list[ErrorRecipe]:
    """Return the list of ErrorRecipe for a named scenario."""
    if scenario in STANDARD_RECIPES:
        return STANDARD_RECIPES[scenario]
    raise ValueError(f"Unknown scenario: {scenario!r}. Choose from {list(STANDARD_RECIPES)}")


# ──────────────────────────────────────────────────────────────────────────────
# Injection runner
# ──────────────────────────────────────────────────────────────────────────────


def inject_errors(
    profile: dict,
    gl_df: pd.DataFrame,
    recon_df: pd.DataFrame,
    cutoff_df: pd.DataFrame,
    scenario: str = "normal",
) -> list[dict]:
    """Apply all ErrorRecipes for *scenario* in-place.

    Returns a list of error dicts (for ground truth recording).
    """
    recipes = get_recipes(scenario)
    error_records: list[dict] = []
    for recipe in recipes:
        recipe.injection(profile, gl_df, recon_df, cutoff_df)
        error_records.append(recipe.to_dict())
    return error_records
