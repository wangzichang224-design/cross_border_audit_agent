# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path

from audit_multi_agent_rag.audit_rag.config import get_settings
from audit_multi_agent_rag.audit_rag.feishu import serve_feishu_webhook
from audit_multi_agent_rag.audit_rag.pipeline import DEFAULT_CASE, CROSS_BORDER_CASE, AuditPipelineResult, run_audit_pipeline
from audit_multi_agent_rag.audit_rag.rag import AuditKnowledgeBase, format_rag_context
from audit_multi_agent_rag.audit_rag.synthetic_data import generate_synthetic_dataset
from audit_multi_agent_rag.scripts.generate_workpaper import (
    DEFAULT_CURRENCY,
    DEFAULT_GAAP,
    DEFAULT_TEMPLATE_KEYWORD,
    copy_template,
    find_template,
    write_ai_sheet,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit multi-agent RAG command center.")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("where", help="Show project folders and latest outputs.")
    subparsers.add_parser("doctor", help="Check local config, packages, API key, and template folder.")
    subparsers.add_parser("index", help="Build the local ChromaDB knowledge index.")
    subparsers.add_parser("feishu", help="Run the Feishu webhook server.")

    search_parser = subparsers.add_parser("search", help="Search the local audit knowledge base.")
    search_parser.add_argument("--query", required=True, help="Search query.")
    search_parser.add_argument("--top-k", type=int, default=4, help="Number of chunks to return.")

    seed_parser = subparsers.add_parser("seed-data", help="Generate a CAS-aligned synthetic dataset.")
    seed_parser.add_argument("--company-name", default="华东智造科技有限公司", help="Synthetic company name.")
    seed_parser.add_argument("--period-start", default="2025-12-01", help="Accounting period start date (YYYY-MM-DD).")
    seed_parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    seed_parser.add_argument("--profile", choices=["audit_training", "clean"], default="audit_training", help="Dataset profile.")

    run_parser = subparsers.add_parser("run", help="Run the audit agent pipeline and generate a Markdown report.")
    add_common_agent_args(run_parser)

    workpaper_parser = subparsers.add_parser("workpaper", help="Generate a standard Excel workpaper copy.")
    add_common_agent_args(workpaper_parser)
    workpaper_parser.add_argument("--template-root", default="", help="Folder that contains standard SWP templates.")
    workpaper_parser.add_argument("--template-keyword", default=DEFAULT_TEMPLATE_KEYWORD, help="Template filename keyword.")
    workpaper_parser.add_argument("--client-name", default="XYZ公司", help="Client name used in output filename.")
    workpaper_parser.add_argument("--gaap", default=DEFAULT_GAAP, help="GAAP label for the lead sheet.")
    workpaper_parser.add_argument("--currency", default=DEFAULT_CURRENCY, help="Currency label for the lead sheet.")

    return parser


def add_common_agent_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["mock", "autogen"], default="mock", help="mock is free; autogen calls API.")
    parser.add_argument(
        "--case-type",
        choices=["fixed_asset", "cross_border"],
        default="fixed_asset",
        help="Preset audit scenario: fixed_asset (default) or cross_border (e-commerce).",
    )
    parser.add_argument("--case", default="", help="Override audit task description (optional).")
    parser.add_argument("--voucher-file", default="", help="Optional voucher CSV path (overrides case-type default).")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "where"

    if command == "where":
        print_locations()
    elif command == "doctor":
        print_doctor()
    elif command == "index":
        build_local_index()
    elif command == "feishu":
        serve_feishu_webhook()
    elif command == "search":
        search_local_knowledge(query=args.query, top_k=args.top_k)
    elif command == "seed-data":
        generate_seed_data(args.company_name, args.period_start, args.seed, args.profile)
    elif command == "run":
        result = run_audit_pipeline(
            mode=args.mode,
            case_type=args.case_type,
            case_description=args.case,
            voucher_file=args.voucher_file,
        )
        print_pipeline_result(result)
    elif command == "workpaper":
        template_root = resolve_template_root(args.template_root)
        result = run_audit_pipeline(
            mode=args.mode,
            case_type=args.case_type,
            case_description=args.case,
            voucher_file=args.voucher_file,
        )
        template_path = find_template(template_root, args.template_keyword)
        workbook_path = copy_template(template_path, args.client_name, args.mode)
        write_ai_sheet(
            workbook_path=workbook_path,
            case_description=args.case,
            mode=args.mode,
            client_name=args.client_name,
            gaap=args.gaap,
            currency=args.currency,
            vouchers=result.vouchers,
            findings=result.findings,
            rag_chunks=result.rag_chunks,
            turns=result.turns,
            report_path=result.report_path,
        )
        print_pipeline_result(result)
        print(f"Template: {template_path}")
        print(f"Excel workpaper: {workbook_path}")
    else:
        parser.error(f"Unknown command: {command}")


def print_locations() -> None:
    settings = get_settings()
    workpapers_dir = settings.project_root / "output" / "workpapers"
    synthetic_dir = settings.project_root / "output" / "synthetic_data"
    template_root = discover_template_root()

    print("Audit agent project")
    print(f"Project root: {settings.project_root}")
    print(f"Start here: {settings.project_root / 'START_HERE.md'}")
    print(f"README: {settings.project_root / 'README.md'}")
    print(f"Synthetic data guide: {settings.project_root / 'SYNTHETIC_DATA_GUIDE.md'}")
    print(f"Development plan: {settings.project_root / 'DEVELOPMENT_PLAN.md'}")
    print(f"Template plan: {settings.project_root / 'TEMPLATE_INTEGRATION_PLAN.md'}")
    print(f"Sample vouchers: {settings.sample_data_path}")
    print(f"Local knowledge sources: {settings.local_knowledge_dir}")
    print(f"Markdown reports: {settings.reports_dir}")
    print(f"Excel workpapers: {workpapers_dir}")
    print(f"Synthetic datasets: {synthetic_dir}")
    print(f"Detected template root: {template_root or 'Not found. Use --template-root.'}")
    print_latest_files(settings.reports_dir, "*.md", "Latest Markdown reports")
    print_latest_files(workpapers_dir, "*.xlsx", "Latest Excel workpapers")
    print_latest_files(synthetic_dir, "dataset_summary.md", "Latest synthetic datasets")


def print_doctor() -> None:
    settings = get_settings()
    template_root = discover_template_root()
    deps = ["openai", "openpyxl", "pandas", "pypdf", "chromadb", "sentence_transformers", "autogen", "autogen_agentchat"]

    print("Doctor check")
    print(f"Python project root: {settings.project_root}")
    print(f"DeepSeek API key: {'configured' if settings.deepseek_api_key else 'missing'}")
    print(f"DeepSeek base URL: {settings.deepseek_base_url}")
    print(f"LLM model: {settings.llm_model}")
    print(f"Template root: {template_root or 'not found'}")
    print(f"Local knowledge dir: {settings.local_knowledge_dir}")
    print(f"Feishu host: {settings.feishu_host}:{settings.feishu_port}{settings.feishu_path}")
    print(f"Feishu App ID: {'configured' if settings.feishu_app_id else 'missing'}")
    print(f"Feishu App Secret: {'configured' if settings.feishu_app_secret else 'missing'}")
    print(f"Feishu Verification Token: {'configured' if settings.feishu_verification_token else 'missing'}")
    for package in deps:
        status = "installed" if importlib.util.find_spec(package) else "missing"
        print(f"Package {package}: {status}")


def print_pipeline_result(result: AuditPipelineResult) -> None:
    high = sum(1 for f in result.findings if f.risk_level == "高")
    mid = sum(1 for f in result.findings if f.risk_level == "中")
    print("Audit pipeline completed.")
    print(f"Case type : {result.case_type}")
    print(f"Mode      : {result.mode}")
    print(f"Vouchers  : {len(result.vouchers)} records from {result.voucher_path.name}")
    print(f"Findings  : {len(result.findings)} total  (高风险 {high} / 中风险 {mid})")
    print(f"Report    : {result.report_path}")


def generate_seed_data(company_name: str, period_start: str, seed: int, profile: str) -> None:
    settings = get_settings()
    dataset = generate_synthetic_dataset(
        project_root=settings.project_root,
        company_name=company_name,
        period_start=period_start,
        seed=seed,
        profile=profile,
    )
    relative_voucher = dataset.voucher_file.relative_to(settings.project_root)

    print("Synthetic dataset generated.")
    print(f"Profile: {profile}")
    print(f"Output dir: {dataset.output_dir}")
    print(f"Voucher file: {dataset.voucher_file}")
    print(f"Journal entries: {dataset.journal_file}")
    print(f"Source documents: {dataset.source_doc_file}")
    print(f"Rendered documents: {dataset.documents_dir}")
    print(f"Trial balance: {dataset.trial_balance_file}")
    print(f"Inventory movements: {dataset.inventory_file}")
    print(f"Expected findings: {dataset.expected_findings_file}")
    print(f"Summary: {dataset.summary_file}")
    print("Run mock audit:")
    print(f"python -m audit_multi_agent_rag.cli run --mode mock --voucher-file {relative_voucher}")
    print("Generate workpaper:")
    print(f"python -m audit_multi_agent_rag.cli workpaper --mode mock --voucher-file {relative_voucher}")


def build_local_index() -> None:
    settings = get_settings()
    kb = AuditKnowledgeBase([settings.sample_knowledge_dir, settings.local_knowledge_dir], settings.chroma_dir)
    try:
        count = kb.build_chroma_index()
    except Exception as exc:
        print("ChromaDB index was not built.")
        print(f"Reason: {exc}")
        print(f"Sample knowledge dir: {settings.sample_knowledge_dir}")
        print(f"Local knowledge dir: {settings.local_knowledge_dir}")
        print("Install the full RAG dependencies first:")
        print(r"python -m pip install -r audit_multi_agent_rag\requirements.txt")
        return
    print(f"Built ChromaDB audit_rules collection with {count} chunks.")
    print(f"Persist dir: {settings.chroma_dir}")
    print(f"Sample knowledge dir: {settings.sample_knowledge_dir}")
    print(f"Local knowledge dir: {settings.local_knowledge_dir}")


def search_local_knowledge(query: str, top_k: int) -> None:
    settings = get_settings()
    kb = AuditKnowledgeBase([settings.sample_knowledge_dir, settings.local_knowledge_dir], settings.chroma_dir)
    chunks = kb.search(query, top_k=top_k)
    print(f"Query: {query}")
    print(f"Results: {len(chunks)}")
    print(format_rag_context(chunks))


def resolve_template_root(raw: str) -> Path:
    if raw:
        template_root = Path(raw)
    else:
        template_root = discover_template_root()
    if not template_root:
        raise SystemExit("Template root not found. Pass --template-root with your standard workpaper folder.")
    if not template_root.exists():
        raise SystemExit(f"Template root does not exist: {template_root}")
    return template_root


def discover_template_root() -> Path | None:
    env_root = os.getenv("SWP_TEMPLATE_ROOT", "").strip()
    if env_root:
        path = Path(env_root)
        if path.exists():
            return path

    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        return None

    for folder in desktop.iterdir():
        if not folder.is_dir():
            continue
        try:
            has_k1_template = any(path.is_file() and path.name.startswith("K1 SWP") for path in folder.rglob("*.xlsx"))
        except OSError:
            continue
        if has_k1_template:
            return folder
    return None


def print_latest_files(folder: Path, pattern: str, title: str) -> None:
    print(title + ":")
    if not folder.exists():
        print("  none")
        return
    files = sorted(folder.rglob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)[:3]
    if not files:
        print("  none")
        return
    for path in files:
        print(f"  {path}")


if __name__ == "__main__":
    main()
