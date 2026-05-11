# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import html
import json
import random
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


TWOPLACES = Decimal("0.01")


COA: dict[str, str] = {
    "1002": "银行存款",
    "1122": "应收账款",
    "1221": "其他应收款",
    "1403": "原材料",
    "1405": "库存商品",
    "1601": "固定资产",
    "1602": "累计折旧",
    "2202": "应付账款",
    "2211": "应付职工薪酬",
    "22210101": "应交税费-应交增值税-进项税额",
    "22210102": "应交税费-应交增值税-销项税额",
    "4001": "实收资本",
    "5001": "生产成本",
    "5101": "制造费用",
    "5401": "主营业务成本",
    "560101": "管理费用-工资",
    "560102": "管理费用-折旧费",
    "560103": "管理费用-办公费",
    "560104": "管理费用-咨询费",
    "560201": "销售费用-工资",
    "6001": "主营业务收入",
}


@dataclass
class JournalLine:
    voucher_id: str
    date: str
    event_type: str
    line_no: int
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    summary: str
    counterparty: str
    source_doc_id: str
    notes: str = ""


@dataclass
class VoucherRow:
    voucher_id: str
    date: str
    debit_subject: str
    credit_subject: str
    amount: Decimal
    summary: str
    vendor: str
    attachment: str


@dataclass
class SourceDocument:
    doc_id: str
    doc_type: str
    date: str
    counterparty: str
    amount: Decimal
    tax_rate: str
    related_voucher_id: str
    notes: str
    rendered_file: str = ""


@dataclass
class InventoryMovement:
    date: str
    item_name: str
    movement_type: str
    qty_in: Decimal
    qty_out: Decimal
    qty_balance: Decimal
    amount_in: Decimal
    amount_out: Decimal
    amount_balance: Decimal
    related_voucher_id: str
    notes: str


@dataclass
class GeneratedDataset:
    output_dir: Path
    voucher_file: Path
    journal_file: Path
    source_doc_file: Path
    trial_balance_file: Path
    inventory_file: Path
    documents_dir: Path
    summary_file: Path
    expected_findings_file: Path


class SyntheticAuditDataGenerator:
    def __init__(self, company_name: str, period_start: date, seed: int = 42, profile: str = "audit_training"):
        self.company_name = company_name
        self.period_start = period_start
        self.seed = seed
        self.profile = profile
        self.rng = random.Random(seed)
        self.lines: list[JournalLine] = []
        self.vouchers: list[VoucherRow] = []
        self.documents: list[SourceDocument] = []
        self.inventory_movements: list[InventoryMovement] = []
        self.expected_findings: list[dict] = []
        self.account_totals: dict[str, dict[str, Decimal]] = {}
        self.raw_qty = Decimal("0")
        self.raw_cost = Decimal("0")
        self.fg_qty = Decimal("0")
        self.fg_cost = Decimal("0")
        self.voucher_seq = 1
        self.doc_seq = 1

    def generate(self, project_root: Path) -> GeneratedDataset:
        self._generate_opening_balances()
        self._generate_procurement_cycle()
        self._generate_production_cycle()
        self._generate_sales_cycle()
        self._generate_fixed_asset_cycle()
        if self.profile == "audit_training":
            self._generate_audit_risks()

        self._validate_balanced()
        output_dir = project_root / "output" / "synthetic_data" / self._dataset_folder_name()
        documents_dir = output_dir / "documents"
        output_dir.mkdir(parents=True, exist_ok=True)
        documents_dir.mkdir(parents=True, exist_ok=True)
        voucher_file = output_dir / "vouchers.csv"
        journal_file = output_dir / "journal_entries.csv"
        source_doc_file = output_dir / "source_documents.csv"
        trial_balance_file = output_dir / "trial_balance.csv"
        inventory_file = output_dir / "inventory_movements.csv"
        summary_file = output_dir / "dataset_summary.md"
        expected_findings_file = output_dir / "expected_findings.json"

        self._render_documents(documents_dir)
        self._write_vouchers(voucher_file)
        self._write_journal_entries(journal_file)
        self._write_source_docs(source_doc_file)
        self._write_trial_balance(trial_balance_file)
        self._write_inventory(inventory_file)
        self._write_expected_findings(expected_findings_file)
        self._write_summary(
            project_root,
            summary_file,
            voucher_file,
            journal_file,
            source_doc_file,
            trial_balance_file,
            inventory_file,
            documents_dir,
        )

        return GeneratedDataset(
            output_dir=output_dir,
            voucher_file=voucher_file,
            journal_file=journal_file,
            source_doc_file=source_doc_file,
            trial_balance_file=trial_balance_file,
            inventory_file=inventory_file,
            documents_dir=documents_dir,
            summary_file=summary_file,
            expected_findings_file=expected_findings_file,
        )

    def _generate_opening_balances(self) -> None:
        self._post_entry(
            entry_date=self.period_start,
            event_type="opening_balance",
            summary="设立期初余额",
            counterparty="本公司",
            line_specs=[
                ("1002", Decimal("5000000"), Decimal("0")),
                ("1403", Decimal("600000"), Decimal("0")),
                ("1405", Decimal("500000"), Decimal("0")),
                ("4001", Decimal("0"), Decimal("6100000")),
            ],
            attachment_type="期初余额表",
            include_voucher=False,
        )
        self.raw_qty = Decimal("1000")
        self.raw_cost = Decimal("600000")
        self.fg_qty = Decimal("500")
        self.fg_cost = Decimal("500000")

    def _generate_procurement_cycle(self) -> None:
        self._purchase_raw_materials(self.period_start + timedelta(days=2), "苏州联禾材料有限公司", Decimal("800"), Decimal("620"))
        self._purchase_raw_materials(self.period_start + timedelta(days=8), "常州精工电子材料有限公司", Decimal("600"), Decimal("640"))
        self._pay_supplier(self.period_start + timedelta(days=12), "苏州联禾材料有限公司", Decimal("560480"))

    def _generate_production_cycle(self) -> None:
        self._issue_materials_to_production(self.period_start + timedelta(days=14), Decimal("900"))
        self._accrue_payroll(self.period_start + timedelta(days=20), prod_amount=Decimal("180000"), admin_amount=Decimal("85000"), sales_amount=Decimal("42000"))
        self._record_overhead(self.period_start + timedelta(days=21), "江苏智维能源服务有限公司", Decimal("33900"))
        self._complete_production(self.period_start + timedelta(days=24), Decimal("880"))

    def _generate_sales_cycle(self) -> None:
        self._sell_finished_goods(self.period_start + timedelta(days=26), "上海远望智能科技有限公司", Decimal("520"), Decimal("1650"))
        self._collect_receivable(self.period_start + timedelta(days=29), "上海远望智能科技有限公司", Decimal("969540"))

    def _generate_fixed_asset_cycle(self) -> None:
        self._acquire_fixed_asset(self.period_start + timedelta(days=10), "北京云启科技有限公司", Decimal("650000"))
        self._record_depreciation(self.period_start + timedelta(days=30), Decimal("9587.02"))

    def _generate_audit_risks(self) -> None:
        self._expense_capex_risk(self.period_start + timedelta(days=18), "北京云启科技有限公司", Decimal("1000000"))
        self._large_consulting_fee(self.period_start + timedelta(days=22), "华信咨询有限公司", Decimal("280000"))
        self._employee_loan(self.period_start + timedelta(days=27), "内部员工", Decimal("180000"))

    def _purchase_raw_materials(self, entry_date: date, vendor: str, qty: Decimal, unit_net_price: Decimal) -> None:
        net = quantize(qty * unit_net_price)
        tax = quantize(net * Decimal("0.13"))
        gross = net + tax
        summary = f"采购原材料 {qty} 件"
        voucher_id, doc_id = self._post_entry(
            entry_date=entry_date,
            event_type="purchase_raw_materials",
            summary=summary,
            counterparty=vendor,
            line_specs=[
                ("1403", net, Decimal("0")),
                ("22210101", tax, Decimal("0")),
                ("2202", Decimal("0"), gross),
            ],
            attachment_type="采购合同/增值税专用发票/入库单",
            voucher_debit="原材料",
            voucher_credit="应付账款",
            voucher_amount=gross,
            attachment_notes=f"数量={qty}; 单价(不含税)={unit_net_price}",
        )
        self.raw_qty += qty
        self.raw_cost += net
        self.documents.append(SourceDocument(doc_id, "增值税专用发票", entry_date.isoformat(), vendor, gross, "13%", voucher_id, f"{summary}; 数量={qty}"))
        self._record_inventory(entry_date, "A100 主板原材料", "采购入库", qty_in=qty, qty_out=Decimal("0"), amount_in=net, amount_out=Decimal("0"), voucher_id=voucher_id, notes=vendor)

    def _pay_supplier(self, entry_date: date, vendor: str, amount: Decimal) -> None:
        voucher_id, doc_id = self._post_entry(
            entry_date=entry_date,
            event_type="pay_supplier",
            summary="支付采购货款",
            counterparty=vendor,
            line_specs=[
                ("2202", amount, Decimal("0")),
                ("1002", Decimal("0"), amount),
            ],
            attachment_type="银行回单/付款审批单",
            voucher_debit="应付账款",
            voucher_credit="银行存款",
            voucher_amount=amount,
        )
        self.documents.append(SourceDocument(doc_id, "银行付款回单", entry_date.isoformat(), vendor, amount, "0%", voucher_id, "付款审批流已完成"))

    def _issue_materials_to_production(self, entry_date: date, qty: Decimal) -> None:
        issue_cost = quantize(self.raw_cost * qty / self.raw_qty)
        self._post_entry(
            entry_date=entry_date,
            event_type="issue_materials",
            summary=f"车间领用原材料 {qty} 件",
            counterparty="本公司生产车间",
            line_specs=[
                ("5001", issue_cost, Decimal("0")),
                ("1403", Decimal("0"), issue_cost),
            ],
            attachment_type="领料单/生产工单",
            include_voucher=False,
        )
        self.raw_qty -= qty
        self.raw_cost -= issue_cost
        self._record_inventory(entry_date, "A100 主板原材料", "生产领用", qty_in=Decimal("0"), qty_out=qty, amount_in=Decimal("0"), amount_out=issue_cost, voucher_id="", notes="生产领料")

    def _accrue_payroll(self, entry_date: date, prod_amount: Decimal, admin_amount: Decimal, sales_amount: Decimal) -> None:
        total = prod_amount + admin_amount + sales_amount
        self._post_entry(
            entry_date=entry_date,
            event_type="accrue_payroll",
            summary="计提当月工资",
            counterparty="本公司员工",
            line_specs=[
                ("5001", prod_amount, Decimal("0")),
                ("560101", admin_amount, Decimal("0")),
                ("560201", sales_amount, Decimal("0")),
                ("2211", Decimal("0"), total),
            ],
            attachment_type="工资计提表/考勤汇总表",
            include_voucher=False,
        )

    def _record_overhead(self, entry_date: date, vendor: str, gross: Decimal) -> None:
        net = quantize(gross / Decimal("1.13"))
        tax = gross - net
        self._post_entry(
            entry_date=entry_date,
            event_type="manufacturing_overhead",
            summary="计提车间能耗及辅料费用",
            counterparty=vendor,
            line_specs=[
                ("5101", net, Decimal("0")),
                ("22210101", tax, Decimal("0")),
                ("2202", Decimal("0"), gross),
            ],
            attachment_type="服务合同/增值税专用发票",
            include_voucher=False,
        )

    def _complete_production(self, entry_date: date, qty: Decimal) -> None:
        prod_cost = self._account_debit_total("5001") - self._account_credit_total("5001")
        overhead = self._account_debit_total("5101") - self._account_credit_total("5101")
        transfer_cost = quantize(prod_cost + overhead)
        self._post_entry(
            entry_date=entry_date,
            event_type="complete_production",
            summary=f"完工入库产成品 {qty} 件",
            counterparty="本公司仓库",
            line_specs=[
                ("1405", transfer_cost, Decimal("0")),
                ("5001", Decimal("0"), prod_cost),
                ("5101", Decimal("0"), overhead),
            ],
            attachment_type="完工入库单/成本计算表",
            include_voucher=False,
        )
        self.fg_qty += qty
        self.fg_cost += transfer_cost
        self._record_inventory(entry_date, "FG200 智能控制器", "完工入库", qty_in=qty, qty_out=Decimal("0"), amount_in=transfer_cost, amount_out=Decimal("0"), voucher_id="", notes="完工入库")

    def _sell_finished_goods(self, entry_date: date, customer: str, qty: Decimal, unit_price_net: Decimal) -> None:
        revenue_net = quantize(qty * unit_price_net)
        tax = quantize(revenue_net * Decimal("0.13"))
        gross = revenue_net + tax
        cogs = quantize(self.fg_cost * qty / self.fg_qty)

        voucher_id, doc_id = self._post_entry(
            entry_date=entry_date,
            event_type="sales_revenue",
            summary=f"销售智能控制器 {qty} 件",
            counterparty=customer,
            line_specs=[
                ("1122", gross, Decimal("0")),
                ("6001", Decimal("0"), revenue_net),
                ("22210102", Decimal("0"), tax),
            ],
            attachment_type="销售合同/销项发票/发货单",
            voucher_debit="应收账款",
            voucher_credit="主营业务收入",
            voucher_amount=gross,
            attachment_notes=f"数量={qty}; 单价(不含税)={unit_price_net}",
        )
        self.documents.append(SourceDocument(doc_id, "销售发票", entry_date.isoformat(), customer, gross, "13%", voucher_id, f"销售数量={qty}; 客户签收单已回传"))

        self._post_entry(
            entry_date=entry_date,
            event_type="carry_cogs",
            summary=f"结转销售成本 {qty} 件",
            counterparty=customer,
            line_specs=[
                ("5401", cogs, Decimal("0")),
                ("1405", Decimal("0"), cogs),
            ],
            attachment_type="出库单/成本结转表",
            include_voucher=False,
        )
        self.fg_qty -= qty
        self.fg_cost -= cogs
        self._record_inventory(entry_date, "FG200 智能控制器", "销售出库", qty_in=Decimal("0"), qty_out=qty, amount_in=Decimal("0"), amount_out=cogs, voucher_id=voucher_id, notes=customer)

    def _collect_receivable(self, entry_date: date, customer: str, amount: Decimal) -> None:
        voucher_id, doc_id = self._post_entry(
            entry_date=entry_date,
            event_type="collect_receivable",
            summary="收回客户货款",
            counterparty=customer,
            line_specs=[
                ("1002", amount, Decimal("0")),
                ("1122", Decimal("0"), amount),
            ],
            attachment_type="银行回单/收款通知单",
            voucher_debit="银行存款",
            voucher_credit="应收账款",
            voucher_amount=amount,
        )
        self.documents.append(SourceDocument(doc_id, "银行收款回单", entry_date.isoformat(), customer, amount, "0%", voucher_id, "与销售回款台账可勾稽"))

    def _acquire_fixed_asset(self, entry_date: date, vendor: str, gross: Decimal) -> None:
        net = quantize(gross / Decimal("1.13"))
        tax = gross - net
        voucher_id, doc_id = self._post_entry(
            entry_date=entry_date,
            event_type="acquire_fixed_asset",
            summary="购入财务共享服务器设备",
            counterparty=vendor,
            line_specs=[
                ("1601", net, Decimal("0")),
                ("22210101", tax, Decimal("0")),
                ("1002", Decimal("0"), gross),
            ],
            attachment_type="采购合同/增值税专用发票/验收单",
            voucher_debit="固定资产-电子设备",
            voucher_credit="银行存款",
            voucher_amount=gross,
        )
        self.documents.append(SourceDocument(doc_id, "固定资产验收单", entry_date.isoformat(), vendor, gross, "13%", voucher_id, "设备已到货并验收"))

    def _record_depreciation(self, entry_date: date, amount: Decimal) -> None:
        self._post_entry(
            entry_date=entry_date,
            event_type="depreciation",
            summary="计提当月固定资产折旧",
            counterparty="本公司",
            line_specs=[
                ("560102", amount, Decimal("0")),
                ("1602", Decimal("0"), amount),
            ],
            attachment_type="折旧计提表",
            include_voucher=False,
        )

    def _expense_capex_risk(self, entry_date: date, vendor: str, gross: Decimal) -> None:
        net = quantize(gross / Decimal("1.13"))
        tax = gross - net
        voucher_id, doc_id = self._post_entry(
            entry_date=entry_date,
            event_type="risk_capex_expensed",
            summary="服务器设备采购及安装",
            counterparty=vendor,
            line_specs=[
                ("560103", net, Decimal("0")),
                ("22210101", tax, Decimal("0")),
                ("2202", Decimal("0"), gross),
            ],
            attachment_type="采购合同/增值税专用发票/验收单",
            voucher_debit="管理费用-办公费",
            voucher_credit="应付账款",
            voucher_amount=gross,
        )
        self.documents.append(SourceDocument(doc_id, "增值税专用发票", entry_date.isoformat(), vendor, gross, "13%", voucher_id, "服务器设备采购及安装，达到预定可使用状态"))
        self.expected_findings.append(
            {
                "voucher_id": voucher_id,
                "risk_type": "资本性支出费用化",
                "expected_level": "高",
                "reason": "服务器设备采购及安装应进一步评估是否满足固定资产确认条件。",
            }
        )

    def _large_consulting_fee(self, entry_date: date, vendor: str, gross: Decimal) -> None:
        voucher_id, doc_id = self._post_entry(
            entry_date=entry_date,
            event_type="risk_consulting_fee",
            summary="年度内控咨询服务",
            counterparty=vendor,
            line_specs=[
                ("560104", gross, Decimal("0")),
                ("1002", Decimal("0"), gross),
            ],
            attachment_type="咨询合同/成果报告",
            voucher_debit="管理费用-咨询费",
            voucher_credit="银行存款",
            voucher_amount=gross,
        )
        self.documents.append(SourceDocument(doc_id, "服务合同", entry_date.isoformat(), vendor, gross, "0%", voucher_id, "金额较大，建议核查服务成果与期间归属"))
        self.expected_findings.append(
            {
                "voucher_id": voucher_id,
                "risk_type": "大额咨询费",
                "expected_level": "中",
                "reason": "咨询费金额较大，需检查服务真实性、受益期间和支持性文件。",
            }
        )

    def _employee_loan(self, entry_date: date, employee: str, amount: Decimal) -> None:
        voucher_id, doc_id = self._post_entry(
            entry_date=entry_date,
            event_type="risk_employee_loan",
            summary="项目备用金往来款",
            counterparty=employee,
            line_specs=[
                ("1221", amount, Decimal("0")),
                ("1002", Decimal("0"), amount),
            ],
            attachment_type="付款审批单/借款单",
            voucher_debit="其他应收款-员工借款",
            voucher_credit="银行存款",
            voucher_amount=amount,
        )
        self.documents.append(SourceDocument(doc_id, "员工借款单", entry_date.isoformat(), employee, amount, "0%", voucher_id, "月末未清理"))
        self.expected_findings.append(
            {
                "voucher_id": voucher_id,
                "risk_type": "其他应收款挂账",
                "expected_level": "中",
                "reason": "员工借款期末未归还，需关注真实性、审批与期后回款。",
            }
        )

    def _post_entry(
        self,
        entry_date: date,
        event_type: str,
        summary: str,
        counterparty: str,
        line_specs: list[tuple[str, Decimal, Decimal]],
        attachment_type: str,
        voucher_debit: str = "",
        voucher_credit: str = "",
        voucher_amount: Decimal | None = None,
        attachment_notes: str = "",
        include_voucher: bool = True,
    ) -> tuple[str, str]:
        voucher_id = self._next_voucher_id()
        doc_id = self._next_doc_id()
        debit_total = Decimal("0")
        credit_total = Decimal("0")
        for idx, (account_code, debit, credit) in enumerate(line_specs, start=1):
            debit_q = quantize(debit)
            credit_q = quantize(credit)
            debit_total += debit_q
            credit_total += credit_q
            account_name = COA[account_code]
            self.lines.append(
                JournalLine(
                    voucher_id=voucher_id,
                    date=entry_date.isoformat(),
                    event_type=event_type,
                    line_no=idx,
                    account_code=account_code,
                    account_name=account_name,
                    debit=debit_q,
                    credit=credit_q,
                    summary=summary,
                    counterparty=counterparty,
                    source_doc_id=doc_id,
                    notes=attachment_notes,
                )
            )
            totals = self.account_totals.setdefault(account_code, {"debit": Decimal("0"), "credit": Decimal("0")})
            totals["debit"] += debit_q
            totals["credit"] += credit_q

        if quantize(debit_total - credit_total) != Decimal("0"):
            raise ValueError(f"Unbalanced entry for {voucher_id}: debit={debit_total}, credit={credit_total}")

        if include_voucher:
            self.vouchers.append(
                VoucherRow(
                    voucher_id=voucher_id,
                    date=entry_date.isoformat(),
                    debit_subject=voucher_debit or COA[line_specs[0][0]],
                    credit_subject=voucher_credit or COA[line_specs[-1][0]],
                    amount=quantize(voucher_amount if voucher_amount is not None else max(debit_total, credit_total)),
                    summary=summary,
                    vendor=counterparty,
                    attachment=attachment_type,
                )
            )
        return voucher_id, doc_id

    def _record_inventory(
        self,
        entry_date: date,
        item_name: str,
        movement_type: str,
        qty_in: Decimal,
        qty_out: Decimal,
        amount_in: Decimal,
        amount_out: Decimal,
        voucher_id: str,
        notes: str,
    ) -> None:
        if "原材料" in item_name:
            qty_balance = self.raw_qty
            amount_balance = self.raw_cost
        else:
            qty_balance = self.fg_qty
            amount_balance = self.fg_cost
        self.inventory_movements.append(
            InventoryMovement(
                date=entry_date.isoformat(),
                item_name=item_name,
                movement_type=movement_type,
                qty_in=quantize(qty_in),
                qty_out=quantize(qty_out),
                qty_balance=quantize(qty_balance),
                amount_in=quantize(amount_in),
                amount_out=quantize(amount_out),
                amount_balance=quantize(amount_balance),
                related_voucher_id=voucher_id,
                notes=notes,
            )
        )

    def _validate_balanced(self) -> None:
        total_debit = sum((line.debit for line in self.lines), Decimal("0"))
        total_credit = sum((line.credit for line in self.lines), Decimal("0"))
        if quantize(total_debit - total_credit) != Decimal("0"):
            raise ValueError(f"Trial balance mismatch: debit={total_debit}, credit={total_credit}")

    def _write_vouchers(self, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["voucher_id", "date", "debit_subject", "credit_subject", "amount", "summary", "vendor", "attachment"])
            for item in self.vouchers:
                writer.writerow([item.voucher_id, item.date, item.debit_subject, item.credit_subject, format_decimal(item.amount), item.summary, item.vendor, item.attachment])

    def _write_journal_entries(self, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["voucher_id", "date", "event_type", "line_no", "account_code", "account_name", "debit", "credit", "summary", "counterparty", "source_doc_id", "notes"])
            for line in self.lines:
                writer.writerow(
                    [
                        line.voucher_id,
                        line.date,
                        line.event_type,
                        line.line_no,
                        line.account_code,
                        line.account_name,
                        format_decimal(line.debit),
                        format_decimal(line.credit),
                        line.summary,
                        line.counterparty,
                        line.source_doc_id,
                        line.notes,
                    ]
                )

    def _write_source_docs(self, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["doc_id", "doc_type", "date", "counterparty", "amount", "tax_rate", "related_voucher_id", "notes", "rendered_file"])
            for doc in self.documents:
                writer.writerow([doc.doc_id, doc.doc_type, doc.date, doc.counterparty, format_decimal(doc.amount), doc.tax_rate, doc.related_voucher_id, doc.notes, doc.rendered_file])

    def _write_trial_balance(self, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["account_code", "account_name", "debit_total", "credit_total", "ending_debit_balance", "ending_credit_balance", "actual_direction", "expected_direction"])
            for code in sorted(self.account_totals):
                debit_total = quantize(self.account_totals[code]["debit"])
                credit_total = quantize(self.account_totals[code]["credit"])
                net = quantize(debit_total - credit_total)
                ending_debit = net if net > 0 else Decimal("0")
                ending_credit = -net if net < 0 else Decimal("0")
                actual_direction = "debit" if net > 0 else "credit" if net < 0 else "zero"
                writer.writerow(
                    [
                        code,
                        COA[code],
                        format_decimal(debit_total),
                        format_decimal(credit_total),
                        format_decimal(ending_debit),
                        format_decimal(ending_credit),
                        actual_direction,
                        expected_balance_side_for_account(code),
                    ]
                )

    def _write_inventory(self, path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "item_name", "movement_type", "qty_in", "qty_out", "qty_balance", "amount_in", "amount_out", "amount_balance", "related_voucher_id", "notes"])
            for row in self.inventory_movements:
                writer.writerow(
                    [
                        row.date,
                        row.item_name,
                        row.movement_type,
                        format_decimal(row.qty_in),
                        format_decimal(row.qty_out),
                        format_decimal(row.qty_balance),
                        format_decimal(row.amount_in),
                        format_decimal(row.amount_out),
                        format_decimal(row.amount_balance),
                        row.related_voucher_id,
                        row.notes,
                    ]
                )

    def _write_expected_findings(self, path: Path) -> None:
        payload = {
            "profile": self.profile,
            "company_name": self.company_name,
            "seed": self.seed,
            "expected_findings": self.expected_findings,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_summary(
        self,
        project_root: Path,
        path: Path,
        voucher_file: Path,
        journal_file: Path,
        source_doc_file: Path,
        trial_balance_file: Path,
        inventory_file: Path,
        documents_dir: Path,
    ) -> None:
        total_debit = sum((line.debit for line in self.lines), Decimal("0"))
        total_credit = sum((line.credit for line in self.lines), Decimal("0"))
        voucher_rel = to_project_relative(project_root, voucher_file)
        lines = [
            f"# 模拟账套说明 - {self.company_name}",
            "",
            f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}",
            f"- 生成模式: {self.profile}",
            f"- 随机种子: {self.seed}",
            f"- 记账期间起始: {self.period_start.isoformat()}",
            f"- 记账凭证数: {len(self.vouchers)}",
            f"- 分录行数: {len(self.lines)}",
            f"- 借方合计: {format_decimal(total_debit)}",
            f"- 贷方合计: {format_decimal(total_credit)}",
            "",
            "## 输出文件",
            f"- vouchers.csv: {voucher_file}",
            f"- journal_entries.csv: {journal_file}",
            f"- source_documents.csv: {source_doc_file}",
            f"- trial_balance.csv: {trial_balance_file}",
            f"- inventory_movements.csv: {inventory_file}",
            f"- rendered documents: {documents_dir}",
            "",
            "## 风险设计",
        ]
        if self.expected_findings:
            for item in self.expected_findings:
                lines.append(f"- {item['voucher_id']}: {item['risk_type']} ({item['expected_level']}) - {item['reason']}")
        else:
            lines.append("- clean 模式未注入专项审计风险。")
        lines += [
            "",
            "## 推荐用法",
            "运行审计 Agent:",
            f"python -m audit_multi_agent_rag.cli run --mode mock --voucher-file {voucher_rel}",
            "",
            "生成标准底稿:",
            f"python -m audit_multi_agent_rag.cli workpaper --mode mock --voucher-file {voucher_rel}",
            "",
            "鐩存帴鏌ョ湅妯℃嫙鍗曟嵁:",
            f'explorer "{documents_dir}"',
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _render_documents(self, documents_dir: Path) -> None:
        for doc in self.documents:
            safe_name = safe_filename(f"{doc.doc_id}_{doc.doc_type}")
            output_path = documents_dir / f"{safe_name}.html"
            voucher = next((item for item in self.vouchers if item.voucher_id == doc.related_voucher_id), None)
            output_path.write_text(self._build_document_html(doc, voucher), encoding="utf-8")
            doc.rendered_file = str(output_path)

    def _build_document_html(self, doc: SourceDocument, voucher: VoucherRow | None) -> str:
        attachment = voucher.attachment if voucher else doc.doc_type
        summary = voucher.summary if voucher else doc.notes
        rows = [
            ("单据编号", doc.doc_id),
            ("单据类型", doc.doc_type),
            ("业务日期", doc.date),
            ("往来单位", doc.counterparty),
            ("价税合计", format_decimal(doc.amount)),
            ("税率", doc.tax_rate),
            ("关联凭证", doc.related_voucher_id),
            ("摘要", summary),
            ("附件组合", attachment),
            ("备注", doc.notes),
        ]
        row_html = "\n".join(
            f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>" for label, value in rows
        )
        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"zh-CN\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\" />\n"
            f"  <title>{html.escape(doc.doc_type)} - {html.escape(doc.doc_id)}</title>\n"
            "  <style>\n"
            "    body { font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 24px; color: #222; }\n"
            "    .page { max-width: 860px; margin: 0 auto; border: 1px solid #bbb; padding: 24px 28px; }\n"
            "    h1 { font-size: 24px; margin: 0 0 8px; }\n"
            "    .sub { color: #666; margin-bottom: 16px; }\n"
            "    table { width: 100%; border-collapse: collapse; }\n"
            "    th, td { border: 1px solid #d6d6d6; padding: 10px 12px; text-align: left; vertical-align: top; }\n"
            "    th { width: 180px; background: #f6f8fa; }\n"
            "    .note { margin-top: 18px; padding: 12px 14px; background: #fff9e8; border: 1px solid #f0d98c; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <div class=\"page\">\n"
            f"    <h1>{html.escape(doc.doc_type)}</h1>\n"
            "    <div class=\"sub\">模拟审计训练单据，仅用于 Agent / RAG / 底稿测试</div>\n"
            "    <table>\n"
            f"{row_html}\n"
            "    </table>\n"
            "    <div class=\"note\">本文件为模拟单据，数据可与 vouchers.csv、journal_entries.csv 和 source_documents.csv 勾稽。</div>\n"
            "  </div>\n"
            "</body>\n"
            "</html>\n"
        )

    def _dataset_folder_name(self) -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        return f"{stamp}_{self.profile}"

    def _next_voucher_id(self) -> str:
        value = f"SYN{self.period_start.year}{self.voucher_seq:04d}"
        self.voucher_seq += 1
        return value

    def _next_doc_id(self) -> str:
        value = f"DOC{self.period_start.year}{self.doc_seq:04d}"
        self.doc_seq += 1
        return value

    def _account_debit_total(self, code: str) -> Decimal:
        return self.account_totals.get(code, {}).get("debit", Decimal("0"))

    def _account_credit_total(self, code: str) -> Decimal:
        return self.account_totals.get(code, {}).get("credit", Decimal("0"))


def generate_synthetic_dataset(
    project_root: Path,
    company_name: str = "华东智造科技有限公司",
    period_start: str = "2025-12-01",
    seed: int = 42,
    profile: str = "audit_training",
) -> GeneratedDataset:
    generator = SyntheticAuditDataGenerator(
        company_name=company_name,
        period_start=date.fromisoformat(period_start),
        seed=seed,
        profile=profile,
    )
    return generator.generate(project_root)


def quantize(value: Decimal | str | float | int) -> Decimal:
    return Decimal(str(value)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def format_decimal(value: Decimal) -> str:
    return f"{quantize(value):.2f}"


def normal_side_for_account(code: str) -> str:
    return expected_balance_side_for_account(code)


def expected_balance_side_for_account(code: str) -> str:
    overrides = {
        "1602": "credit",
        "2202": "credit",
        "2211": "credit",
        "22210101": "debit",
        "22210102": "credit",
        "4001": "credit",
        "6001": "credit",
    }
    if code in overrides:
        return overrides[code]
    if code.startswith(("1", "5")):
        return "debit"
    return "credit"


def safe_filename(text: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", text).strip()
    return cleaned[:120] or "document"


def to_project_relative(project_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)
