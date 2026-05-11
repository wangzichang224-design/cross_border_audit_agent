"""
Agent Orchestrator — the "Perceive → Decide → Act" loop.

Pipeline:
  1. PERCEIVE:  Ingest raw data from CSV sources
  2. DECIDE:    Run data quality checks + rule-based anomaly detection
  3. ACT (LLM): Classify ambiguous transactions; generate AI audit findings; write report
"""

import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich import print as rprint

console = Console(highlight=False)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, ANOMALY_THRESHOLDS,
    DEEPSEEK_API_KEY,
    RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR,
)
from src.data_ingestion import generate_transactions, save_raw_data, generate_settlement_schedule
from src.cleaning import DataCleaner
from src.audit import RuleBasedAnomalyDetector
from src.llm import LLMClassifier, LLMAuditAnalyst, DeepSeekClassifier, DeepSeekAuditAnalyst
from src.reporting import ReportGenerator, ReportVisualizer

logger = logging.getLogger(__name__)


class AuditAgentOrchestrator:
    """
    Top-level agent that coordinates all pipeline stages.
    Implements a perceive-decide-act loop with graceful degradation
    if the LLM API is unavailable (demo/offline mode).
    """

    def __init__(self, api_key: str = None, offline_mode: bool = False):
        # Auto-detect provider: explicit key > Anthropic env > DeepSeek env > offline
        if api_key:
            self.api_key = api_key
            self.provider = "anthropic"
        elif ANTHROPIC_API_KEY:
            self.api_key = ANTHROPIC_API_KEY
            self.provider = "anthropic"
        elif DEEPSEEK_API_KEY:
            self.api_key = DEEPSEEK_API_KEY
            self.provider = "deepseek"
        else:
            self.api_key = ""
            self.provider = "none"

        self.offline_mode = offline_mode or (not self.api_key)
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.offline_mode:
            console.print(
                "[yellow][!] Running in OFFLINE MODE -- LLM steps will be skipped.[/yellow]"
            )
        else:
            console.print(f"[cyan][i] LLM provider: {self.provider.upper()}[/cyan]")

    def run(
        self,
        use_existing_data: bool = False,
        n_days: int = 90,
    ) -> dict:
        """Execute the full audit pipeline. Returns a summary dict."""

        console.print(Panel.fit(
            "[bold blue]Cross-border E-commerce AI Audit Agent[/bold blue]\n"
            f"Run ID: {self.run_id}  |  Mode: {'OFFLINE' if self.offline_mode else 'LIVE'}",
            border_style="blue",
        ))

        results = {}

        # ─────────────────────────────────────
        # STAGE 1: Data Ingestion
        # ─────────────────────────────────────
        with console.status("[bold cyan]Stage 1/5: Ingesting raw transaction data...[/bold cyan]"):
            df_raw = self._stage_ingest(use_existing_data, n_days)
            results["raw_count"] = len(df_raw)
            console.print(f"[green]OK Loaded {len(df_raw):,} raw transactions[/green]")

        # ─────────────────────────────────────
        # STAGE 2: Data Cleaning
        # ─────────────────────────────────────
        with console.status("[bold cyan]Stage 2/5: Cleaning & normalizing data...[/bold cyan]"):
            df_clean, quality_report = self._stage_clean(df_raw)
            results["cleaned_count"] = len(df_clean)
            results["quality_stats"] = quality_report.stats
            console.print(f"[green]OK Cleaned {len(df_clean):,} transactions "
                          f"(DQ score: {quality_report.stats.get('completeness_pct', 0):.1f}%)[/green]")

        # Print quality report
        console.print(Panel(quality_report.summary(), title="Data Quality Report", border_style="yellow"))

        # ─────────────────────────────────────
        # STAGE 3: Rule-based Anomaly Detection
        # ─────────────────────────────────────
        with console.status("[bold cyan]Stage 3/5: Running audit rules...[/bold cyan]"):
            findings, detector = self._stage_rule_audit(df_clean)
            results["rule_findings_count"] = len(findings)
            console.print(f"[green]OK Rule engine: {len(findings)} findings[/green]")

        self._print_findings_table(findings)

        # ─────────────────────────────────────
        # STAGE 4: LLM Analysis
        # ─────────────────────────────────────
        if not self.offline_mode:
            with console.status("[bold cyan]Stage 4/6: LLM classification & AI audit analysis...[/bold cyan]"):
                df_clean, ai_audit_result = self._stage_llm_analysis(df_clean, detector)
                results["ai_findings"] = ai_audit_result
                console.print("[green]OK LLM analysis complete[/green]")
            ai_narrative = ai_audit_result.get("summary_narrative", "")

            # ─────────────────────────────────────
            # STAGE 4b: Settlement Reconciliation
            # ─────────────────────────────────────
            with console.status("[bold cyan]Stage 4b/6: Settlement reconciliation...[/bold cyan]"):
                recon_result = self._stage_reconciliation(df_clean)
                results["reconciliation"] = recon_result
                status = recon_result.get("reconciliation_status", "ERROR")
                unreconciled = len(recon_result.get("unreconciled_items", []))
                console.print(
                    f"[green]OK Reconciliation: {status} — "
                    f"{unreconciled} unreconciled item(s)[/green]"
                )
        else:
            console.print("[yellow][!] Stage 4: LLM skipped (offline mode)[/yellow]")
            ai_narrative = "_AI narrative unavailable in offline mode. Set ANTHROPIC_API_KEY to enable._"
            results["ai_findings"] = {}
            results["reconciliation"] = {}

        # ─────────────────────────────────────
        # STAGE 5: Report Generation
        # ─────────────────────────────────────
        with console.status("[bold cyan]Stage 5/6: Generating visualizations & report...[/bold cyan]"):
            report_path = self._stage_report(
                df_clean, findings, ai_narrative, quality_report.stats
            )
            results["report_path"] = report_path
            console.print(f"[green]OK Report saved: {report_path}[/green]")

        # Save processed data
        processed_path = str(PROCESSED_DATA_DIR / f"clean_transactions_{self.run_id}.csv")
        df_clean.to_csv(processed_path, index=False, encoding="utf-8-sig")
        results["processed_data_path"] = processed_path

        # Final summary
        self._print_final_summary(results, findings)
        return results

    # ────────────────────────────────────────────
    # Stage implementations
    # ────────────────────────────────────────────

    def _stage_ingest(self, use_existing: bool, n_days: int) -> pd.DataFrame:
        existing = list(RAW_DATA_DIR.glob("*.csv"))
        if use_existing and existing:
            logger.info(f"Loading existing data: {existing[0]}")
            return pd.read_csv(existing[0])

        df = generate_transactions(n_days=n_days)
        save_raw_data(df, str(RAW_DATA_DIR))
        return df

    def _stage_clean(self, df: pd.DataFrame):
        cleaner = DataCleaner()
        return cleaner.clean(df)

    def _stage_rule_audit(self, df: pd.DataFrame):
        detector = RuleBasedAnomalyDetector(thresholds=ANOMALY_THRESHOLDS)
        findings = detector.run_all_checks(df)
        return findings, detector

    def _make_classifier(self):
        if self.provider == "deepseek":
            return DeepSeekClassifier(api_key=self.api_key)
        return LLMClassifier(api_key=self.api_key, model=CLAUDE_MODEL)

    def _make_analyst(self):
        if self.provider == "deepseek":
            return DeepSeekAuditAnalyst(api_key=self.api_key)
        return LLMAuditAnalyst(api_key=self.api_key, model=CLAUDE_MODEL)

    def _stage_llm_analysis(self, df: pd.DataFrame, detector: RuleBasedAnomalyDetector):
        classifier = self._make_classifier()
        analyst = self._make_analyst()

        # Pre-compute summary from raw df — classifier only adds new columns, no conflict
        summary_json = json.dumps(detector.to_summary_dict(df), indent=2, default=str)

        # Classify and analyze run concurrently (no data dependency between them)
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_classify = executor.submit(classifier.classify_unclassified, df)
            future_analyze = executor.submit(
                analyst.analyze_anomalies,
                summary_json=summary_json,
                thresholds=ANOMALY_THRESHOLDS,
            )
            df = future_classify.result()
            ai_result = future_analyze.result()

        return df, ai_result

    def _stage_reconciliation(self, df: pd.DataFrame) -> dict:
        schedule = generate_settlement_schedule(df)
        analyst = self._make_analyst()
        return analyst.reconcile_settlements(schedule)

    def _stage_report(
        self,
        df: pd.DataFrame,
        findings: list,
        ai_narrative: str,
        quality_stats: dict,
    ) -> str:
        run_reports_dir = REPORTS_DIR / self.run_id
        run_reports_dir.mkdir(parents=True, exist_ok=True)

        # Visualizations
        viz = ReportVisualizer(output_dir=str(run_reports_dir))
        chart_paths = viz.generate_all(df, findings)

        # AI-generated narrative report
        report_gen = ReportGenerator(output_dir=str(run_reports_dir))
        report_path = report_gen.generate(
            df=df,
            findings=findings,
            chart_paths=chart_paths,
            ai_narrative=ai_narrative,
            quality_stats=quality_stats,
        )
        return report_path

    # ────────────────────────────────────────────
    # Display helpers
    # ────────────────────────────────────────────

    def _print_findings_table(self, findings: list):
        if not findings:
            return

        table = Table(title="Rule-Based Audit Findings", show_lines=True, expand=True)
        table.add_column("ID", style="dim", min_width=4, no_wrap=True)
        table.add_column("Risk", min_width=8, no_wrap=True)
        table.add_column("Rule", min_width=18, no_wrap=True)
        table.add_column("Impact (USD)", justify="right", min_width=12, no_wrap=True)
        table.add_column("Description")

        risk_styles = {
            "CRITICAL": "bold red",
            "HIGH": "bold yellow",
            "MEDIUM": "yellow",
            "LOW": "green",
        }
        for f in sorted(findings, key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(x.risk_level, 4)):
            style = risk_styles.get(f.risk_level, "white")
            table.add_row(
                f.finding_id,
                f"[{style}]{f.risk_level}[/{style}]",
                f.rule_name,
                f"${f.amount_impact_usd:,.0f}",
                f.description,
            )
        console.print(table)

    def _print_final_summary(self, results: dict, findings: list):
        from collections import Counter
        counts = Counter(getattr(f, "risk_level", "?") for f in findings)

        console.print(Panel.fit(
            f"[bold green]Audit Pipeline Complete[/bold green]\n\n"
            f"  Raw transactions:    {results.get('raw_count', 0):,}\n"
            f"  Cleaned transactions:{results.get('cleaned_count', 0):,}\n"
            f"  Rule findings:       {results.get('rule_findings_count', 0)} "
            f"([red]{counts.get('CRITICAL',0)} CRITICAL[/red], "
            f"[yellow]{counts.get('HIGH',0)} HIGH[/yellow], "
            f"{counts.get('MEDIUM',0)} MEDIUM, "
            f"[green]{counts.get('LOW',0)} LOW[/green])\n"
            f"  Report:              {results.get('report_path', 'N/A')}",
            border_style="green",
        ))
