# -*- coding: utf-8 -*-
"""
Parse bank confirmation PDFs (银行询证函回函) into ConfirmationRow dataclasses.

Relies on pypdf for PDF text extraction.  Since reportlab-generated PDFs
may not expose Chinese glyphs as extractable text, the parser uses:
  - Account numbers (digits with spaces) → identifies the bank account
  - Largest numeric amount → confirmed balance
  - File name → bank name hint

If pypdf is not installed or parsing fails for all PDFs, the caller should
fall back to CSV-based confirmations.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Try importing pypdf
PDF_SUPPORT: bool
try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Amount: 11,731,518.99 or 11065460.00
_AMOUNT_RE = re.compile(r"\d{1,3}(?:,\d{3})+\.\d{2}|\b\d+\.\d{2}\b")
# Account: groups of 4-4-4-3/4 digits with optional spaces
_ACCOUNT_RE = re.compile(r"(\d{4})\s*(\d{4})\s*(\d{4})\s*(\d{3,4})")
# Date: YYYY-MM-DD
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def parse_confirmation_pdf(path: Path) -> dict | None:
    """Extract fields from a single bank confirmation PDF.

    Returns a dict with keys: bank_name, bank_account, confirmed_balance,
    currency, or None if parsing fails.
    """
    if not PDF_SUPPORT:
        logger.warning("pypdf not installed; cannot parse PDF confirmations")
        return None

    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        logger.warning("Failed to read PDF %s: %s", path, exc)
        return None

    if not text.strip():
        return None

    result: dict = {}

    # --- Bank name: extract from filename ---
    # Filename pattern: 工商银行深圳分行_556633442211009_询证函回函.pdf
    name_match = re.match(r"(.+?)_\d+_\S+\.pdf", path.name)
    if name_match:
        result["bank_name"] = name_match.group(1).replace("_", "")

    # --- Account number ---
    acct_match = _ACCOUNT_RE.search(text)
    if acct_match:
        result["bank_account"] = "".join(acct_match.groups())
    else:
        # Fallback: try to extract from filename
        fn_match = re.search(r"_(\d{15,20})_", path.name)
        if fn_match:
            result["bank_account"] = fn_match.group(1)

    # --- Confirmed balance: largest match is the balance line ---
    amounts = [float(n.replace(",", "")) for n in _AMOUNT_RE.findall(text)]
    if amounts:
        result["confirmed_balance"] = max(amounts)

    # --- Currency ---
    if "USD" in text:
        result["currency"] = "USD"
    elif "$" in text:
        result["currency"] = "USD"
    else:
        result["currency"] = "CNY"

    # --- Confirmation date ---
    dates = _DATE_RE.findall(text)
    if dates:
        result["confirmation_date"] = dates[0]

    if result.get("bank_account") and result.get("confirmed_balance"):
        return result

    logger.warning("Incomplete parse for %s: %s", path.name, result)
    return None


def load_confirmations_from_pdfs(pdf_dir: Path) -> list:
    """Scan a directory for PDF confirmation files and parse each one.

    Returns a list of ConfirmationRow-compatible dicts.
    """
    from .materials_loader import ConfirmationRow

    if not pdf_dir.is_dir():
        logger.warning("Confirmation PDF directory not found: %s", pdf_dir)
        return []

    rows: list = []
    for pdf_path in sorted(pdf_dir.glob("*询证函回函*.pdf")):
        data = parse_confirmation_pdf(pdf_path)
        if data is None:
            logger.warning("Skipping unparseable PDF: %s", pdf_path.name)
            continue

        from datetime import date
        conf_date = data.get("confirmation_date")
        if isinstance(conf_date, str):
            try:
                from datetime import datetime
                conf_date = datetime.strptime(conf_date, "%Y-%m-%d").date()
            except ValueError:
                conf_date = None

        rows.append(
            ConfirmationRow(
                bank_name=data.get("bank_name", ""),
                bank_account=data.get("bank_account", ""),
                currency=data.get("currency", "CNY"),
                confirmed_balance=data.get("confirmed_balance", 0.0),
                restricted_amount=0.0,
                restriction_nature="",
                confirmation_date=conf_date,
                confirmation_index="C.01",
            )
        )

    logger.info("Parsed %d/%d confirmation PDFs", len(rows), len(list(pdf_dir.glob("*.pdf"))))
    return rows
