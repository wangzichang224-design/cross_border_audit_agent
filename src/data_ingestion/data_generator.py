"""
Generate realistic cross-border e-commerce transaction data.
Simulates billing exports from Amazon, TikTok Shop, Shopify, eBay.
Anomalies are embedded naturally — no labels exposed in the data.
"""

import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

# ── Company profile ──────────────────────────────────────────────────────────
COMPANY_NAME = "星辰跨境科技（深圳）有限公司"
COMPANY_EN   = "StarCross Technology (Shenzhen) Co., Ltd."

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
        "revenue":    "Shopify International Limited",
        "fba":        "ShipBob, Inc.",
        "commission": "Shopify International Limited",
        "ads":        "Meta Platforms Ireland Limited",
        "logistics":  "Flexport, Inc.",
        "customs":    "C.H. Robinson Worldwide, Inc.",
        "payment":    "Stripe Payments Company",
        "vat":        "Internal Revenue Service",
        "refund":     "Shopify International Limited",
        "fx":         "Payoneer Inc.",
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

# ── Transaction descriptions ──────────────────────────────────────────────────
DESCRIPTIONS = {
    "Product Revenue": [
        "Platform settlement — Q4 product sales",
        "Merchant payout — electronics category",
        "Sales proceeds transfer — weekly batch",
        "Revenue disbursement — home & garden",
        "Settlement transfer — consumer goods",
        "Platform payout — health & beauty",
        "Gross revenue remittance — batch #{n}",
    ],
    "Amazon FBA Fee": [
        "FBA fulfillment fee — standard size",
        "FBA monthly storage fee — Q4",
        "FBA pick & pack charge",
        "Fulfillment by Amazon — oversize surcharge",
        "FBA inventory placement fee",
        "Long-term storage fee — 180+ days",
    ],
    "Platform Commission": [
        "Referral fee — electronics 8%",
        "Selling fee deduction — category rate",
        "Platform commission — standard rate",
        "Referral fee adjustment",
        "Marketplace commission — monthly",
        "Category commission — home appliances",
    ],
    "Advertising Spend": [
        "Sponsored Products — ASIN campaign",
        "Sponsored Brands — keyword bidding",
        "PPC campaign charge — Q4 promotion",
        "Display advertising — retargeting",
        "Influencer collaboration — KOL fee",
        "Brand promotion — seasonal campaign",
        "Performance Max campaign charge",
    ],
    "Logistics & Freight": [
        "International express freight — air",
        "Sea freight — FCL container charge",
        "First-mile logistics — Yiwu to LAX",
        "Last-mile delivery surcharge",
        "Cross-border logistics — ground",
        "Airfreight surcharge — fuel adjustment",
        "Warehouse-to-port transportation",
    ],
    "Customs & Duties": [
        "US import duty — HS code 8471",
        "EU customs clearance fee",
        "Import tariff — consumer electronics",
        "Customs bond annual premium",
        "Duty drawback — re-export refund",
        "Entry filing fee — CBP",
        "Anti-dumping duty payment",
    ],
    "Refund & Chargeback": [
        "Customer refund — order cancellation",
        "A-to-Z claim — product not received",
        "Chargeback dispute — unauthorized txn",
        "Return processing — quality issue",
        "Goodwill refund — late delivery",
        "Dispute settlement — INR case",
    ],
    "FX Conversion": [
        "USD/EUR conversion — monthly sweep",
        "Currency exchange — revenue repatriation",
        "FX settlement — CNY conversion",
        "Multi-currency payout consolidation",
        "Hedging settlement — forward contract",
        "FX sweep — weekly treasury operation",
    ],
    "Payment Processing Fee": [
        "Payment gateway fee — 2.9% + $0.30",
        "Cross-border processing surcharge",
        "Card transaction fee — Visa/MC",
        "International wire transfer fee",
        "Collection account management fee",
        "Currency conversion fee — 1.5%",
    ],
    "VAT / Tax Remittance": [
        "UK VAT return — quarterly filing",
        "EU OSS VAT remittance — Q4",
        "German VAT — Finanzamt payment",
        "GST payment — AU quarterly",
        "Tax compliance filing fee",
        "VAT registration and filing — FR",
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
    base_daily_revenue: float = 85_000,
    start_date: str = "2024-10-01",
) -> pd.DataFrame:
    """Generate n_days of realistic synthetic transaction data with embedded anomalies."""

    start = datetime.strptime(start_date, "%Y-%m-%d")
    records = []

    platforms = ["Amazon US", "Amazon EU", "TikTok Shop", "Shopify", "eBay"]
    currencies = {
        "Amazon US":   "USD",
        "Amazon EU":   "EUR",
        "TikTok Shop": "USD",
        "Shopify":     "USD",
        "eBay":        "GBP",
    }
    fx_rates = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "JPY": 0.0067, "BRL": 0.20}

    platform_share = {
        "Amazon US":   0.40,
        "Amazon EU":   0.25,
        "TikTok Shop": 0.20,
        "Shopify":     0.10,
        "eBay":        0.05,
    }

    cost_structure = {
        "Amazon FBA Fee":         (0.10, 0.13),
        "Platform Commission":    (0.08, 0.12),
        "Advertising Spend":      (0.06, 0.14),
        "Logistics & Freight":    (0.04, 0.08),
        "Customs & Duties":       (0.02, 0.04),
        "Payment Processing Fee": (0.02, 0.03),
        "VAT / Tax Remittance":   (0.05, 0.10),
    }

    # Anomaly schedule — business-plausible triggers
    anomaly_days = {
        15: "large_transaction",   # Black Friday batch settlement
        32: "fee_spike",           # Double-11 ad overspend
        47: "refund_wave",         # Product defect recall
        61: "fx_deviation",        # Unauthorized FX conversion
        74: "missing_data",        # ERP migration data gap
        82: "duplicate_entry",     # Accounting system double-booking
    }

    # Anomaly memo — plausible business notes (no "ANOMALY:" labels)
    anomaly_notes = {
        "large_transaction": "Black Friday consolidated settlement — multi-week batch",
        "fee_spike":         "Double-11 campaign — CPC overage approved by marketing",
        "refund_wave":       "Batch refund processing — SKU quality recall batch #QR-2024",
        "fx_deviation":      "Emergency FX conversion — treasury instruction ref TRY-0061",
        "missing_data":      "",   # Simulated as null — ERP migration gap
        "duplicate_entry":   "Reconciliation entry — pending finance review",
    }

    txn_id = 10000
    batch_counter = 0

    for day_offset in range(n_days):
        date = start + timedelta(days=day_offset)
        anomaly = anomaly_days.get(day_offset)

        # Revenue trend: slight growth + weekly seasonality + noise
        trend      = 1 + (day_offset / n_days) * 0.18
        seasonality = 1 + 0.22 * np.sin(2 * np.pi * day_offset / 7)
        noise      = np.random.normal(1.0, 0.07)
        daily_rev  = base_daily_revenue * trend * seasonality * noise

        for platform in platforms:
            ccy  = currencies[platform]
            rate = fx_rates.get(ccy, 1.0)

            rev         = daily_rev * platform_share[platform] * np.random.normal(1.0, 0.05)
            rev_local   = rev / rate
            settle_lag  = 7 if "Amazon" in platform else 3
            settle_date = date + timedelta(days=settle_lag)

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

                # Anomaly: advertising overspend
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

        # ── Anomaly: duplicate entry (accounting double-booking) ──
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
    print(df[["txn_id","date","platform","counterparty","amount_usd","category","note"]].head(12).to_string())
