# -*- coding: utf-8 -*-
"""
Generate a simplified trial balance / client-prepared financial statement (试算平衡表).

Output: ``materials/cash/试算平衡表.xlsx``

Contains a snapshot of ALL major GL accounts (not just cash), so the Agent
can see the full picture — revenue, receivables, payables, fixed assets, etc.
Only the 货币资金 row's values come from the client profile; other accounts
get reasonable synthetic values.

This mimics the A3 (or client-provided TB) that auditors receive before
starting fieldwork.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .cash_client_profile import ClientProfile

TB_COLUMNS = [
    "科目编码",
    "科目名称",
    "期末借方余额",
    "期末贷方余额",
    "上年末审定数",
    "备注",
]

# Standard chart of accounts for a mid-size cross-border e-commerce company
ACCOUNTS = [
    ("1001", "库存现金"),
    ("1002", "银行存款"),
    ("1012", "其他货币资金"),
    ("1101", "交易性金融资产"),
    ("1121", "应收票据"),
    ("1122", "应收账款"),
    ("1123", "预付账款"),
    ("1131", "应收股利"),
    ("1221", "其他应收款"),
    ("1231", "坏账准备"),
    ("1401", "材料采购"),
    ("1403", "原材料"),
    ("1405", "库存商品"),
    ("1408", "委托加工物资"),
    ("1471", "存货跌价准备"),
    ("1501", "持有待售资产"),
    ("1511", "长期股权投资"),
    ("1601", "固定资产"),
    ("1602", "累计折旧"),
    ("1603", "固定资产减值准备"),
    ("1604", "在建工程"),
    ("1701", "无形资产"),
    ("1702", "累计摊销"),
    ("2001", "短期借款"),
    ("2201", "应付票据"),
    ("2202", "应付账款"),
    ("2203", "预收账款"),
    ("2211", "应付职工薪酬"),
    ("2221", "应交税费"),
    ("2231", "应付利息"),
    ("2241", "其他应付款"),
    ("2501", "长期借款"),
    ("4001", "实收资本"),
    ("4002", "资本公积"),
    ("4101", "盈余公积"),
    ("4104", "未分配利润"),
    ("5001", "生产成本"),
    ("5101", "制造费用"),
    ("6001", "主营业务收入"),
    ("6051", "其他业务收入"),
    ("6111", "投资收益"),
    ("6301", "营业外收入"),
    ("6401", "主营业务成本"),
    ("6402", "其他业务成本"),
    ("6601", "销售费用"),
    ("6602", "管理费用"),
    ("6603", "财务费用"),
    ("6701", "资产减值损失"),
    ("6711", "营业外支出"),
    ("6801", "所得税费用"),
]


def generate_trial_balance(
    profile: ClientProfile,
    output_path: Path,
    seed: int = 42,
) -> Path:
    """Generate a trial balance Excel file with all major GL accounts.

    The 货币资金 rows (库存现金/银行存款/其他货币资金) use the actual
    values from the client profile. Other accounts get proportionate synthetic
    values based on total assets / revenue implied by the profile.
    """
    rng = np.random.RandomState(seed + 400)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Total assets proxy from profile
    cash_total = profile.cash_on_hand + sum(a.book_balance for a in profile.bank_accounts) + profile.other_funds
    # Assume cash is ~12% of total assets (typical for e-commerce)
    total_assets_estimate = cash_total / rng.uniform(0.08, 0.18)
    total_revenue_estimate = total_assets_estimate * rng.uniform(1.2, 2.5)

    rows: list[dict] = []
    is_cash_row = {
        "库存现金": True,
        "银行存款": True,
        "其他货币资金": True,
    }

    for code, name in ACCOUNTS:
        if name in is_cash_row:
            # Pull actual cash values from profile
            if name == "库存现金":
                cur_balance = profile.cash_on_hand
            elif name == "银行存款":
                cur_balance = sum(a.book_balance for a in profile.bank_accounts)
            else:
                cur_balance = profile.other_funds
            prior = round(cur_balance * rng.uniform(0.85, 1.15), 2)
            rows.append(_debit_row(code, name, cur_balance, prior))
        elif name in ("累计折旧", "累计摊销", "坏账准备", "存货跌价准备", "固定资产减值准备"):
            # Contra accounts — credit balance
            amount = round(total_assets_estimate * rng.uniform(0.002, 0.01), 2)
            prior = round(amount * rng.uniform(0.9, 1.1), 2)
            rows.append(_credit_row(code, name, amount, prior))
        elif name in ("应收账款", "预付账款", "其他应收款"):
            amount = round(total_assets_estimate * rng.uniform(0.02, 0.08), 2)
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_debit_row(code, name, amount, prior))
        elif name in ("存货", "原材料", "库存商品"):
            amount = round(total_assets_estimate * rng.uniform(0.05, 0.15), 2)
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_debit_row(code, name, amount, prior))
        elif name in ("固定资产", "在建工程", "无形资产", "长期股权投资"):
            amount = round(total_assets_estimate * rng.uniform(0.05, 0.20), 2)
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_debit_row(code, name, amount, prior))
        elif name in ("应付账款", "预收账款", "应付职工薪酬", "应交税费", "其他应付款"):
            amount = round(total_assets_estimate * rng.uniform(0.01, 0.06), 2)
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_credit_row(code, name, amount, prior))
        elif name in ("短期借款", "长期借款"):
            amount = round(total_assets_estimate * rng.uniform(0.05, 0.20), 2)
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_credit_row(code, name, amount, prior))
        elif name in ("实收资本", "资本公积", "盈余公积"):
            amount = round(total_assets_estimate * rng.uniform(0.10, 0.40), 2)
            prior = round(amount * rng.uniform(0.95, 1.05), 2)
            rows.append(_credit_row(code, name, amount, prior))
        elif name == "未分配利润":
            amount = round(total_assets_estimate * rng.uniform(0.05, 0.20), 2)
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_credit_row(code, name, amount, prior))
        elif name.startswith("主营业务收入") or name in ("其他业务收入", "投资收益", "营业外收入"):
            amount = round(total_revenue_estimate * rng.uniform(0.01, 0.90), 2)
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_credit_row(code, name, amount, prior))
        elif name.startswith(("主营业务成本", "其他业务成本")):
            amount = round(total_revenue_estimate * rng.uniform(0.60, 0.85), 2)
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_debit_row(code, name, amount, prior))
        elif name in ("销售费用", "管理费用", "财务费用", "资产减值损失", "营业外支出"):
            amount = round(total_revenue_estimate * rng.uniform(0.01, 0.08), 2)
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_debit_row(code, name, amount, prior))
        elif name == "所得税费用":
            profit = total_revenue_estimate * 0.10  # rough 10% net margin
            amount = round(profit * 0.25, 2)  # 25% CIT
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_debit_row(code, name, amount, prior))
        else:
            # Default: small debit balance
            amount = round(total_assets_estimate * rng.uniform(0.001, 0.01), 2)
            prior = round(amount * rng.uniform(0.85, 1.15), 2)
            rows.append(_debit_row(code, name, amount, prior))

    df = pd.DataFrame(rows, columns=TB_COLUMNS)

    # Write with openpyxl for formatting
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="试算平衡表")
        ws = writer.sheets["试算平衡表"]
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 22
        ws.column_dimensions["C"].width = 18
        ws.column_dimensions["D"].width = 18
        ws.column_dimensions["E"].width = 18
        ws.column_dimensions["F"].width = 14
        # Bold header
        from openpyxl.styles import Font
        for cell in ws[1]:
            cell.font = Font(bold=True)

    return output_path


def _debit_row(code: str, name: str, balance: float, prior: float) -> dict:
    return {
        "科目编码": code,
        "科目名称": name,
        "期末借方余额": balance,
        "期末贷方余额": 0.0,
        "上年末审定数": prior,
        "备注": "",
    }


def _credit_row(code: str, name: str, balance: float, prior: float) -> dict:
    return {
        "科目编码": code,
        "科目名称": name,
        "期末借方余额": 0.0,
        "期末贷方余额": balance,
        "上年末审定数": prior,
        "备注": "",
    }
