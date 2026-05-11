"""
Entry point for the Cross-border E-commerce AI Audit Agent.

Usage:
    python main.py                        # Full run with LLM (requires ANTHROPIC_API_KEY)
    python main.py --offline              # Offline demo (no API key needed)
    python main.py --offline --days 30    # Short demo run
"""

import sys

# Force UTF-8 on Windows before any other module (including Rich) is imported,
# so that logging.StreamHandler (stderr) and Rich Console (stdout) share the
# same encoding and Chinese paths / Unicode arrows render correctly.
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from src.agent.orchestrator import AuditAgentOrchestrator


def main():
    parser = argparse.ArgumentParser(
        description="Cross-border E-commerce AI Audit Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --offline               # Demo run, no API key needed
  python main.py --days 90               # Full 90-day audit with LLM
  python main.py --use-existing          # Re-run on previously generated data
        """,
    )
    parser.add_argument("--offline", action="store_true",
                        help="Run without LLM API (skips classification & AI narrative)")
    parser.add_argument("--days", type=int, default=90,
                        help="Number of days to simulate (default: 90)")
    parser.add_argument("--use-existing", action="store_true",
                        help="Use existing raw CSV instead of regenerating")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()],
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    offline = args.offline or not api_key

    if not offline and not api_key:
        print("⚠  ANTHROPIC_API_KEY not set — switching to offline mode.")
        offline = True

    agent = AuditAgentOrchestrator(api_key=api_key, offline_mode=offline)
    results = agent.run(
        use_existing_data=args.use_existing,
        n_days=args.days,
    )

    return 0 if results.get("report_path") else 1


if __name__ == "__main__":
    sys.exit(main())
