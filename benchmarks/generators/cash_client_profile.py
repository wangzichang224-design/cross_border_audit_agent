# -*- coding: utf-8 -*-
"""
Generate a realistic client profile for the C (货币资金) audit workpaper.

Output: ``materials/cash/client_profile.json``

The profile is the single source of truth for an entire test scenario:
account structure, materiality thresholds, risk levels, and bank info.
All downstream generators (GL ledger, transactions, documents) read from it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Deterministic pools
# ──────────────────────────────────────────────────────────────────────────────

COMPANY_NAMES = [
    "星辰跨境科技(深圳)有限公司",
    "云帆国际贸易(上海)有限公司",
    "蓝海跨境电商(广州)有限公司",
    "天穹出海科技(杭州)有限公司",
    "飞鱼数字贸易(深圳)有限公司",
]

BANK_NAMES_CNY = [
    "招商银行深圳分行",
    "中国银行深圳分行",
    "建设银行广州分行",
    "工商银行深圳分行",
    "农业银行深圳分行",
]

BANK_NAMES_USD = [
    "中国银行深圳分行",
    "招商银行深圳分行",
    "汇丰银行深圳分行",
]

ACCOUNT_SUFFIXES = [
    "7559 1234 5678 901",
    "7788 4321 5678 101",
    "6688 9876 5432 101",
    "5566 3344 2211 009",
]

RISK_LEVELS = ("Minimal", "Low", "Moderate", "High", "Significant")

# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BankAccount:
    bank_name: str
    account_no: str
    currency: str  # "CNY" or "USD"
    book_balance: float
    statement_balance: float


@dataclass(frozen=True)
class RiskLevels:
    completeness: str = "Moderate"
    existence: str = "Low"
    valuation: str = "Moderate"
    rights: str = "Low"
    presentation: str = "Low"


@dataclass(frozen=True)
class ClientProfile:
    company_name: str
    period_end: str  # "2025-12-31"
    currency: str  # "CNY"
    gaap: str  # "企业会计准则"
    te: float  # Tolerable Error
    sad: float  # SAD threshold
    cash_on_hand: float  # 库存现金
    other_funds: float  # 其他货币资金
    bank_accounts: list[BankAccount] = field(default_factory=list)
    risk_levels: RiskLevels = field(default_factory=RiskLevels)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["bank_accounts"] = [asdict(ba) for ba in self.bank_accounts]
        d["risk_levels"] = asdict(self.risk_levels)
        return d


# ──────────────────────────────────────────────────────────────────────────────
# Generator
# ──────────────────────────────────────────────────────────────────────────────


def generate_profile(
    seed: int = 42,
    company_name: str | None = None,
    period_end: str = "2025-12-31",
) -> ClientProfile:
    """Generate a deterministic client profile.

    Parameters
    ----------
    seed:
        Random seed for reproducibility. Different seeds → different profile.
    company_name:
        Override the auto-picked company name (useful for testing).
    period_end:
        Balance sheet date string.
    """
    rng = np.random.RandomState(seed)

    # ── Pick company ──────────────────────────────────────────────────
    name = company_name or COMPANY_NAMES[seed % len(COMPANY_NAMES)]

    # ── Determine TE and SAD ─────────────────────────────────────────
    # Total assets roughly 50M ~ 200M (reasonable for a mid-size exporter)
    total_assets = rng.uniform(50_000_000, 200_000_000)
    te = round(total_assets * rng.uniform(0.03, 0.08), -3)  # 3-8% of TA
    sad = round(te * rng.uniform(0.04, 0.06), -2)  # 4-6% of TE

    # ── Cash composition ─────────────────────────────────────────────
    cash_total = round(total_assets * rng.uniform(0.08, 0.20), -3)  # 8-20% of TA
    cash_on_hand = round(cash_total * rng.uniform(0.002, 0.01), -2)  # 0.2-1%
    other_funds = round(cash_total * rng.uniform(0.01, 0.05), -2)  # 1-5%
    bank_total = cash_total - cash_on_hand - other_funds

    # ── Bank accounts ────────────────────────────────────────────────
    num_cny_accounts = int(rng.choice([1, 2], p=[0.6, 0.4]))
    num_usd_accounts = int(rng.choice([0, 1], p=[0.4, 0.6]))

    cny_amounts = _split_amount(bank_total * 0.7, num_cny_accounts, rng)
    usd_amounts = _split_amount(bank_total * 0.3, num_usd_accounts, rng)

    accounts: list[BankAccount] = []
    used_cny_banks: set[str] = set()
    used_suffixes: set[str] = set()

    for i in range(num_cny_accounts):
        bank = _pick_unused(BANK_NAMES_CNY, used_cny_banks, rng, seed + i)
        suffix = _pick_unused(ACCOUNT_SUFFIXES, used_suffixes, rng, seed + i + 10)
        book = round(cny_amounts[i], 2)
        # Statement balance differs slightly (creates reconciliation need)
        stmt = round(book * rng.uniform(0.98, 1.02), 2)
        accounts.append(BankAccount(
            bank_name=bank, account_no=suffix,
            currency="CNY", book_balance=book, statement_balance=stmt,
        ))

    for i in range(num_usd_accounts):
        bank = _pick_unused(BANK_NAMES_USD, set(), rng, seed + i + 20)
        suffix = _pick_unused(ACCOUNT_SUFFIXES, used_suffixes, rng, seed + i + 30)
        usd_amount = round(usd_amounts[i] / 7.12, 2)  # Convert to USD
        stmt = round(usd_amount * rng.uniform(0.98, 1.02), 2)
        accounts.append(BankAccount(
            bank_name=bank, account_no=suffix,
            currency="USD", book_balance=usd_amount, statement_balance=stmt,
        ))

    # ── Risk levels (pick from weighted distribution) ────────────────
    risk_weights = {"Minimal": 0.1, "Low": 0.35, "Moderate": 0.35, "High": 0.15, "Significant": 0.05}
    risk_names, risk_probs = zip(*risk_weights.items())
    risk_picked = list(rng.choice(risk_names, size=5, p=risk_probs))
    risk = RiskLevels(
        completeness=risk_picked[0],
        existence=risk_picked[1],
        valuation=risk_picked[2],
        rights=risk_picked[3],
        presentation=risk_picked[4],
    )

    return ClientProfile(
        company_name=name,
        period_end=period_end,
        currency="CNY",
        gaap="企业会计准则",
        te=te,
        sad=sad,
        cash_on_hand=cash_on_hand,
        other_funds=other_funds,
        bank_accounts=accounts,
        risk_levels=risk,
    )


# ──────────────────────────────────────────────────────────────────────────────
# IO
# ──────────────────────────────────────────────────────────────────────────────


def save_profile(profile: ClientProfile, path: Path) -> Path:
    """Write the profile as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
    return path


def load_profile(path: Path) -> ClientProfile:
    """Load a previously saved profile from JSON."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    accounts = [BankAccount(**ba) for ba in data.pop("bank_accounts", [])]
    risk_data = data.pop("risk_levels", {})
    risk = RiskLevels(**risk_data)
    return ClientProfile(**data, bank_accounts=accounts, risk_levels=risk)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _pick_unused(pool: list[str], used: set[str], rng: np.random.RandomState, fallback_seed: int) -> str:
    """Pick from pool avoiding *used* items; fall back to deterministic if pool exhausted."""
    available = [item for item in pool if item not in used]
    if not available:
        idx = fallback_seed % len(pool)
        return pool[idx]
    idx = rng.randint(len(available))
    chosen = available[idx]
    used.add(chosen)
    return chosen


def _split_amount(total: float, n: int, rng: np.random.RandomState) -> list[float]:
    """Split *total* into *n* random positive amounts that sum to *total*."""
    if n == 0:
        return []
    if n == 1:
        return [total]
    ratios = rng.dirichlet(np.ones(n))
    # Ensure large-enough remaining for last split
    amounts = [round(total * r, 2) for r in ratios[:-1]]
    amounts.append(round(total - sum(amounts), 2))
    return amounts
