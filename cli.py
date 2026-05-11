# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path

from audit_rag.config import get_settings
from audit_rag.feishu import serve_feishu_webhook
from audit_rag.pipeline import DEFAULT_CASE, CROSS_BORDER_CASE, AuditPipelineResult, run_audit_pipeline
from audit_rag.rag import AuditKnowledgeBase, format_rag_context
from audit_rag.synthetic_data import generate_synthetic_dataset
from scripts.generate_workpaper import (
    CASE_TYPE_DEFAULTS,
    DEFAULT_CURRENCY,
    DEFAULT_GAAP,
    DEFAULT_TEMPLATE_KEYWORD,
    copy_template,
    find_template,
    write_ai_sheet,
    _build_cash_output_path,
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
    workpaper_parser.add_argument(
        "--template-keyword",
        default="",
        help="Template filename keyword. Defaults to the keyword for the chosen --case-type.",
    )
    workpaper_parser.add_argument("--client-name", default="XYZ公司", help="Client name (fixed_asset/cross_border only).")
    workpaper_parser.add_argument("--gaap", default=DEFAULT_GAAP, help="GAAP label (fixed_asset/cross_border only).")
    workpaper_parser.add_argument("--currency", default=DEFAULT_CURRENCY, help="Currency label (fixed_asset/cross_border only).")
    workpaper_parser.add_argument(
        "--materials-dir",
        default="",
        help="For --case-type=cash: path to benchmarks/materials/case_xxx/.",
    )

    # ── paysim ──────────────────────────────────────────────────────────
    paysim_parser = subparsers.add_parser("paysim", help="PaySim dataset conversion and evaluation.")
    paysim_sub = paysim_parser.add_subparsers(dest="paysim_cmd")

    conv = paysim_sub.add_parser("convert", help="Convert PaySim CSV to audit voucher CSVs.")
    conv.add_argument("--phase", type=int, choices=[1, 2, 3], help="Run one phase only (default: all).")
    conv.add_argument("--force", action="store_true", help="Overwrite existing output files.")

    prun = paysim_sub.add_parser("run", help="Run audit agent on a PaySim voucher CSV.")
    prun.add_argument("--phase", type=int, choices=[1, 2, 3], default=1)
    prun.add_argument("--sample", type=int, default=100, help="Randomly sample N rows from the phase CSV.")
    prun.add_argument("--mode", choices=["mock", "autogen"], default="mock")
    prun.add_argument("--seed", type=int, default=42)

    peval = paysim_sub.add_parser("eval", help="Run agent + compare findings to fraud labels (precision/recall).")
    peval.add_argument("--phase", type=int, choices=[1, 2, 3], default=3)
    peval.add_argument("--sample", type=int, default=200, help="Randomly sample N rows from the phase CSV.")
    peval.add_argument("--mode", choices=["mock", "autogen"], default="mock")
    peval.add_argument("--seed", type=int, default=42)

    return parser


def add_common_agent_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["mock", "autogen"], default="mock", help="mock is free; autogen calls API.")
    parser.add_argument(
        "--case-type",
        choices=["fixed_asset", "cross_border", "cash"],
        default="fixed_asset",
        help="Audit scenario. 'fixed_asset' and 'cross_border' use the agent pipeline."
        " 'cash' uses the Phase 1 benchmark filler and requires --materials-dir.",
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
        if args.case_type == "cash":
            _run_cli_cash_workpaper(args)
        else:
            _run_cli_pipeline_workpaper(args)
    elif command == "paysim":
        paysim_cmd = getattr(args, "paysim_cmd", None) or "convert"
        if paysim_cmd == "convert":
            paysim_convert(phase=args.phase, force=args.force)
        elif paysim_cmd == "run":
            paysim_run(phase=args.phase, sample_n=args.sample, mode=args.mode, seed=args.seed)
        elif paysim_cmd == "eval":
            paysim_eval(phase=args.phase, sample_n=args.sample, mode=args.mode, seed=args.seed)
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


def _run_cli_pipeline_workpaper(args: argparse.Namespace) -> None:
    """Legacy workpaper path: run the audit pipeline, then write the AI sheet
    into a copy of the K1 固定资产 / cross-border template."""
    template_root = resolve_template_root(args.template_root)
    template_keyword = args.template_keyword or DEFAULT_TEMPLATE_KEYWORD
    result = run_audit_pipeline(
        mode=args.mode,
        case_type=args.case_type,
        case_description=args.case,
        voucher_file=args.voucher_file,
    )
    template_path = find_template(template_root, template_keyword)
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


def _run_cli_cash_workpaper(args: argparse.Namespace) -> None:
    """Phase 1 cash workpaper path: read benchmarks/materials/case_xxx/
    fixtures and fill a copy of the neutral C cash workpaper template via the
    rule-based filler. Skips the audit pipeline entirely.
    """
    if not args.materials_dir:
        raise SystemExit("--case-type=cash requires --materials-dir <path>")

    # Lazy import — keep startup fast for users who never touch benchmarks.
    from benchmarks.agent.cash_workpaper_filler import fill_cash_workpaper
    from benchmarks.agent.materials_loader import load_case_materials

    materials_dir = Path(args.materials_dir)
    if not materials_dir.is_dir():
        raise SystemExit(f"--materials-dir does not exist: {materials_dir}")

    template_root = resolve_template_root(args.template_root)
    template_keyword = args.template_keyword or CASE_TYPE_DEFAULTS["cash"]["template_keyword"]
    template_path = find_template(template_root, template_keyword)

    # Fail-fast load so schema errors surface before we touch the template.
    materials = load_case_materials(materials_dir)
    output_path = _build_cash_output_path(template_path, materials.meta.client_name, materials.meta.case_id)

    llm_enhance = args.mode == "autogen"
    fill_cash_workpaper(materials_dir, template_path, output_path, llm_enhance=llm_enhance)

    print("Cash workpaper generated.")
    print(f"Case ID  : {materials.meta.case_id}")
    print(f"Client   : {materials.meta.client_name}")
    print(f"Period   : {materials.meta.period_end}")
    print(f"Template : {template_path}")
    print(f"Materials: {materials_dir}")
    print(f"LLM      : {'enabled' if llm_enhance else 'disabled'}")
    print(f"Output   : {output_path}")


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


# ──────────────────────────────────────────────────────────────────────────────
# PaySim data paths
# ──────────────────────────────────────────────────────────────────────────────

PAYSIM_VOUCHER_DIR = Path(__file__).resolve().parents[0] / "data" / "paysim" / "vouchers"

_PHASE_FILENAMES = {
    1: "phase1_fraud_focus.csv",
    2: "phase2_stress_sample.csv",
    3: "phase3_balanced.csv",
}


# ──────────────────────────────────────────────────────────────────────────────
# PaySim handlers
# ──────────────────────────────────────────────────────────────────────────────


def paysim_convert(phase: int | None, force: bool) -> None:
    import pandas as pd

    paysim_csv = PAYSIM_VOUCHER_DIR.parent / "PS_20174392719_1491204439457_log.csv"
    if not paysim_csv.exists():
        raise SystemExit(
            f"PaySim CSV not found at {paysim_csv}\n"
            "Download with: kaggle datasets download -d ealaxi/paysim1 "
            "-p data/paysim --unzip"
        )

    PAYSIM_VOUCHER_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Loading {paysim_csv.name} ...")
    df = pd.read_csv(paysim_csv)

    targets = [phase] if phase else [1, 2, 3]
    for num in targets:
        filename = _PHASE_FILENAMES[num]
        labels_filename = filename.replace(".csv", "_labels.csv")
        out_path = PAYSIM_VOUCHER_DIR / filename
        labels_path = PAYSIM_VOUCHER_DIR / labels_filename

        if out_path.exists() and not force:
            print(f"[Phase {num}] Already exists, skip (use --force to overwrite): {out_path.name}")
            continue

        # Build the sampler inline (no depends on paysim_to_vouchers.py)
        rng = __import__("numpy").random.RandomState(42)
        if num == 1:
            fraud = df[df["isFraud"] == 1]
            normal = df[df["isFraud"] == 0].sample(n=500, random_state=42)
            sample = pd.concat([fraud, normal]).sample(frac=1, random_state=42).reset_index(drop=True)
        elif num == 2:
            sample = df.sample(frac=0.01, random_state=42).reset_index(drop=True)
        else:
            fraud = df[df["isFraud"] == 1]
            normal = df[df["isFraud"] == 0].sample(n=len(fraud), random_state=42)
            sample = pd.concat([fraud, normal]).sample(frac=1, random_state=42).reset_index(drop=True)

        vouchers, labels = _paysim_transform(sample)
        vouchers.to_csv(out_path, index=False, encoding="utf-8-sig")
        labels.to_csv(labels_path, index=False, encoding="utf-8-sig")

        print(f"[Phase {num}] Vouchers : {len(vouchers)} rows -> {out_path}")
        print(f"          Labels   : {len(labels)} rows -> {labels_path}")
        print(f"          Fraud    : {labels['is_fraud'].sum()} / {len(labels)}")


def paysim_run(phase: int, sample_n: int, mode: str, seed: int) -> None:
    import tempfile

    import pandas as pd

    voucher_path = PAYSIM_VOUCHER_DIR / _PHASE_FILENAMES[phase]
    if not voucher_path.exists():
        raise SystemExit(f"Phase {phase} CSV not found. Run: python -m audit_rag.cli paysim convert --phase {phase}")

    df = pd.read_csv(voucher_path)
    sample = df.sample(n=min(sample_n, len(df)), random_state=seed)

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8-sig") as f:
        sample.to_csv(f, index=False)
        tmp_path = f.name

    result = run_audit_pipeline(mode=mode, case_type="cross_border", voucher_file=tmp_path)
    print_pipeline_result(result)
    Path(tmp_path).unlink(missing_ok=True)


def paysim_eval(phase: int, sample_n: int, mode: str, seed: int) -> None:
    import tempfile

    import pandas as pd

    voucher_path = PAYSIM_VOUCHER_DIR / _PHASE_FILENAMES[phase]
    labels_path = PAYSIM_VOUCHER_DIR / _PHASE_FILENAMES[phase].replace(".csv", "_labels.csv")

    if not voucher_path.exists() or not labels_path.exists():
        raise SystemExit(f"Phase {phase} files not found. Run: python -m audit_rag.cli paysim convert --phase {phase}")

    vouchers_df = pd.read_csv(voucher_path)
    labels_df = pd.read_csv(labels_path)

    sampled_ids = vouchers_df["voucher_id"].sample(n=min(sample_n, len(vouchers_df)), random_state=seed).tolist()
    sample_vouchers = vouchers_df[vouchers_df["voucher_id"].isin(sampled_ids)]
    sample_labels = labels_df[labels_df["voucher_id"].isin(sampled_ids)]

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8-sig") as f:
        sample_vouchers.to_csv(f, index=False)
        tmp_path = f.name

    result = run_audit_pipeline(mode=mode, case_type="cross_border", voucher_file=tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    flagged_ids = {f.voucher_id for f in result.findings}
    fraud_ids = set(sample_labels[sample_labels["is_fraud"] == 1]["voucher_id"])

    tp = len(flagged_ids & fraud_ids)
    fp = len(flagged_ids - fraud_ids)
    fn = len(fraud_ids - flagged_ids)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print_pipeline_result(result)
    print()
    print("=== PaySim Evaluation ===")
    print(f"Sample     : {len(sampled_ids)} vouchers  (fraud: {len(fraud_ids)}, normal: {len(sampled_ids) - len(fraud_ids)})")
    print(f"Agent flagged: {len(flagged_ids)} vouchers")
    print(f"TP={tp}  FP={fp}  FN={fn}")
    print(f"Precision  : {precision:.2%}")
    print(f"Recall     : {recall:.2%}")
    print(f"F1         : {f1:.2%}")


def _paysim_transform(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inline PaySim→voucher transform (no depends on paysim_to_vouchers.py)."""
    import hashlib
    from datetime import datetime, timedelta

    import pandas as pd  # noqa: F811 — already imported at function scope

    def _pick(pool, seed_str):
        idx = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % len(pool)
        return pool[idx]

    BASE_DATE = datetime(2025, 1, 1)
    PLATFORM_VENDORS = [
        "亚马逊全球销售有限公司", "TikTok电商有限公司",
        "Shopee电商(新加坡)有限公司", "eBay国际销售平台",
    ]
    RELATED_PARTY_VENDORS = [
        "深圳跨境通(香港)有限公司", "Cross-Border Trading (BVI) Ltd.",
        "开曼群岛CrossTech控股有限公司",
    ]
    CUSTOMS_VENDORS = ["中国海关-深圳关区", "中国海关-广州关区", "中国海关-上海关区"]
    BANK_VENDORS = ["中国银行深圳分行", "招商银行深圳分行", "建设银行广州分行"]

    records = []
    for _, row in df.iterrows():
        t = row["type"]
        amount = round(float(row["amount"]), 2)
        is_fraud = int(row["isFraud"]) == 1
        dest_is_merchant = str(row["nameDest"]).startswith("M")
        is_large = amount >= 500_000

        if t == "TRANSFER" and dest_is_merchant:
            category = "platform_fee"
        elif t == "TRANSFER" and is_large:
            category = "related_party"
        elif t == "TRANSFER":
            category = "revenue"
        elif t == "CASH_OUT" and is_large:
            category = "related_party"
        elif t == "CASH_OUT":
            category = "platform_fee"
        elif t == "CASH_IN":
            category = "cash_in"
        elif t == "PAYMENT":
            category = "customs"
        else:
            category = "forex"

        debit_map = {
            "revenue": "应收账款-平台结算款",
            "platform_fee": "销售费用-平台服务费",
            "related_party": "管理费用-关联方服务费",
            "customs": "税金及附加",
            "forex": "财务费用-汇兑损益",
            "cash_in": "银行存款",
        }
        credit_map = {
            "revenue": "主营业务收入",
            "platform_fee": "银行存款",
            "related_party": "应付账款-关联方",
            "customs": "应交税费-进口关税及增值税",
            "forex": "应收账款-平台结算款",
            "cash_in": "主营业务收入",
        }

        if category == "revenue":
            vendor = _pick(PLATFORM_VENDORS, row["nameDest"])
        elif category == "related_party":
            vendor = _pick(RELATED_PARTY_VENDORS, row["nameDest"])
        elif category == "customs":
            vendor = _pick(CUSTOMS_VENDORS, row["nameOrig"])
        elif category == "platform_fee":
            vendor = _pick(PLATFORM_VENDORS, row["nameDest"])
        else:
            vendor = _pick(BANK_VENDORS, row["nameOrig"])

        if is_fraud and t in {"TRANSFER", "CASH_OUT"}:
            fraud_pool = {
                "TRANSFER": [
                    "向境外关联方转账-香港子公司大额往来款(疑似利润转移)",
                    "关联方跨境资金划转-开曼控股公司股东借款",
                    "境外关联方管理服务费-转让定价依据不明",
                ],
                "CASH_OUT": [
                    "大额咨询费-境外顾问公司(无合同支撑)",
                    "境外暂估付款-关联供应商发票缺失",
                    "海外佣金支出-收款方为BVI离岸公司",
                ],
            }
            summary = _pick(fraud_pool[t], row["nameOrig"])
        else:
            summary_templates = {
                "revenue": f"{_pick(PLATFORM_VENDORS, row['nameDest'])}店铺销售结算款",
                "platform_fee": f"平台FBA仓储配送及服务费(USD {amount/7.12:.0f} @ 7.12)",
                "related_party": f"向关联方支付年度管理及技术服务费(金额{amount:,.0f}元)",
                "customs": f"进口消费电子零部件关税及增值税(完税金额{amount:,.0f}元)",
                "forex": "期末USD应收账款汇率重估汇兑损益(期末汇率7.10)",
                "cash_in": "跨境平台销售款项入账(结算周期T+3)",
            }
            summary = summary_templates.get(category, "业务往来款")

        records.append({
            "date": (BASE_DATE + timedelta(hours=int(row["step"]))).strftime("%Y-%m-%d"),
            "debit_subject": debit_map[category],
            "credit_subject": credit_map[category],
            "amount": amount,
            "summary": summary,
            "vendor": vendor,
            "attachment": "",
            "_is_fraud": is_fraud,
        })

    out = pd.DataFrame(records)
    ids = [f"V2025-PS-{i+1:05d}" for i in range(len(out))]
    out.insert(0, "voucher_id", ids)
    labels = out[["voucher_id", "_is_fraud"]].rename(columns={"_is_fraud": "is_fraud"}).copy()
    vouchers = out.drop(columns=["_is_fraud"], errors="ignore")
    return vouchers, labels


if __name__ == "__main__":
    main()
