# -*- coding: utf-8 -*-
"""Optional LLM enhancement for the cash workpaper filler.

The Phase 1 cash filler is deterministic: it aggregates materials and writes
safe cells. This module adds a narrow API-backed layer that only decides
professional judgments and narrative text. It never writes Excel directly.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any

from audit_rag.config import get_settings

from . import cell_map as cm
from .cash_workpaper_filler import FillContext


RISK_KEYS = {
    "completeness": cm.LEAD_RISK_COMPLETENESS,
    "existence": cm.LEAD_RISK_EXISTENCE,
    "valuation": cm.LEAD_RISK_VALUATION,
    "rights": cm.LEAD_RISK_RIGHTS,
    "presentation": cm.LEAD_RISK_PRESENTATION,
}

RISK_NORMALIZATION = {
    "Minimal": "Minimal",
    "Low": "Low",
    "Moderate": "Moderate",
    "High": "High",
    "Significant": "Significant",
    "\u6781\u4f4e": "Minimal",
    "\u4f4e": "Low",
    "\u8f83\u4f4e": "Low",
    "\u4e2d\u7b49": "Moderate",
    "\u4e2d": "Moderate",
    "\u9ad8": "High",
    "\u91cd\u5927": "Significant",
    "\u4e0d\u9002\u7528": "Low",
}

SYSTEM_PROMPT = (
    "You are an assistant to a Chinese CPA audit engagement team preparing "
    "cash and bank workpaper narratives under CAS/Chinese Auditing Standards. "
    "Return strict JSON only, with no Markdown. Write all narrative values in "
    "concise professional Chinese audit-workpaper wording. Do not invent "
    "standard paragraph numbers. If evidence is insufficient, describe the "
    "additional audit procedure needed instead of pretending the matter is "
    "resolved."
)

USER_INSTRUCTIONS = (
    "Review the structured cash audit materials summary and return strict JSON "
    "with this shape:\n"
    "{\n"
    '  "risk_levels": {\n'
    '    "completeness": "Minimal|Low|Moderate|High|Significant",\n'
    '    "existence": "Minimal|Low|Moderate|High|Significant",\n'
    '    "valuation": "Minimal|Low|Moderate|High|Significant",\n'
    '    "rights": "Minimal|Low|Moderate|High|Significant",\n'
    '    "presentation": "Minimal|Low|Moderate|High|Significant"\n'
    "  },\n"
    '  "lead_gl_notes": {"<account name from payload.gl_rows>": "..."},\n'
    '  "recon_rationale": "...",\n'
    '  "recon_conclusion": "...",\n'
    '  "cutoff_reason": "...",\n'
    '  "cutoff_conclusion": "..."\n'
    "}\n\n"
)


def enhance_fill_context_with_llm(ctx: FillContext) -> FillContext:
    """Return a FillContext enhanced by an OpenAI-compatible chat API.

    Required environment variables are already supported by ``audit_rag``:
    ``DEEPSEEK_API_KEY``, optional ``DEEPSEEK_BASE_URL`` and ``LLM_MODEL``.
    """
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is empty. Set .env or use --mode mock.")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "openai package is not installed. Run pip install -r requirements-phase1.txt."
        ) from exc

    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    payload = _context_payload(ctx)
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": USER_INSTRUCTIONS
                + f"Materials summary:\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
            },
        ],
    )
    content = response.choices[0].message.content or ""
    data = _parse_json_object(content)
    return _apply_llm_data(ctx, data)


def _context_payload(ctx: FillContext) -> dict[str, Any]:
    gl_rows = {}
    for account_name, row in ctx.lead_gl_rows.items():
        gl_rows[account_name] = {
            "gl_account_code": row.gl_account_code,
            "current_balance": row.book_value_unaudited,
            "prior_year_balance": row.prior_year_audited,
            "change": row.book_value_unaudited - row.prior_year_audited,
        }

    restricted = [
        {
            "description": item.description,
            "amount": item.amount,
            "nature": item.nature,
            "index": item.index,
        }
        for item in ctx.lead_restricted
    ]

    recon_items = {
        key: [
            {"description": item.description, "amount": item.amount, "index": item.index}
            for item in items
        ]
        for key, items in ctx.recon_items_by_category.items()
    }

    cutoff = {
        "window": ctx.cutoff_window,
        "pre_period_sample_count": len(ctx.cutoff_pre_period),
        "post_period_sample_count": len(ctx.cutoff_post_period),
        "pre_period_total": sum(s.out_amount + s.in_amount for s in ctx.cutoff_pre_period),
        "post_period_total": sum(s.out_amount + s.in_amount for s in ctx.cutoff_post_period),
    }

    return {
        "client_name": ctx.company_name,
        "period_end": ctx.period_end.isoformat(),
        "analysis_date": ctx.analysis_date.isoformat(),
        "te": ctx.te,
        "sad": ctx.sad,
        "gaap": ctx.gaap,
        "currency": ctx.currency,
        "variation_pct": ctx.variation_pct,
        "gl_rows": gl_rows,
        "restricted_cash_items": restricted,
        "recon_account": None
        if ctx.recon_account is None
        else {
            "subject": ctx.recon_account.subject,
            "bank_name": ctx.recon_account.bank_name,
            "bank_account": ctx.recon_account.bank_account,
            "currency": ctx.recon_account.currency,
            "statement_date": ctx.recon_account.statement_date.isoformat(),
            "book_base": ctx.recon_book_base,
            "bank_base": ctx.recon_bank_base,
        },
        "recon_items": recon_items,
        "cutoff": cutoff,
    }


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError(f"LLM did not return JSON: {content[:200]!r}")
        return json.loads(match.group(0))


def _apply_llm_data(ctx: FillContext, data: dict[str, Any]) -> FillContext:
    risk_levels = dict(ctx.risk_levels)
    for key, cell in RISK_KEYS.items():
        raw = str(data.get("risk_levels", {}).get(key, "")).strip()
        if not raw:
            continue
        normalized = RISK_NORMALIZATION.get(raw)
        if normalized in cm.ALLOWED_RISK_LEVELS:
            risk_levels[cell] = normalized

    lead_gl_notes = _string_dict(data.get("lead_gl_notes", {}))
    return replace(
        ctx,
        risk_levels=risk_levels,
        lead_gl_notes=lead_gl_notes,
        recon_rationale=_short_text(data.get("recon_rationale", "")),
        recon_conclusion=_short_text(data.get("recon_conclusion", "")),
        cutoff_reason=_short_text(data.get("cutoff_reason", "")),
        cutoff_conclusion=_short_text(data.get("cutoff_conclusion", "")),
    )


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): _short_text(v) for k, v in value.items() if str(v).strip()}


def _short_text(value: Any, max_len: int = 500) -> str:
    text = str(value).replace("\r", " ").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_len]


__all__ = ["enhance_fill_context_with_llm"]
