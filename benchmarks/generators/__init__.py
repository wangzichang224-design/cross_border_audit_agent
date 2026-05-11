# -*- coding: utf-8 -*-
"""
Material generators for the C (货币资金) audit workpaper.

``generate_all()`` produces a complete scenario from scratch:

    >>> from benchmarks.generators import generate_all
    >>> gt_path = generate_all(seed=42, scenario="book_stmt_mismatch")
    >>> print(gt_path)
    benchmarks/ground_truth/cash/scenario_book_stmt_mismatch_042.json
"""

from __future__ import annotations

from pathlib import Path

from .cash_client_profile import generate_profile, save_profile
from .cash_gl_ledger import generate_gl_ledger, save_gl_ledger
from .cash_transactions import (
    generate_cutoff_samples,
    generate_reconciliation_items,
    save_transactions,
)
from .cash_documents import generate_journal, generate_bank_confirmations
from .cash_trial_balance import generate_trial_balance
from .cash_error_injector import inject_errors
from .cash_ground_truth import write_ground_truth

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATERIALS_DIR = PROJECT_ROOT / "benchmarks" / "materials" / "cash"
DEFAULT_GROUND_TRUTH_DIR = PROJECT_ROOT / "benchmarks" / "ground_truth" / "cash"


def generate_all(
    seed: int = 42,
    scenario: str = "normal",
    materials_dir: str | Path = "",
    ground_truth_dir: str | Path = "",
) -> Path:
    """Generate a complete C (cash) scenario.

    Parameters
    ----------
    seed:
        Random seed for deterministic generation.
    scenario:
        Error scenario name. Choose from:
        ``"normal"`` (clean), ``"book_stmt_mismatch"``, ``"missing_cutoff"``,
        ``"prior_year_swing"``, ``"full"`` (all errors combined).
    materials_dir:
        Output directory for generated materials. Defaults to
        ``benchmarks/materials/cash/``.
    ground_truth_dir:
        Output directory for the ground-truth JSON. Defaults to
        ``benchmarks/ground_truth/cash/``.

    Returns
    -------
    Path
        Path to the ground-truth JSON file.
    """
    mat_dir = Path(materials_dir) if materials_dir else DEFAULT_MATERIALS_DIR
    gt_dir = Path(ground_truth_dir) if ground_truth_dir else DEFAULT_GROUND_TRUTH_DIR

    # Step 1: Generate the client profile
    profile = generate_profile(seed=seed)
    save_profile(profile, mat_dir / "client_profile.json")

    # Step 2: Generate GL ledger
    gl_df = generate_gl_ledger(profile, seed=seed)
    save_gl_ledger(gl_df, mat_dir)

    # Step 3: Generate reconciliation items and cutoff samples
    recon_df = generate_reconciliation_items(profile, seed=seed)
    cutoff_df = generate_cutoff_samples(profile, seed=seed)
    save_transactions(recon_df, cutoff_df, mat_dir)

    # Step 4: Generate Excel journal + trial balance (before error injection)
    generate_journal(profile, mat_dir / "银行存款日记账.xlsx", seed=seed)
    generate_trial_balance(profile, mat_dir / "试算平衡表.xlsx", seed=seed)

    # Step 5: Inject errors (in-place on the DataFrames and profile)
    profile_dict = profile.to_dict()
    errors = inject_errors(profile_dict, gl_df, recon_df, cutoff_df, scenario=scenario)

    # Re-save the modified materials (with errors injected)
    import json as _json
    with open(mat_dir / "client_profile.json", "w", encoding="utf-8") as _f:
        _json.dump(profile_dict, _f, ensure_ascii=False, indent=2)
    gl_df.to_csv(mat_dir / "gl_balances.csv", index=False, encoding="utf-8-sig")
    recon_df.to_csv(mat_dir / "reconciliation_items.csv", index=False, encoding="utf-8-sig")
    cutoff_df.to_csv(mat_dir / "cutoff_samples.csv", index=False, encoding="utf-8-sig")

    # Step 6: Generate bank confirmations AFTER error injection so balances match
    # Build a temporary profile dict so confirmations see the post-error book_balances
    from .cash_client_profile import ClientProfile, BankAccount, RiskLevels
    error_profile = ClientProfile(
        company_name=profile_dict["company_name"],
        period_end=profile_dict["period_end"],
        currency=profile_dict["currency"],
        gaap=profile_dict["gaap"],
        te=profile_dict["te"],
        sad=profile_dict["sad"],
        cash_on_hand=profile_dict["cash_on_hand"],
        other_funds=profile_dict["other_funds"],
        bank_accounts=[BankAccount(**ba) for ba in profile_dict["bank_accounts"]],
        risk_levels=RiskLevels(**profile_dict["risk_levels"]),
    )
    generate_bank_confirmations(error_profile, mat_dir / "bank_confirmations", seed=seed)

    # Step 7: Write ground truth
    gt_path = write_ground_truth(
        scenario=scenario,
        seed=seed,
        profile=profile,
        gl_df=gl_df,
        recon_df=recon_df,
        cutoff_df=cutoff_df,
        errors=errors,
        output_dir=gt_dir,
    )

    return gt_path


__all__ = [
    "generate_all",
    "generate_profile",
    "generate_gl_ledger",
    "generate_reconciliation_items",
    "generate_cutoff_samples",
    "generate_journal",
    "generate_bank_confirmations",
    "generate_trial_balance",
    "inject_errors",
]
