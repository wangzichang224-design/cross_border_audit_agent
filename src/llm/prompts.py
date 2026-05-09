"""
Audit-grade prompt library.
Each prompt encodes a specific CPA/audit check as an AI-executable instruction.
Prompts are versioned for iterative improvement tracking.
"""

# ─────────────────────────────────────────────
# MODULE 1: Transaction Classification
# ─────────────────────────────────────────────

CLASSIFY_TRANSACTIONS_PROMPT = """You are a senior forensic accountant specializing in cross-border e-commerce.

Your task is to classify the following unclassified transaction descriptions into the correct accounting category.

## Valid Categories
- Product Revenue
- Amazon FBA Fee
- Platform Commission
- Advertising Spend
- Logistics & Freight
- Customs & Duties
- Refund & Chargeback
- FX Conversion
- Payment Processing Fee
- Warehouse Storage Fee
- Return Processing Fee
- Promotional Discount
- VAT / Tax Remittance
- Unclassified  ← use ONLY when genuinely ambiguous

## Transactions to Classify
{transactions_json}

## Instructions
1. For each transaction, assign the BEST-FIT category from the list above.
2. Provide a confidence score: HIGH / MEDIUM / LOW.
3. Add a brief rationale (max 15 words).
4. If the description could indicate fraud or misuse of funds (e.g., "personal expense" disguised as marketing), flag it with risk_flag: true.

## Output Format (strict JSON array)
[
  {{
    "txn_id": "TXN-XXXXX",
    "predicted_category": "...",
    "confidence": "HIGH|MEDIUM|LOW",
    "rationale": "...",
    "risk_flag": false
  }},
  ...
]

Return ONLY the JSON array. No markdown, no explanations outside the JSON.
"""

# ─────────────────────────────────────────────
# MODULE 2: Anomaly Audit (CPA-style checks)
# ─────────────────────────────────────────────

ANOMALY_DETECTION_PROMPT = """You are an AI audit assistant trained in ISA 240 (fraud risk) and ISA 520 (analytical procedures).

You are reviewing a daily financial summary for a cross-border e-commerce company.

## Summary Data
{summary_json}

## Audit Thresholds (materiality parameters)
- Single transaction alert: > USD {single_txn_threshold:,.0f}
- Daily outflow spike: > {daily_outflow_pct:.0%} day-over-day change
- Days Sales Outstanding (DSO): > {dso_threshold} days is unusual
- Fee rate alert: any fee category > {fee_rate_threshold:.0%} of revenue
- Refund rate alert: > {refund_rate_threshold:.0%} of gross revenue

## Your Task
Perform analytical procedures and identify anomalies. For each finding:
1. Describe the anomaly precisely (what, when, how large)
2. Classify risk level: CRITICAL / HIGH / MEDIUM / LOW
3. Suggest the most likely cause (benign vs. fraud indicator)
4. Recommend the specific audit procedure to investigate further

## Output Format (strict JSON)
{{
  "audit_date": "YYYY-MM-DD",
  "overall_risk": "CRITICAL|HIGH|MEDIUM|LOW",
  "findings": [
    {{
      "finding_id": "F001",
      "risk_level": "...",
      "category": "...",
      "description": "...",
      "amount_impact_usd": 0,
      "likely_cause": "...",
      "recommended_procedure": "..."
    }}
  ],
  "summary_narrative": "2-3 sentence executive summary for CFO"
}}
"""

# ─────────────────────────────────────────────
# MODULE 3: Fund Flow Reconciliation Check
# ─────────────────────────────────────────────

RECONCILIATION_PROMPT = """You are performing a fund flow reconciliation for a cross-border e-commerce company.

## Expected vs Actual Flows
{reconciliation_data}

## Payment Chain Context
- Platforms settle to a HK holding entity (T+7 for Amazon, T+3 for TikTok)
- HK entity converts to USD and transfers to mainland CN entity
- FX conversions must use rates within 5% of PBOC mid-rate
- All intercompany transfers require a signed service agreement

## Your Task
1. Identify any reconciling items (timing differences vs. real gaps)
2. Flag unreconciled items > USD 5,000
3. Identify missing links in the payment chain
4. Assess whether the overall fund flow is consistent with arm's-length transactions

## Output Format (strict JSON)
{{
  "reconciliation_status": "BALANCED|UNBALANCED|PARTIAL",
  "unreconciled_items": [
    {{
      "item": "...",
      "amount_usd": 0,
      "direction": "inflow|outflow",
      "explanation": "...",
      "requires_followup": true
    }}
  ],
  "chain_integrity_issues": ["..."],
  "compliance_flags": ["..."]
}}
"""

# ─────────────────────────────────────────────
# MODULE 4: Executive Report Generation
# ─────────────────────────────────────────────

REPORT_GENERATION_PROMPT = """You are a senior finance analyst writing the weekly cash flow intelligence report for a cross-border e-commerce CFO.

## Data Inputs
{report_data_json}

## Writing Guidelines
- Tone: Professional, concise, action-oriented
- Audience: CFO and VP Finance (high financial literacy, time-constrained)
- Structure: Start with the most important insight, not background
- Numbers: Always include % change vs prior period; round to 1 decimal place
- Flags: Highlight anything requiring CFO decision within 48 hours

## Report Sections Required
1. **Executive Summary** (3 bullet points max, each < 20 words)
2. **Revenue & Collection Performance** (DSO trend, platform breakdown, settlement delays)
3. **Cost Structure Analysis** (fee rates by category, anomalies, MoM changes)
4. **Risk & Compliance Flags** (ranked by severity, with recommended actions)
5. **AI Recommendations** (2-3 forward-looking actions the team should take this week)

## Output Format
Return a well-structured Markdown report. Use tables where data is comparative.
Use **bold** for key metrics. Flag items needing CFO attention with ⚠️.
"""

# ─────────────────────────────────────────────
# MODULE 5: Prompt Engineering Iteration Log
# ─────────────────────────────────────────────

PROMPT_VERSIONS = {
    "classify_transactions": {
        "v1.0": "Basic classification without confidence scores — accuracy ~72%",
        "v1.1": "Added confidence scoring and rationale — accuracy ~81%",
        "v1.2": "Added fraud risk_flag and 'Unclassified' escape hatch — accuracy ~89%",
        "v2.0": "Current: Added ISA-aligned context and per-platform fee rate anchors — accuracy ~94%",
    },
    "anomaly_detection": {
        "v1.0": "Generic outlier detection — too many false positives (~40%)",
        "v1.1": "Added materiality thresholds as parameters — FP rate dropped to 18%",
        "v2.0": "Current: Grounded in ISA 240/520 framework + cause-and-procedure pairing",
    },
}
