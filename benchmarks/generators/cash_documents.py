# -*- coding: utf-8 -*-
"""
Generate bank confirmation PDFs (per bank) + Excel journal ledger.

Input:  ``materials/cash/client_profile.json``
Output::

    materials/cash/bank_confirmations/
        ├── 工商银行深圳分行_询证函回函.pdf
        └── 招商银行深圳分行_询证函回函.pdf
    materials/cash/银行存款日记账.xlsx

Each bank confirmation PDF looks like a real bank reply to an audit
confirmation request (银行询证函回函), with seal area and balance info.
The Excel journal is a chronological ledger of all bank transactions
across accounts (序时账).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .cash_client_profile import ClientProfile

REPORTLAB_AVAILABLE = False
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    pass

TX_NARRATIVES = [
    "跨境平台销售结算款-亚马逊",
    "跨境平台销售结算款-TikTok",
    "海外仓FBA仓储费扣款",
    "境外供应商货款支付",
    "汇兑损益-美元结汇",
    "银行手续费-跨境汇款",
    "利息收入-活期存款",
    "代扣增值税-进口关税",
    "关联公司往来款-香港子公司",
    "理财赎回-结构性存款",
    "工资代发-境外员工",
    "退税款-出口退税",
]

JOURNAL_COLUMNS = [
    "日期", "银行名称", "账号", "币种", "摘要", "借方金额", "贷方金额", "余额", "对方单位",
]


def generate_journal(
    profile: ClientProfile,
    output_path: Path,
    seed: int = 42,
) -> Path:
    """Generate a chronological bank journal Excel file (银行存款日记账).

    All accounts' transactions interleaved by date, one row per transaction,
    with a "银行名称" column to distinguish accounts.
    """
    rng = np.random.RandomState(seed + 200)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    counter_parties = [
        "亚马逊平台", "TikTok Shop", "Shopee平台",
        "深圳前海供应链有限公司", "香港子公司",
        "美国客户-ABC Corp", "德国进口商 GmbH",
        "深圳税务局", "中国海关",
    ]

    all_rows: list[dict] = []
    for acct in profile.bank_accounts:
        n_tx = int(rng.randint(20, 50))
        tx_amounts = _generate_tx_amounts(acct.book_balance, n_tx, rng)
        tx_dates = _generate_tx_dates(profile.period_end, n_tx, rng)
        narratives = [str(rng.choice(TX_NARRATIVES)) for _ in range(n_tx)]

        running = 0.0
        for j in range(n_tx):
            amt = tx_amounts[j]
            running += amt
            all_rows.append({
                "日期": tx_dates[j],
                "银行名称": acct.bank_name,
                "账号": acct.account_no,
                "币种": acct.currency,
                "摘要": narratives[j],
                "借方金额": round(amt, 2) if amt >= 0 else 0.0,
                "贷方金额": round(-amt, 2) if amt < 0 else 0.0,
                "余额": round(running, 2),
                "对方单位": str(rng.choice(counter_parties)),
            })

    all_rows.sort(key=lambda r: (r["日期"], r["银行名称"]))

    df = pd.DataFrame(all_rows, columns=JOURNAL_COLUMNS)
    df.to_excel(output_path, index=False, sheet_name="银行存款日记账", engine="openpyxl")
    return output_path


def generate_bank_confirmations(
    profile: ClientProfile,
    output_dir: Path,
    seed: int = 42,
) -> list[Path]:
    """Generate one bank confirmation PDF per account (银行询证函回函).

    Returns list of generated PDF paths. Falls back to CSV if reportlab
    not installed.
    """
    rng = np.random.RandomState(seed + 300)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for acct in profile.bank_accounts:
        n_tx = int(rng.randint(20, 50))
        # Use book_balance so confirmation total matches journal total
        tx_amounts = _generate_tx_amounts(acct.book_balance, n_tx, rng)
        tx_dates = _generate_tx_dates(profile.period_end, n_tx, rng)
        narratives = [str(rng.choice(TX_NARRATIVES)) for _ in range(n_tx)]

        # Build transaction rows with running balance
        tx_rows: list[list] = [["日期", "摘要", "借方", "贷方", "余额"]]
        running = 0.0
        for i in range(n_tx):
            amt = tx_amounts[i]
            running += amt
            tx_rows.append([
                tx_dates[i],
                narratives[i][:14],
                f"{amt:,.2f}" if amt >= 0 else "",
                f"{abs(amt):,.2f}" if amt < 0 else "",
                f"{running:,.2f}",
            ])

        safe_name = acct.bank_name.replace(" ", "_")
        safe_acct = acct.account_no.replace(" ", "")

        if REPORTLAB_AVAILABLE:
            pdf_path = output_dir / f"{safe_name}_{safe_acct}_询证函回函.pdf"
            _write_confirmation_pdf(pdf_path, profile, acct, tx_rows)
            paths.append(pdf_path)
        else:
            csv_path = output_dir / f"{safe_name}_{safe_acct}_询证函回函.csv"
            _write_confirmation_csv(csv_path, profile, acct, tx_rows)
            paths.append(csv_path)

    return paths


def _write_confirmation_csv(path: Path, profile: ClientProfile, acct, tx_rows: list[list]) -> None:
    """Fallback: write bank confirmation as CSV."""
    import csv

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["===== 银行询证函回函 ====="])
        w.writerow(["客户名称", profile.company_name])
        w.writerow(["银行名称", acct.bank_name])
        w.writerow(["账号", acct.account_no])
        w.writerow(["币种", acct.currency])
        w.writerow(["函证基准日", profile.period_end])
        w.writerow(["期末余额", f"{acct.book_balance:,.2f}"])
        w.writerow([])
        w.writerow(["交易明细"])
        for row in tx_rows:
            w.writerow(row)
        w.writerow([])
        w.writerow(["银行盖章处"])
        w.writerow(["(模拟银行公章)"])


def _write_confirmation_pdf(path: Path, profile: ClientProfile, acct, tx_rows: list[list]) -> None:
    """Generate a single-page bank confirmation reply PDF (银行询证函回函)."""
    from reportlab.platypus.flowables import KeepTogether

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=12 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    styles["Title"].fontSize = 14
    styles["Normal"].fontSize = 8
    elements = []

    # Header
    elements.append(Paragraph("<b>银行询证函回函</b>", styles["Title"]))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph("致: 会计师事务所", styles["Normal"]))
    elements.append(Spacer(1, 4 * mm))

    # Info block — compact
    info_data = [
        ["客户名称", profile.company_name],
        ["函证基准日", profile.period_end],
        ["银行名称", acct.bank_name],
        ["账号", acct.account_no],
        ["币种", acct.currency],
        ["期末余额（本位币）", f"{acct.book_balance:,.2f}"],
    ]
    info_table = Table(info_data, colWidths=[40 * mm, 120 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F7FB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 4 * mm))

    # Transaction details
    elements.append(Paragraph("<b>交易明细</b>", styles["Heading3"]))
    elements.append(Spacer(1, 2 * mm))

    # Limit to 18 data rows so everything fits on one page
    header = tx_rows[0]
    data_rows = tx_rows[1:19]
    trimmed = [header] + data_rows

    col_widths = [30 * mm, 48 * mm, 38 * mm, 38 * mm, 36 * mm]
    tx_table = Table(trimmed, colWidths=col_widths, repeatRows=1)
    tx_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F7FB")]),
    ]))

    elements.append(tx_table)
    elements.append(Spacer(1, 8 * mm))

    # Seal / stamp area
    seal_data = [
        ["银行盖章处"],
        ["(本行确认以上信息与记录相符)"],
    ]
    seal_table = Table(seal_data, colWidths=[160 * mm])
    seal_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("BOX", (0, 0), (-1, -1), 1, colors.black),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF9E6")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 1), (-1, 1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
    ]))
    elements.append(seal_table)

    doc.build(elements)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers (shared between journal and confirmations)
# ──────────────────────────────────────────────────────────────────────────────


def _generate_tx_amounts(target_balance: float, n: int, rng: np.random.RandomState) -> list[float]:
    """Generate a list of *n* transaction amounts that ladder up to
    *target_balance* from an assumed zero opening balance.
    """
    amounts: list[float] = []
    remaining = target_balance

    for _ in range(n - 1):
        if rng.random() < 0.7:
            amt = rng.uniform(1000, min(500000, remaining * 0.3))
            amt = min(amt, remaining)
            remaining -= amt
        else:
            amt = -rng.uniform(100, min(100000, abs(remaining) * 0.3 + 50000))
            remaining -= amt
        amounts.append(round(amt, 2))

    amounts.append(round(remaining, 2))
    return amounts


def _generate_tx_dates(period_end: str, n: int, rng: np.random.RandomState) -> list[str]:
    dates: list[str] = []
    for _ in range(n):
        day = rng.randint(1, 28)
        dates.append(f"2025-12-{day:02d}")
    return sorted(dates)
