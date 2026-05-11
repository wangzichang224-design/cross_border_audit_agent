# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CAPITAL_KEYWORDS = ["设备", "服务器", "机器", "固定资产", "工程", "装修", "硬件", "车辆", "产线"]
EXPENSE_SUBJECTS = ["管理费用", "销售费用", "研发费用", "咨询费", "办公费"]
SENSITIVE_KEYWORDS = ["咨询", "往来款", "关联方", "大额", "暂估", "预付", "其他应收", "其他应付"]
CONSULTING_KEYWORDS = ["咨询", "顾问", "内控", "整改", "实施"]
EMPLOYEE_LOAN_KEYWORDS = ["员工借款", "借款", "备用金", "往来款"]

# Cross-border e-commerce specific keyword sets
CB_RELATED_PARTY_KEYWORDS = ["香港", "BVI", "开曼", "境外子公司", "关联方", "控股股东", "品牌授权", "转让定价"]
CB_FOREX_KEYWORDS = ["汇兑", "汇兑损益", "汇率重估", "即期汇率", "外汇敞口", "外汇头寸", "汇率调整"]
CB_REVENUE_KEYWORDS = ["Amazon", "亚马逊", "TikTok", "Shopee", "eBay", "平台结算", "销售回款", "店铺"]
CB_CUSTOMS_KEYWORDS = ["关税", "海关", "进口", "报关", "完税", "原产地"]
CB_INVENTORY_IMPAIRMENT_KEYWORDS = ["存货跌价", "减值准备", "NRV", "库龄", "滞销", "跌价准备", "净现值"]
CB_RETURN_PROVISION_KEYWORDS = ["退货准备", "预计退货", "退款准备", "预计负债-销售退货"]


@dataclass
class Voucher:
    voucher_id: str
    date: str
    debit_subject: str
    credit_subject: str
    amount: float
    summary: str
    vendor: str = ""
    attachment: str = ""


@dataclass
class Finding:
    voucher_id: str
    risk_level: str
    issue: str
    evidence: str
    suggested_procedure: str


def _to_float(value: str) -> float:
    cleaned = str(value).replace(",", "").strip()
    return float(cleaned or 0)


def load_vouchers(path: Path) -> list[Voucher]:
    if not path.exists():
        raise FileNotFoundError(path)

    rows: list[Voucher] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                Voucher(
                    voucher_id=row.get("voucher_id", ""),
                    date=row.get("date", ""),
                    debit_subject=row.get("debit_subject", ""),
                    credit_subject=row.get("credit_subject", ""),
                    amount=_to_float(row.get("amount", "0")),
                    summary=row.get("summary", ""),
                    vendor=row.get("vendor", ""),
                    attachment=row.get("attachment", ""),
                )
            )
    return rows


def analyze_vouchers(
    vouchers: Iterable[Voucher],
    materiality: float = 500_000,
    consulting_threshold: float = 200_000,
    loan_threshold: float = 50_000,
) -> list[Finding]:
    findings: list[Finding] = []

    for voucher in vouchers:
        summary_text = " ".join(
            text for text in [voucher.summary, voucher.vendor, voucher.attachment, voucher.debit_subject, voucher.credit_subject] if text
        )
        debit_is_expense = any(subject in voucher.debit_subject for subject in EXPENSE_SUBJECTS)
        looks_capital = any(keyword in summary_text for keyword in CAPITAL_KEYWORDS)
        looks_consulting = "咨询费" in voucher.debit_subject or any(keyword in summary_text for keyword in CONSULTING_KEYWORDS)
        looks_employee_loan = "其他应收" in voucher.debit_subject and any(keyword in summary_text for keyword in EMPLOYEE_LOAN_KEYWORDS)
        sensitive_hits = [keyword for keyword in SENSITIVE_KEYWORDS if keyword in summary_text]

        if debit_is_expense and looks_capital and voucher.amount >= materiality:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="高",
                    issue="疑似资本性支出费用化",
                    evidence=(
                        f"{voucher.date} 凭证 {voucher.voucher_id}: 借记 {voucher.debit_subject}, 金额 {voucher.amount:,.2f}, "
                        f"摘要/附件显示与长期资产相关: {summary_text}"
                    ),
                    suggested_procedure="检查合同、发票、验收单和资产使用状态，判断是否应计入固定资产并补提折旧。",
                )
            )
            continue

        if looks_consulting and voucher.amount >= consulting_threshold:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="中",
                    issue="大额咨询费或服务真实性风险",
                    evidence=(
                        f"{voucher.date} 凭证 {voucher.voucher_id}: 借记 {voucher.debit_subject}, 金额 {voucher.amount:,.2f}, "
                        f"摘要/附件: {summary_text}"
                    ),
                    suggested_procedure="核查咨询合同、成果交付、审批流程和受益期间，评估是否存在虚构服务或跨期确认。",
                )
            )
            continue

        if looks_employee_loan and voucher.amount >= loan_threshold:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="中",
                    issue="其他应收款挂账或员工借款未清",
                    evidence=(
                        f"{voucher.date} 凭证 {voucher.voucher_id}: 借记 {voucher.debit_subject}, 金额 {voucher.amount:,.2f}, "
                        f"摘要/附件: {summary_text}"
                    ),
                    suggested_procedure="检查借款审批、用途说明和期后归还情况，评估真实性、合规性及是否存在资金占用。",
                )
            )
            continue

        if debit_is_expense and voucher.amount >= materiality:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="中",
                    issue="大额费用入账需执行截止和性质测试",
                    evidence=f"{voucher.date} 凭证 {voucher.voucher_id}: 借记 {voucher.debit_subject}, 金额 {voucher.amount:,.2f}",
                    suggested_procedure="抽查支持性文件，评价费用性质、受益期间和入账期间。",
                )
            )
            continue

        if sensitive_hits:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="中",
                    issue="出现敏感关键词",
                    evidence=f"{voucher.date} 凭证 {voucher.voucher_id}: 命中关键词 {', '.join(sorted(set(sensitive_hits)))}",
                    suggested_procedure="结合供应商背景、合同内容和审批记录判断是否存在舞弊或关联方风险。",
                )
            )

    return findings


def format_findings(findings: list[Finding]) -> str:
    if not findings:
        return "未在样本凭证中识别出高风险异常。"

    lines = []
    for idx, finding in enumerate(findings, start=1):
        lines.append(
            f"{idx}. [{finding.risk_level}风险] {finding.issue}\n"
            f"   - 凭证: {finding.voucher_id}\n"
            f"   - 证据: {finding.evidence}\n"
            f"   - 建议程序: {finding.suggested_procedure}"
        )
    return "\n".join(lines)


def analyze_cross_border_vouchers(
    vouchers: Iterable[Voucher],
    materiality: float = 500_000,
    related_party_threshold: float = 300_000,
    inventory_impairment_threshold: float = 200_000,
    forex_threshold: float = 30_000,
    revenue_threshold: float = 200_000,
) -> list[Finding]:
    """Detect audit risks specific to cross-border e-commerce companies."""
    findings: list[Finding] = []

    for voucher in vouchers:
        summary_text = " ".join(
            text for text in [voucher.summary, voucher.vendor, voucher.attachment, voucher.debit_subject, voucher.credit_subject] if text
        )

        is_related_party = any(kw in summary_text for kw in CB_RELATED_PARTY_KEYWORDS)
        is_forex = any(kw in summary_text for kw in CB_FOREX_KEYWORDS) and "财务费用" in voucher.debit_subject
        is_ecommerce_revenue = (
            any(kw in summary_text for kw in CB_REVENUE_KEYWORDS)
            and ("主营业务收入" in voucher.credit_subject or "应收账款" in voucher.debit_subject)
        )
        is_customs = any(kw in summary_text for kw in CB_CUSTOMS_KEYWORDS)
        is_inventory_impairment = any(kw in summary_text for kw in CB_INVENTORY_IMPAIRMENT_KEYWORDS)
        is_return_provision = any(kw in summary_text for kw in CB_RETURN_PROVISION_KEYWORDS)

        # HIGH: Related party cross-border service fee — transfer pricing & BEPS risk
        if is_related_party and voucher.amount >= related_party_threshold:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="高",
                    issue="跨境关联方交易 — 转让定价及BEPS合规风险",
                    evidence=(
                        f"{voucher.date} 凭证 {voucher.voucher_id}: 借记 {voucher.debit_subject}, "
                        f"金额 {voucher.amount:,.2f}, 对手方/摘要涉及境外关联方: {summary_text}"
                    ),
                    suggested_procedure=(
                        "1. 获取跨境服务协议, 核查服务内容、定价依据及实际交付成果;\n"
                        "   2. 审阅独立转让定价报告, 验证收费标准是否符合独立交易原则(Arm's Length);\n"
                        "   3. 核查是否已按税法要求在年度企业所得税申报表中进行关联交易披露;\n"
                        "   4. 评估是否存在BEPS第13号行动计划(主体文档/本地文档)合规义务。"
                    ),
                )
            )
            continue

        # HIGH: Inventory impairment over threshold — NRV methodology challenge
        if is_inventory_impairment and voucher.amount >= inventory_impairment_threshold:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="高",
                    issue="跨境仓库存货减值 — NRV评估方法及充分性存疑",
                    evidence=(
                        f"{voucher.date} 凭证 {voucher.voucher_id}: 借记 {voucher.debit_subject}, "
                        f"金额 {voucher.amount:,.2f}, 摘要: {summary_text}"
                    ),
                    suggested_procedure=(
                        "1. 获取库龄分析明细及ASIN级别销售数据, 验证滞销品认定标准的一致性;\n"
                        "   2. 重新计算NRV(估计售价 - 估计销售费用), 评估管理层假设的合理性;\n"
                        "   3. 比对前期减值计提情况及期后实际处置价格, 测试估计的准确性;\n"
                        "   4. 关注FBA平台库存与账面库存是否一致, 实施跨平台数据核对程序。"
                    ),
                )
            )
            continue

        # MEDIUM: Multi-platform e-commerce revenue — recognition timing
        if is_ecommerce_revenue and voucher.amount >= revenue_threshold:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="中",
                    issue="跨境电商平台收入 — 确认时点与汇率折算准确性风险",
                    evidence=(
                        f"{voucher.date} 凭证 {voucher.voucher_id}: 贷记 {voucher.credit_subject}, "
                        f"金额 {voucher.amount:,.2f}, 平台/摘要: {summary_text}"
                    ),
                    suggested_procedure=(
                        "1. 核查收入确认政策: 是否按控制权转移时点(货物出境/买家签收)确认, 而非平台结算日;\n"
                        "   2. 验证折算汇率选用(交易日即期汇率 vs. 平均汇率), 抽查具体单据核对计算准确性;\n"
                        "   3. 获取平台Sales Report与账面收入逐月核对, 测试截止日前后是否存在跨期入账;\n"
                        "   4. 评估平台结算回款与应收账款账龄是否匹配, 核查是否存在长期未收款异常。"
                    ),
                )
            )
            continue

        # MEDIUM: Foreign exchange — methodology consistency
        if is_forex and voucher.amount >= forex_threshold:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="中",
                    issue="外汇损益 — 汇率折算政策一致性及敞口管理风险",
                    evidence=(
                        f"{voucher.date} 凭证 {voucher.voucher_id}: 借记 {voucher.debit_subject}, "
                        f"金额 {voucher.amount:,.2f}, 摘要: {summary_text}"
                    ),
                    suggested_procedure=(
                        "1. 核查外汇折算会计政策是否与前期一致, 期末重估汇率是否采用资产负债表日即期汇率;\n"
                        "   2. 复算外汇损益金额: 外汇敞口余额 × (期末汇率 - 期初/交易汇率);\n"
                        "   3. 获取银行对账单及外汇头寸明细, 评估USD/EUR等主要货币敞口集中度;\n"
                        "   4. 询问管理层是否存在套期保值安排, 若有则审阅套期文件及有效性测试。"
                    ),
                )
            )
            continue

        # MEDIUM: Customs duties — import compliance
        if is_customs and voucher.amount >= 50_000:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="中",
                    issue="进口关税及增值税 — 税率适用及进项税额抵扣合规性",
                    evidence=(
                        f"{voucher.date} 凭证 {voucher.voucher_id}: 借记 {voucher.debit_subject}, "
                        f"金额 {voucher.amount:,.2f}, 摘要: {summary_text}"
                    ),
                    suggested_procedure=(
                        "1. 核查进口报关单、完税证明与账面入账金额是否一致;\n"
                        "   2. 验证HS编码对应税率是否正确, 是否存在错误归类导致少缴关税的风险;\n"
                        "   3. 检查进口增值税是否已按规定申报抵扣, 进项税额与完税证明金额核对;\n"
                        "   4. 确认原产地证书的有效性及是否享受自贸协定优惠税率。"
                    ),
                )
            )
            continue

        # LOW-MEDIUM: Return provision — estimation basis
        if is_return_provision and voucher.amount >= 50_000:
            findings.append(
                Finding(
                    voucher_id=voucher.voucher_id,
                    risk_level="中",
                    issue="销售退货准备 — 估计基础合理性及会计政策一致性",
                    evidence=(
                        f"{voucher.date} 凭证 {voucher.voucher_id}: 借记 {voucher.debit_subject}, "
                        f"金额 {voucher.amount:,.2f}, 摘要: {summary_text}"
                    ),
                    suggested_procedure=(
                        "1. 获取退货率统计数据, 验证历史退货率假设是否基于充足的历史数据且按平台/品类分层;\n"
                        "   2. 核查退货准备计提基数(当期销售额)与收入确认时点的一致性;\n"
                        "   3. 测试前期退货准备估计的准确性: 期初余额 vs. 实际退货发生额;\n"
                        "   4. 评估跨境退货的特殊性(关税退税、物流成本、跨境退货周期)是否已纳入估计模型。"
                    ),
                )
            )

    return findings
