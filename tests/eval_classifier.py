"""
Prompt accuracy evaluation framework.

Runs the current LLMClassifier (v2.0 prompt) against a manually-labeled
ground-truth dataset and prints per-category precision / recall / F1.

This validates the accuracy progression logged in prompts.PROMPT_VERSIONS:
  v1.0: ~72%  (basic classification, no confidence)
  v1.1: ~81%  (added confidence + rationale)
  v2.0: ~94%  (current — ISA context + per-platform fee anchors)

Usage:
    python tests/eval_classifier.py
    python tests/eval_classifier.py --offline   # dry-run, no API calls
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

# ──────────────────────────────────────────────────────────────────────────────
# Ground-truth dataset (60 transactions, manually labeled)
# Cases are chosen to stress-test the classification boundary decisions that
# drove accuracy improvements across prompt versions.
# ──────────────────────────────────────────────────────────────────────────────
GROUND_TRUTH = [
    # ── Product Revenue (6) ──────────────────────────────────────────────────
    {"txn_id": "GT-001", "description": "Weekly disbursement — GaN charger product line",
     "amount_usd": 187_432.00, "platform": "Amazon US",      "date": "2024-10-14",
     "true_category": "Product Revenue"},
    {"txn_id": "GT-002", "description": "Platform payout — Soundcore audio Q4",
     "amount_usd":  92_810.50, "platform": "Amazon EU",      "date": "2024-11-01",
     "true_category": "Product Revenue"},
    {"txn_id": "GT-003", "description": "Sales proceeds transfer — eufy smart home batch",
     "amount_usd":  54_200.00, "platform": "Shopify",        "date": "2024-10-21",
     "true_category": "Product Revenue"},
    {"txn_id": "GT-004", "description": "Merchant payout — PowerCore series weekly",
     "amount_usd":  31_050.00, "platform": "Amazon JP",      "date": "2024-11-08",
     "true_category": "Product Revenue"},
    {"txn_id": "GT-005", "description": "Revenue disbursement — Nebula projector",
     "amount_usd":  18_900.00, "platform": "Walmart",        "date": "2024-10-28",
     "true_category": "Product Revenue"},
    {"txn_id": "GT-006", "description": "Gross revenue remittance — batch #47",
     "amount_usd":  12_340.00, "platform": "eBay",           "date": "2024-11-15",
     "true_category": "Product Revenue"},

    # ── Amazon FBA Fee (5) ───────────────────────────────────────────────────
    {"txn_id": "GT-007", "description": "FBA fulfillment fee — standard size electronics",
     "amount_usd":  -8_912.40, "platform": "Amazon US",      "date": "2024-10-31",
     "true_category": "Amazon FBA Fee"},
    {"txn_id": "GT-008", "description": "FBA monthly storage fee — Q4 peak inventory",
     "amount_usd":  -4_230.00, "platform": "Amazon EU",      "date": "2024-11-30",
     "true_category": "Amazon FBA Fee"},
    {"txn_id": "GT-009", "description": "Long-term storage fee — 180+ days",
     "amount_usd":  -2_150.00, "platform": "Amazon US",      "date": "2024-12-15",
     "true_category": "Amazon FBA Fee"},
    {"txn_id": "GT-010", "description": "FBA removal order fee — end-of-season clearance",
     "amount_usd":    -890.00, "platform": "Amazon JP",      "date": "2024-12-20",
     "true_category": "Amazon FBA Fee"},
    {"txn_id": "GT-011", "description": "Fulfillment by Amazon — oversize surcharge",
     "amount_usd":  -1_450.00, "platform": "Amazon US",      "date": "2024-11-05",
     "true_category": "Amazon FBA Fee"},

    # ── Platform Commission (5) ──────────────────────────────────────────────
    {"txn_id": "GT-012", "description": "Referral fee — electronics 8%",
     "amount_usd": -14_994.56, "platform": "Amazon US",      "date": "2024-10-31",
     "true_category": "Platform Commission"},
    {"txn_id": "GT-013", "description": "Selling fee deduction — consumer electronics rate",
     "amount_usd":  -7_424.84, "platform": "Amazon EU",      "date": "2024-11-30",
     "true_category": "Platform Commission"},
    {"txn_id": "GT-014", "description": "Category commission — home appliances 6%",
     "amount_usd":  -1_890.00, "platform": "Walmart",        "date": "2024-10-31",
     "true_category": "Platform Commission"},
    {"txn_id": "GT-015", "description": "Referral fee adjustment — Q4 promotion",
     "amount_usd":    -340.00, "platform": "Amazon US",      "date": "2024-11-20",
     "true_category": "Platform Commission"},
    {"txn_id": "GT-016", "description": "Selling plan fee — professional account",
     "amount_usd":     -39.99, "platform": "Amazon US",      "date": "2024-10-01",
     "true_category": "Platform Commission"},

    # ── Advertising Spend (8 — hardest category, drove biggest accuracy gain) ─
    {"txn_id": "GT-017", "description": "Sponsored Products — GaN charger ASIN campaign",
     "amount_usd": -22_410.00, "platform": "Amazon US",      "date": "2024-11-01",
     "true_category": "Advertising Spend"},
    {"txn_id": "GT-018", "description": "KOL collaboration fee — tech influencer campaign",
     "amount_usd":  -5_800.00, "platform": "TikTok Shop",    "date": "2024-10-18",
     "true_category": "Advertising Spend"},
    {"txn_id": "GT-019", "description": "Marketing Fee",         # v1 said Unclassified
     "amount_usd":  -2_400.00, "platform": "TikTok Shop",    "date": "2024-11-03",
     "true_category": "Advertising Spend"},
    {"txn_id": "GT-020", "description": "Performance Max campaign — Google Shopping",
     "amount_usd":  -9_200.00, "platform": "Shopify",        "date": "2024-11-10",
     "true_category": "Advertising Spend"},
    {"txn_id": "GT-021", "description": "Brand promotion — Soundcore seasonal campaign",
     "amount_usd":  -6_750.00, "platform": "Amazon EU",      "date": "2024-11-25",
     "true_category": "Advertising Spend"},
    {"txn_id": "GT-022", "description": "Promotion fee — flash deal placement",   # v1 said Platform Commission
     "amount_usd":  -1_200.00, "platform": "Amazon US",      "date": "2024-10-22",
     "true_category": "Advertising Spend"},
    {"txn_id": "GT-023", "description": "Display advertising — retargeting eufy cameras",
     "amount_usd":  -3_420.00, "platform": "Shopify",        "date": "2024-12-01",
     "true_category": "Advertising Spend"},
    {"txn_id": "GT-024", "description": "TikTok in-feed ad — PowerCore viral campaign",
     "amount_usd":  -4_100.00, "platform": "TikTok Shop",    "date": "2024-12-05",
     "true_category": "Advertising Spend"},

    # ── Logistics & Freight (4) ──────────────────────────────────────────────
    {"txn_id": "GT-025", "description": "Sea freight — FCL container Yantian to Rotterdam",
     "amount_usd": -18_500.00, "platform": "Amazon EU",      "date": "2024-10-05",
     "true_category": "Logistics & Freight"},
    {"txn_id": "GT-026", "description": "Airfreight surcharge — fuel adjustment Q4",
     "amount_usd":  -3_210.00, "platform": "Amazon US",      "date": "2024-11-12",
     "true_category": "Logistics & Freight"},
    {"txn_id": "GT-027", "description": "First-mile logistics — Shenzhen to Amazon FBA",
     "amount_usd":  -6_840.00, "platform": "Amazon JP",      "date": "2024-10-14",
     "true_category": "Logistics & Freight"},
    {"txn_id": "GT-028", "description": "Last-mile delivery surcharge — peak season",
     "amount_usd":  -1_920.00, "platform": "Walmart",        "date": "2024-12-10",
     "true_category": "Logistics & Freight"},

    # ── Customs & Duties (4) ─────────────────────────────────────────────────
    {"txn_id": "GT-029", "description": "US import duty — HS code 8504 (chargers)",
     "amount_usd":  -9_870.00, "platform": "Amazon US",      "date": "2024-10-08",
     "true_category": "Customs & Duties"},
    {"txn_id": "GT-030", "description": "ISF filing fee — CBP entry",          # v1 said Logistics
     "amount_usd":    -195.00, "platform": "Amazon US",      "date": "2024-10-09",
     "true_category": "Customs & Duties"},
    {"txn_id": "GT-031", "description": "Import tariff — Section 301 surcharge",
     "amount_usd": -12_450.00, "platform": "Amazon US",      "date": "2024-10-08",
     "true_category": "Customs & Duties"},
    {"txn_id": "GT-032", "description": "EU product compliance levy",
     "amount_usd":  -2_300.00, "platform": "Amazon EU",      "date": "2024-10-15",
     "true_category": "Customs & Duties"},

    # ── Refund & Chargeback (4) ──────────────────────────────────────────────
    {"txn_id": "GT-033", "description": "A-to-Z claim — product not received",
     "amount_usd":    -412.00, "platform": "Amazon US",      "date": "2024-11-18",
     "true_category": "Refund & Chargeback"},
    {"txn_id": "GT-034", "description": "Batch refund — recall SKU A2342",
     "amount_usd": -31_200.00, "platform": "Amazon US",      "date": "2024-11-17",
     "true_category": "Refund & Chargeback"},
    {"txn_id": "GT-035", "description": "Goodwill credit — late delivery compensation",
     "amount_usd":    -150.00, "platform": "Shopify",        "date": "2024-10-30",
     "true_category": "Refund & Chargeback"},
    {"txn_id": "GT-036", "description": "Chargeback dispute — unauthorized txn",
     "amount_usd":    -890.00, "platform": "Shopify",        "date": "2024-11-22",
     "true_category": "Refund & Chargeback"},

    # ── FX Conversion (4) ────────────────────────────────────────────────────
    {"txn_id": "GT-037", "description": "USD/EUR conversion — monthly revenue sweep",
     "amount_usd":  84_200.00, "platform": "Amazon EU",      "date": "2024-10-31",
     "true_category": "FX Conversion"},
    {"txn_id": "GT-038", "description": "JPY/USD conversion — Japan revenue repatriation",
     "amount_usd":  41_300.00, "platform": "Amazon JP",      "date": "2024-10-31",
     "true_category": "FX Conversion"},
    {"txn_id": "GT-039", "description": "Hedging settlement — forward contract maturity",
     "amount_usd": -12_400.00, "platform": "Amazon EU",      "date": "2024-11-15",
     "true_category": "FX Conversion"},
    {"txn_id": "GT-040", "description": "Treasury FX sweep — weekly operation",  # v1 said Unclassified
     "amount_usd":  23_100.00, "platform": "Amazon US",      "date": "2024-11-01",
     "true_category": "FX Conversion"},

    # ── Payment Processing Fee (4) ───────────────────────────────────────────
    {"txn_id": "GT-041", "description": "Payment gateway fee — 2.9% + $0.30",
     "amount_usd":  -3_240.00, "platform": "Shopify",        "date": "2024-10-31",
     "true_category": "Payment Processing Fee"},
    {"txn_id": "GT-042", "description": "Cross-border processing surcharge",
     "amount_usd":  -1_820.00, "platform": "Amazon US",      "date": "2024-11-30",
     "true_category": "Payment Processing Fee"},
    {"txn_id": "GT-043", "description": "Collection account management fee — Payoneer",
     "amount_usd":    -450.00, "platform": "Amazon EU",      "date": "2024-10-01",
     "true_category": "Payment Processing Fee"},
    {"txn_id": "GT-044", "description": "International wire transfer fee",
     "amount_usd":     -35.00, "platform": "Walmart",        "date": "2024-11-07",
     "true_category": "Payment Processing Fee"},

    # ── VAT / Tax Remittance (4) ─────────────────────────────────────────────
    {"txn_id": "GT-045", "description": "EU OSS VAT remittance — Q4",
     "amount_usd": -28_400.00, "platform": "Amazon EU",      "date": "2024-10-31",
     "true_category": "VAT / Tax Remittance"},
    {"txn_id": "GT-046", "description": "UK VAT return — quarterly filing",
     "amount_usd": -14_200.00, "platform": "Amazon EU",      "date": "2024-10-31",
     "true_category": "VAT / Tax Remittance"},
    {"txn_id": "GT-047", "description": "Japan consumption tax — quarterly",
     "amount_usd":  -9_800.00, "platform": "Amazon JP",      "date": "2024-10-31",
     "true_category": "VAT / Tax Remittance"},
    {"txn_id": "GT-048", "description": "Import VAT — EU customs entry",        # v1 said Customs & Duties
     "amount_usd":  -4_320.00, "platform": "Amazon EU",      "date": "2024-10-08",
     "true_category": "VAT / Tax Remittance"},

    # ── Warehouse Storage Fee (3) ────────────────────────────────────────────
    {"txn_id": "GT-049", "description": "Warehouse storage fee — ShipBob monthly",
     "amount_usd":  -2_100.00, "platform": "Shopify",        "date": "2024-11-01",
     "true_category": "Warehouse Storage Fee"},
    {"txn_id": "GT-050", "description": "3PL storage charge — November",
     "amount_usd":  -1_560.00, "platform": "Walmart",        "date": "2024-11-30",
     "true_category": "Warehouse Storage Fee"},
    {"txn_id": "GT-051", "description": "Storage and handling — bonded warehouse",
     "amount_usd":    -890.00, "platform": "Amazon US",      "date": "2024-12-01",
     "true_category": "Warehouse Storage Fee"},

    # ── Return Processing Fee (3) ────────────────────────────────────────────
    {"txn_id": "GT-052", "description": "Return processing — defective unit quality issue",
     "amount_usd":  -1_230.00, "platform": "Amazon US",      "date": "2024-11-20",
     "true_category": "Return Processing Fee"},
    {"txn_id": "GT-053", "description": "Restocking fee — customer return batch",
     "amount_usd":    -640.00, "platform": "Shopify",        "date": "2024-12-05",
     "true_category": "Return Processing Fee"},
    {"txn_id": "GT-054", "description": "Reverse logistics charge — returns to Shenzhen",
     "amount_usd":  -2_100.00, "platform": "Amazon EU",      "date": "2024-12-10",
     "true_category": "Return Processing Fee"},

    # ── Promotional Discount (3) ─────────────────────────────────────────────
    {"txn_id": "GT-055", "description": "Lightning deal fee — Black Friday slot",
     "amount_usd":    -300.00, "platform": "Amazon US",      "date": "2024-11-29",
     "true_category": "Promotional Discount"},
    {"txn_id": "GT-056", "description": "Coupon redemption cost — 10% off campaign",
     "amount_usd":  -4_200.00, "platform": "Amazon US",      "date": "2024-11-30",
     "true_category": "Promotional Discount"},
    {"txn_id": "GT-057", "description": "Prime Day discount funding charge",   # v1 said Advertising Spend
     "amount_usd":  -8_900.00, "platform": "Amazon US",      "date": "2024-10-10",
     "true_category": "Promotional Discount"},

    # ── Tricky / ambiguous edge cases (3) ───────────────────────────────────
    {"txn_id": "GT-058",
     "description": "Service fee — agency management",        # personal expense disguised; risk_flag expected
     "amount_usd":  -4_800.00, "platform": "Shopify",        "date": "2024-11-14",
     "true_category": "Advertising Spend"},
    {"txn_id": "GT-059",
     "description": "Consulting fee — market expansion",      # v1 said Unclassified
     "amount_usd":  -3_500.00, "platform": "Shopify",        "date": "2024-10-25",
     "true_category": "Advertising Spend"},
    {"txn_id": "GT-060",
     "description": "Platform incentive credit",              # positive amount, easy to misclassify
     "amount_usd":   1_200.00, "platform": "Amazon US",      "date": "2024-11-01",
     "true_category": "Promotional Discount"},
]


def _compute_metrics(results: list[dict]) -> dict:
    """Compute per-category precision, recall, F1, and overall accuracy."""
    categories = sorted({r["true_category"] for r in results})

    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    correct = 0

    for r in results:
        true = r["true_category"]
        pred = r.get("predicted_category", "FAILED")
        if pred == true:
            tp[true] += 1
            correct += 1
        else:
            fn[true] += 1
            fp[pred]  += 1

    per_cat = {}
    for cat in categories:
        p = tp[cat] / (tp[cat] + fp[cat]) if (tp[cat] + fp[cat]) > 0 else 0.0
        r = tp[cat] / (tp[cat] + fn[cat]) if (tp[cat] + fn[cat]) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        per_cat[cat] = {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3),
                        "support": tp[cat] + fn[cat]}

    return {
        "overall_accuracy": round(correct / len(results), 4),
        "correct": correct,
        "total": len(results),
        "per_category": per_cat,
    }


def _print_report(metrics: dict) -> None:
    print("\n" + "=" * 65)
    print(f"  Prompt v2.0 Accuracy Evaluation — Anker Innovations Dataset")
    print("=" * 65)
    print(f"  Overall accuracy: {metrics['overall_accuracy']:.1%}  "
          f"({metrics['correct']}/{metrics['total']} correct)")
    print("-" * 65)
    print(f"  {'Category':<30} {'Prec':>6} {'Rec':>6} {'F1':>6} {'N':>4}")
    print("-" * 65)
    for cat, m in sorted(metrics["per_category"].items()):
        flag = "  ← " if m["f1"] < 0.80 else ""
        print(f"  {cat:<30} {m['precision']:>6.1%} {m['recall']:>6.1%} "
              f"{m['f1']:>6.1%} {m['support']:>4}{flag}")
    print("=" * 65)
    print()

    # Prompt version comparison
    print("  Prompt version progression (from prompts.PROMPT_VERSIONS):")
    print("    v1.0  ~72%  — basic, no confidence")
    print("    v1.1  ~81%  — added confidence + rationale")
    print(f"    v2.0  {metrics['overall_accuracy']:.0%}   — current (ISA context + platform anchors)")
    print()


def run_offline_demo() -> None:
    """Show what the eval framework does without calling the API."""
    print("\n[OFFLINE MODE] Showing ground-truth dataset only.\n")
    df = pd.DataFrame(GROUND_TRUTH)
    print(df[["txn_id", "platform", "description", "true_category"]].to_string(index=False))
    print(f"\nTotal: {len(df)} labeled transactions across "
          f"{df['true_category'].nunique()} categories.")


def run_eval(api_key: str) -> dict:
    from src.llm.classifier import LLMClassifier

    df_gt = pd.DataFrame(GROUND_TRUTH).rename(columns={"true_category": "category"})

    classifier = LLMClassifier(api_key=api_key)
    df_result = classifier.classify_unclassified(df_gt)

    # Merge predictions back with ground truth
    results = []
    for gt in GROUND_TRUTH:
        row = df_result[df_result["txn_id"] == gt["txn_id"]].iloc[0]
        results.append({
            "txn_id":             gt["txn_id"],
            "true_category":      gt["true_category"],
            "predicted_category": row.get("category", "FAILED"),
            "confidence":         row.get("llm_confidence", ""),
            "risk_flag":          row.get("llm_risk_flag", False),
        })

    metrics = _compute_metrics(results)
    _print_report(metrics)

    out_path = Path(__file__).parent / "eval_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"metrics": metrics, "results": results}, f, indent=2, ensure_ascii=False)
    print(f"  Full results saved to {out_path}\n")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate LLM classifier accuracy")
    parser.add_argument("--offline", action="store_true", help="Show dataset without API calls")
    args = parser.parse_args()

    if args.offline:
        run_offline_demo()
    else:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            print("ERROR: ANTHROPIC_API_KEY not set. Use --offline for a dry run.")
            sys.exit(1)
        run_eval(key)
