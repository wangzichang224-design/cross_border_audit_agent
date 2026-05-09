"""
Generate realistic cross-border e-commerce transaction data.
Modeled after Anker Innovations (安克创新) public financial disclosures.
Simulates billing exports from Amazon US/EU/JP, Shopify, Walmart, eBay.
Anomalies are embedded naturally — no labels exposed in the data.
"""

import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

# ── Company profile ──────────────────────────────────────────────────────────
COMPANY_NAME = "安克创新股份有限公司"
COMPANY_EN   = "Anker Innovations Limited"

# Settlement terms by platform (days after sale)
SETTLEMENT_TERMS = {
    "Amazon US":   14,
    "Amazon EU":   14,
    "Amazon JP":   21,
    "TikTok Shop":  3,
    "Shopify":      2,
    "Walmart":      7,
    "eBay":         7,
}

# ── Realistic counterparties per platform × category ─────────────────────────
COUNTERPARTIES = {
    "Amazon US": {
        "revenue":    "Amazon.com Services LLC",
        "fba":        "Amazon Fulfillment Services, Inc.",
        "commission": "Amazon.com Services LLC",
        "ads":        "Amazon Advertising LLC",
        "logistics":  "UPS Supply Chain Solutions, Inc.",
        "customs":    "Geodis USA LLC",
        "payment":    "Payoneer Inc.",
        "vat":        "Internal Revenue Service",
        "refund":     "Amazon.com Services LLC",
        "fx":         "JPMorgan Chase Bank, N.A.",
    },
    "Amazon EU": {
        "revenue":    "Amazon EU S.a.r.l.",
        "fba":        "Amazon Fulfillment Centre GmbH",
        "commission": "Amazon EU S.a.r.l.",
        "ads":        "Amazon Online Germany GmbH",
        "logistics":  "DHL Express GmbH",
        "customs":    "Mainfreight International GmbH",
        "payment":    "PingPong Financial",
        "vat":        "Bundeszentralamt fuer Steuern",
        "refund":     "Amazon EU S.a.r.l.",
        "fx":         "Barclays Bank PLC",
    },
    "Amazon JP": {
        "revenue":    "Amazon Japan G.K.",
        "fba":        "Amazon Japan G.K. Fulfillment",
        "commission": "Amazon Japan G.K.",
        "ads":        "Amazon Advertising K.K.",
        "logistics":  "Yamato Transport Co., Ltd.",
        "customs":    "Nippon Express Co., Ltd.",
        "payment":    "Payoneer Inc.",
        "vat":        "National Tax Agency Japan",
        "refund":     "Amazon Japan G.K.",
        "fx":         "MUFG Bank, Ltd.",
    },
    "TikTok Shop": {
        "revenue":    "TikTok Technology Limited",
        "fba":        "4PX Express Co., Ltd.",
        "commission": "TikTok Technology Limited",
        "ads":        "TikTok Ads Manager",
        "logistics":  "Yunexpress (HK) Limited",
        "customs":    "Kerry Logistics Network",
        "payment":    "Lianlian Global",
        "vat":        "HMRC",
        "refund":     "TikTok Technology Limited",
        "fx":         "Wise Payments Limited",
    },
    "Shopify": {
        "revenue":    "Anker Innovations Ltd. — Direct Store",
        "fba":        "ShipBob, Inc.",
        "commission": "Shopify International Limited",
        "ads":        "Meta Platforms Ireland Limited",
        "logistics":  "Flexport, Inc.",
        "customs":    "C.H. Robinson Worldwide, Inc.",
        "payment":    "Stripe Payments Company",
        "vat":        "Internal Revenue Service",
        "refund":     "Anker Innovations Ltd. — Direct Store",
        "fx":         "Payoneer Inc.",
    },
    "Walmart": {
        "revenue":    "Walmart Inc.",
        "fba":        "Walmart Fulfillment Services",
        "commission": "Walmart Inc.",
        "ads":        "Walmart Connect",
        "logistics":  "FedEx Supply Chain",
        "customs":    "Expeditors International",
        "payment":    "Payoneer Inc.",
        "vat":        "Internal Revenue Service",
        "refund":     "Walmart Inc.",
        "fx":         "Citibank N.A.",
    },
    "eBay": {
        "revenue":    "eBay Marketplaces GmbH",
        "fba":        "Shipwire, Inc.",
        "commission": "eBay Marketplaces GmbH",
        "ads":        "eBay Advertising GmbH",
        "logistics":  "FedEx International",
        "customs":    "Expeditors International",
        "payment":    "Payoneer Inc.",
        "vat":        "HMRC",
        "refund":     "eBay Marketplaces GmbH",
        "fx":         "OFX Group Limited",
    },
}

# ── Anker-specific transaction descriptions ───────────────────────────────────
DESCRIPTIONS = {
    "Product Revenue": [
        "Platform settlement — Anker charging accessories Q4",
        "Merchant payout — Soundcore audio products",
        "Sales proceeds transfer — eufy smart home batch",
        "Revenue disbursement — Nebula projector category",
        "Settlement transfer — PowerCore power bank series",
        "Platform payout — USB-C cable & hub category",
        "Gross revenue remittance — batch #{n}",
        "Weekly disbursement — GaN charger product line",
    ],
    "Amazon FBA Fee": [
        "FBA fulfillment fee — standard size electronics",
        "FBA monthly storage fee — Q4 peak inventory",
        "FBA pick & pack charge — Anker accessories",
        "Fulfillment by Amazon — oversize surcharge",
        "FBA inventory placement fee — Shenzhen origin",
        "Long-term storage fee — 180+ days",
        "FBA removal order fee — end-of-season clearance",
    ],
    "Platform Commission": [
        "Referral fee — electronics 8%",
        "Selling fee deduction — consumer electronics rate",
        "Platform commission — standard rate",
        "Referral fee adjustment — Q4 promotion",
        "Marketplace commission — monthly statement",
        "Category commission — home appliances 6%",
        "Selling plan fee — professional account",
    ],
    "Advertising Spend": [
        "Sponsored Products — GaN charger ASIN campaign",
        "Sponsored Brands — Anker keyword bidding",
        "PPC campaign charge — Q4 Black Friday promotion",
        "Display advertising — retargeting eufy cameras",
        "KOL collaboration fee — tech influencer campaign",
        "Brand promotion — Soundcore seasonal campaign",
        "Performance Max campaign — Google Shopping",
        "TikTok in-feed ad — PowerCore viral campaign",
        "Marketing Fee — platform promotion program",
    ],
    "Logistics & Freight": [
        "International express freight — air Shenzhen to LAX",
        "Sea freight — FCL container Yantian to Rotterdam",
        "First-mile logistics — Shenzhen to Amazon FBA",
        "Last-mile delivery surcharge — peak season",
        "Cross-border logistics — ground US domestic",
        "Airfreight surcharge — fuel adjustment Q4",
        "Warehouse-to-port transportation — Guangzhou",
    ],
    "Customs & Duties": [
        "US import duty — HS code 8504 (chargers)",
        "EU customs clearance fee — electronics",
        "Import tariff — Section 301 surcharge",
        "Customs bond annual premium",
        "ISF filing fee — CBP entry",
        "Anti-dumping duty assessment",
        "EU product compliance levy",
    ],
    "Refund & Chargeback": [
        "Customer refund — order cancellation",
        "A-to-Z claim — product not received",
        "Chargeback dispute — unauthorized txn",
        "Return processing — defective unit quality issue",
        "Goodwill credit — late delivery compensation",
        "Dispute settlement — INR case resolution",
        "Batch refund — recall SKU A2342",
    ],
    "FX Conversion": [
        "USD/EUR conversion — monthly revenue sweep",
        "Currency exchange — CNY repatriation",
        "FX settlement — GBP to USD conversion",
        "Multi-currency payout consolidation",
        "Hedging settlement — forward contract maturity",
        "FX sweep — weekly treasury operation",
        "JPY/USD conversion — Japan revenue repatriation",
    ],
    "Payment Processing Fee": [
        "Payment gateway fee — 2.9% + $0.30",
        "Cross-border processing surcharge",
        "Card transaction fee — Visa/MC",
        "International wire transfer fee",
        "Collection account management fee — Payoneer",
        "Currency conversion fee — 1.5%",
    ],
    "VAT / Tax Remittance": [
        "UK VAT return — quarterly filing",
        "EU OSS VAT remittance — Q4",
        "German VAT — Finanzamt payment",
        "Japan consumption tax — quarterly",
        "Tax compliance filing fee",
        "VAT registration and filing — FR",
        "Import VAT — EU customs entry",
    ],
}


def _desc(category: str, n: int = 0) -> str:
    options = DESCRIPTIONS.get(category, [category])
    text = random.choice(options)
    return text.replace("{n}", str(n))


def _counterparty(platform: str, category: str) -> str:
    cat_map = {
        "Product Revenue":       "revenue",
        "Amazon FBA Fee":        "fba",
        "Platform Commission":   "commission",
        "Advertising Spend":     "ads",
        "Logistics & Freight":   "logistics",
        "Customs & Duties":      "customs",
        "Payment Processing Fee":"payment",
        "VAT / Tax Remittance":  "vat",
        "Refund & Chargeback":   "refund",
        "FX Conversion":         "fx",
    }
    key = cat_map.get(category, "revenue")
    return COUNTERPARTIES.get(platform, COUNTERPARTIES["Amazon US"]).get(key, "Unknown")


def generate_transactions(
    n_days: int = 90,
    base_daily_revenue: float = 500_000,
    start_date: str = "2024-10-01",
) -> pd.DataFrame:
    """
    Generate n_days of Anker Innovations-style synthetic transaction data.
    Revenue scale (~$500K/day) reflects Anker's ~$2.4B annual revenue.
    Anomalies embedded naturally — no labels in data.
    """

    start = datetime.strptime(start_date, "%Y-%m-%d")
    records = []

    platforms = ["Amazon US", "Amazon EU", "Amazon JP", "TikTok Shop", "Shopify", "Walmart", "eBay"]
    currencies = {
        "Amazon US":   "USD",
        "Amazon EU":   "EUR",
        "Amazon JP":   "JPY",
        "TikTok Shop": "USD",
        "Shopify":     "USD",
        "Walmart":     "USD",
        "eBay":        "GBP",
    }
    fx_rates = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067}

    # Anker's actual platform revenue mix (approximated from public disclosures)
    platform_share = {
        "Amazon US":   0.38,
        "Amazon EU":   0.22,
        "Amazon JP":   0.12,
        "TikTok Shop": 0.10,
        "Shopify":     0.10,
        "Walmart":     0.05,
        "eBay":        0.03,
    }

    # Anker cost structure (approximated from annual report ratios)
    cost_structure = {
        "Amazon FBA Fee":         (0.11, 0.13),
        "Platform Commission":    (0.07, 0.09),
        "Advertising Spend":      (0.13, 0.17),   # Anker spends heavily on ads
        "Logistics & Freight":    (0.04, 0.07),
        "Customs & Duties":       (0.02, 0.04),
        "Payment Processing Fee": (0.015, 0.025),
        "VAT / Tax Remittance":   (0.05, 0.09),
    }

    # Anomaly schedule — business-plausible triggers
    anomaly_days = {
        15: "large_transaction",   # Black Friday batch settlement
        32: "fee_spike",           # Double-11 ad overspend
        47: "refund_wave",         # Product defect recall (SKU A2342)
        61: "fx_deviation",        # Unauthorized FX conversion
        74: "missing_data",        # ERP migration data gap
        82: "duplicate_entry",     # Accounting system double-booking
    }

    anomaly_notes = {
        "large_transaction": "Black Friday consolidated settlement — multi-week batch",
        "fee_spike":         "Double-11 campaign — CPC overage approved by marketing",
        "refund_wave":       "Batch refund processing — SKU A2342 quality recall",
        "fx_deviation":      "Emergency FX conversion — treasury instruction ref TRY-0061",
        "missing_data":      "",
        "duplicate_entry":   "Reconciliation entry — pending finance review",
    }

    txn_id = 10000
    batch_counter = 0

    for day_offset in range(n_days):
        date = start + timedelta(days=day_offset)
        anomaly = anomaly_days.get(day_offset)

        # Revenue trend: Q4 peak growth + weekly seasonality + noise
        trend       = 1 + (day_offset / n_days) * 0.22
        seasonality = 1 + 0.28 * np.sin(2 * np.pi * day_offset / 7)
        noise       = np.random.normal(1.0, 0.06)
        daily_rev   = base_daily_revenue * trend * seasonality * noise

        for platform in platforms:
            ccy         = currencies[platform]
            rate        = fx_rates.get(ccy, 1.0)
            settle_days = SETTLEMENT_TERMS[platform]

            rev         = daily_rev * platform_share[platform] * np.random.normal(1.0, 0.05)
            rev_local   = rev / rate
            settle_date = date + timedelta(days=settle_days)

            batch_counter += 1
            note = ""

            # ── Anomaly: oversized single settlement (Black Friday) ──
            if anomaly == "large_transaction" and platform == "Amazon US":
                rev_local *= 8.5
                note = anomaly_notes["large_transaction"]

            records.append({
                "txn_id":          f"TXN-{txn_id:05d}",
                "date":            date.strftime("%Y-%m-%d"),
                "settlement_date": settle_date.strftime("%Y-%m-%d"),
                "platform":        platform,
                "currency":        ccy,
                "amount_local":    round(rev_local, 2),
                "amount_usd":      round(rev_local * rate, 2),
                "category":        "Product Revenue",
                "description":     _desc("Product Revenue", batch_counter),
                "counterparty":    _counterparty(platform, "Product Revenue"),
                "payment_method":  "Bank Transfer",
                "reference":       f"REF-{date.strftime('%Y%m')}-{txn_id:04d}",
                "note":            note,
                "data_source":     f"{platform.lower().replace(' ','_')}_settlement.csv",
            })
            txn_id += 1

            # ── Cost entries ──
            for cost_cat, (lo, hi) in cost_structure.items():
                rate_pct  = random.uniform(lo, hi)
                cost_amt  = rev_local * rate_pct
                cost_note = ""

                if anomaly == "fee_spike" and cost_cat == "Advertising Spend":
                    cost_amt  *= 3.2
                    cost_note  = anomaly_notes["fee_spike"]

                records.append({
                    "txn_id":          f"TXN-{txn_id:05d}",
                    "date":            date.strftime("%Y-%m-%d"),
                    "settlement_date": date.strftime("%Y-%m-%d"),
                    "platform":        platform,
                    "currency":        ccy,
                    "amount_local":    round(-cost_amt, 2),
                    "amount_usd":      round(-cost_amt * rate, 2),
                    "category":        cost_cat,
                    "description":     _desc(cost_cat),
                    "counterparty":    _counterparty(platform, cost_cat),
                    "payment_method":  random.choice(["Bank Transfer", "ACH", "Wire Transfer"]),
                    "reference":       f"INV-{date.strftime('%Y%m')}-{txn_id:04d}",
                    "note":            cost_note,
                    "data_source":     f"{platform.lower().replace(' ','_')}_billing.csv",
                })
                txn_id += 1

            # ── Anomaly: refund wave (product recall) ──
            if anomaly == "refund_wave" and platform in ["Amazon US", "TikTok Shop"]:
                refund_amt = rev_local * random.uniform(0.18, 0.22)
                records.append({
                    "txn_id":          f"TXN-{txn_id:05d}",
                    "date":            date.strftime("%Y-%m-%d"),
                    "settlement_date": date.strftime("%Y-%m-%d"),
                    "platform":        platform,
                    "currency":        ccy,
                    "amount_local":    round(-refund_amt, 2),
                    "amount_usd":      round(-refund_amt * rate, 2),
                    "category":        "Refund & Chargeback",
                    "description":     _desc("Refund & Chargeback"),
                    "counterparty":    _counterparty(platform, "Refund & Chargeback"),
                    "payment_method":  "Reversal",
                    "reference":       f"RFD-{date.strftime('%Y%m')}-{txn_id:04d}",
                    "note":            anomaly_notes["refund_wave"],
                    "data_source":     f"{platform.lower().replace(' ','_')}_returns.csv",
                })
                txn_id += 1

            # ── Anomaly: FX deviation (unauthorized conversion) ──
            if anomaly == "fx_deviation" and ccy == "EUR":
                bad_rate = rate * 0.92
                records.append({
                    "txn_id":          f"TXN-{txn_id:05d}",
                    "date":            date.strftime("%Y-%m-%d"),
                    "settlement_date": date.strftime("%Y-%m-%d"),
                    "platform":        platform,
                    "currency":        "EUR",
                    "amount_local":    round(rev_local * 0.5, 2),
                    "amount_usd":      round(rev_local * 0.5 * bad_rate, 2),
                    "category":        "FX Conversion",
                    "description":     _desc("FX Conversion"),
                    "counterparty":    _counterparty(platform, "FX Conversion"),
                    "payment_method":  "FX Swap",
                    "reference":       f"FX-{date.strftime('%Y%m')}-{txn_id:04d}",
                    "note":            anomaly_notes["fx_deviation"],
                    "data_source":     "treasury_fx_log.csv",
                })
                txn_id += 1

        # ── Anomaly: duplicate entry ──
        if anomaly == "duplicate_entry" and records:
            dup = records[-1].copy()
            dup["txn_id"] = f"TXN-{txn_id:05d}"
            dup["note"]   = anomaly_notes["duplicate_entry"]
            records.append(dup)
            txn_id += 1

    df = pd.DataFrame(records)

    # ── Anomaly: missing data (ERP migration gap, day 74) ──
    gap_date = (start + timedelta(days=74)).strftime("%Y-%m-%d")
    mask = (df["date"] == gap_date) & (df["platform"] == "Shopify")
    df.loc[mask, "amount_local"] = np.nan
    df.loc[mask, "amount_usd"]   = np.nan

    # ── Scramble 8% of transactions to Unclassified for AI classification ──
    unclass_idx = df.sample(frac=0.08, random_state=7).index
    df.loc[unclass_idx, "category"] = "Unclassified"

    return df.reset_index(drop=True)


def generate_settlement_schedule(df: pd.DataFrame) -> dict:
    """
    Derive expected vs actual settlement flows from transaction data.
    Used as input for RECONCILIATION_PROMPT.

    Returns a dict with:
      expected_settlements: what platforms owe based on sales + T+N terms
      actual_bank_receipts: what actually arrived (with embedded discrepancies)
    """
    revenue = df[df["category"] == "Product Revenue"].copy()
    revenue["settlement_date"] = pd.to_datetime(revenue["settlement_date"])
    revenue["week"] = revenue["settlement_date"].dt.to_period("W").astype(str)

    # Aggregate expected settlements by platform × week
    expected = (
        revenue.groupby(["platform", "week", "currency"])["amount_usd"]
        .sum()
        .reset_index()
        .rename(columns={"amount_usd": "expected_usd"})
        .round({"expected_usd": 2})
    )

    # Build actual receipts — start from expected, then embed discrepancies
    actual_rows = []
    for _, row in expected.iterrows():
        actual_rows.append({
            "platform":    row["platform"],
            "week":        row["week"],
            "currency":    row["currency"],
            "received_usd": row["expected_usd"],
            "receipt_ref": f"RCPT-{row['platform'][:3].upper()}-{row['week'][-4:]}",
            "note":        "",
        })

    actual = pd.DataFrame(actual_rows)

    # ── Discrepancy 1: Amazon EU Week 6 — payment delayed 14 extra days ──
    weeks = sorted(expected["week"].unique())
    if len(weeks) >= 6:
        w6 = weeks[5]
        mask = (actual["platform"] == "Amazon EU") & (actual["week"] == w6)
        actual.loc[mask, "received_usd"] = 0.0
        actual.loc[mask, "note"] = "Payment not received — Amazon EU settlement delay (T+28)"
        # Insert as a late receipt in week 8
        if len(weeks) >= 8:
            late_amount = float(expected.loc[
                (expected["platform"] == "Amazon EU") & (expected["week"] == w6),
                "expected_usd"
            ].sum())
            actual_rows.append({
                "platform":    "Amazon EU",
                "week":        weeks[7],
                "currency":    "EUR",
                "received_usd": late_amount,
                "receipt_ref": f"RCPT-AMZ-EU-LATE-W6",
                "note":        "Late receipt — originally due W6, arrived W8",
            })

    # ── Discrepancy 2: TikTok Shop Week 5 — 7% shortfall, no explanation ──
    if len(weeks) >= 5:
        w5 = weeks[4]
        mask = (actual["platform"] == "TikTok Shop") & (actual["week"] == w5)
        actual.loc[mask, "received_usd"] = (
            actual.loc[mask, "received_usd"] * 0.93
        ).round(2)
        actual.loc[mask, "note"] = "Partial receipt — 7% shortfall, TikTok platform fee adjustment unconfirmed"

    # ── Discrepancy 3: Shopify Week 11 — overpayment with no matching sales ──
    if len(weeks) >= 11:
        actual_rows.append({
            "platform":    "Shopify",
            "week":        weeks[10],
            "currency":    "USD",
            "received_usd": 8_247.50,
            "receipt_ref": "RCPT-SHP-UNKN-001",
            "note":        "Unidentified inflow — no matching sales order; requires investigation",
        })

    # ── Discrepancy 4: Amazon JP Week 3 — settlement missing entirely ──
    if len(weeks) >= 3:
        w3 = weeks[2]
        mask = (actual["platform"] == "Amazon JP") & (actual["week"] == w3)
        actual.loc[mask, "received_usd"] = 0.0
        actual.loc[mask, "note"] = "Missing settlement — Amazon JP Week 3; FX conversion pending"

    actual = pd.DataFrame(actual_rows)

    return {
        "company":               COMPANY_EN,
        "period":                "2024-Q4",
        "expected_settlements":  expected.to_dict(orient="records"),
        "actual_bank_receipts":  actual.to_dict(orient="records"),
    }


def save_raw_data(df: pd.DataFrame, output_dir: str) -> str:
    import os
    os.makedirs(output_dir, exist_ok=True)
    path = f"{output_dir}/raw_transactions_2024Q4.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config import RAW_DATA_DIR
    df = generate_transactions()
    out = save_raw_data(df, str(RAW_DATA_DIR))
    print(f"Generated {len(df):,} transactions -> {out}")
    print(df[["txn_id", "date", "platform", "counterparty", "amount_usd", "category", "note"]].head(12).to_string())

    schedule = generate_settlement_schedule(df)
    print(f"\nSettlement schedule: {len(schedule['expected_settlements'])} expected, "
          f"{len(schedule['actual_bank_receipts'])} actual entries")
