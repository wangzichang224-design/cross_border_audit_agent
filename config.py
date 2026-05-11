"""Global configuration for the Cross-border E-commerce Audit Agent."""

import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"

# Streamlit Cloud mounts source code read-only at /mount/src/.
# Fall back to /tmp for any directories we need to write at runtime.
def _writable(path: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.touch()
        probe.unlink()
        return path
    except (OSError, PermissionError):
        alt = Path(tempfile.gettempdir()) / "cross_border_audit" / path.relative_to(BASE_DIR)
        alt.mkdir(parents=True, exist_ok=True)
        return alt

DATA_DIR           = _writable(BASE_DIR / "data")
RAW_DATA_DIR       = _writable(BASE_DIR / "data" / "raw")
PROCESSED_DATA_DIR = _writable(BASE_DIR / "data" / "processed")
REPORTS_DIR        = _writable(BASE_DIR / "reports")

# Anthropic API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"

# DeepSeek API (OpenAI-compatible)
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Audit thresholds
ANOMALY_THRESHOLDS = {
    "single_txn_amount_usd": 50_000,       # Flag transactions > $50K
    "daily_outflow_pct_change": 0.50,       # Flag >50% day-over-day spike
    "collection_days_upper": 45,            # Days Sales Outstanding upper bound
    "fee_rate_upper": 0.20,                 # Suspiciously high fee rate (>20%)
    "refund_rate_upper": 0.15,             # Refund rate >15% is anomalous
    "concentration_risk_pct": 0.60,        # Single platform >60% of revenue
    "fx_deviation_pct": 0.05,             # FX rate deviation >5% from reference
}

# Supported platforms
PLATFORMS = ["Amazon US", "Amazon EU", "TikTok Shop", "Shopify", "eBay", "Walmart"]
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "BRL", "SGD"]

# Transaction categories
TRANSACTION_CATEGORIES = [
    "Product Revenue",
    "Amazon FBA Fee",
    "Platform Commission",
    "Advertising Spend",
    "Logistics & Freight",
    "Customs & Duties",
    "Refund & Chargeback",
    "FX Conversion",
    "Payment Processing Fee",
    "Warehouse Storage Fee",
    "Return Processing Fee",
    "Promotional Discount",
    "VAT / Tax Remittance",
    "Unclassified",
]

# Risk levels
RISK_LEVELS = {
    "LOW": "low",
    "MEDIUM": "medium",
    "HIGH": "high",
    "CRITICAL": "critical",
}
