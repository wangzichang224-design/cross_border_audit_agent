# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse

from audit_multi_agent_rag.audit_rag.pipeline import DEFAULT_CASE, run_audit_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1 audit multi-agent demo.")
    parser.add_argument("--mode", choices=["mock", "autogen"], default="mock", help="mock does not require API key.")
    parser.add_argument("--case", default=DEFAULT_CASE, help="Audit task description.")
    parser.add_argument("--voucher-file", default="", help="Optional voucher CSV path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_audit_pipeline(mode=args.mode, case_description=args.case, voucher_file=args.voucher_file)

    print("Phase 1 demo completed.")
    print(f"Mode: {result.mode}")
    print(f"Vouchers: {len(result.vouchers)}")
    print(f"Findings: {len(result.findings)}")
    print(f"Report: {result.report_path}")


if __name__ == "__main__":
    main()
