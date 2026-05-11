# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from .config import Settings, build_llm_config
from .data_tools import Finding, format_findings
from .rag import RetrievedChunk, format_rag_context


DATA_EXTRACTOR_PROMPT = """你是 Data_Extractor，一名资深审计助理。
职责:
1. 使用 Python/Pandas/审计抽样思维处理凭证、Excel、PDF 证据。
2. 识别异常金额、异常科目、敏感关键词，例如咨询费、往来款、大额采购、固定资产、设备。
3. 输出必须包含: 发现、证据、潜在错报方向、下一步审计程序。
限制:
- 不直接下最终审计意见。
- 不编造准则条文。
"""


COMPLIANCE_CHECKER_PROMPT = """你是 Compliance_Checker，技术部合规专家。
职责:
1. 结合 RAG 检索到的审计准则、CPA 教材和企业会计准则片段进行合规分析。
2. 必须引用检索依据编号，例如 [依据 1]。
3. 判断是否涉及资本性支出费用化、重大错报风险、截止/分类/列报风险。
限制:
- 如果检索依据不足，必须说明"依据不足，需要补充官方准则原文"。
- 不得凭空编造条款。
"""


AUDIT_PARTNER_PROMPT = """你是 Audit_Partner，签字合伙人。
职责:
1. 对 Data_Extractor 和 Compliance_Checker 的结论进行质疑。
2. 识别证据链缺口、金额重要性、舞弊风险和管理层动机。
3. 给出最终审计意见和需要追加的审计程序。
输出风格:
- 直接、审慎、可落入审计工作底稿。
- 结论要区分"已识别事实""推断风险""待补充证据"。
"""

# Cross-border e-commerce specialised agent prompts
CB_DATA_EXTRACTOR_PROMPT = """你是 Data_Extractor，专注于跨境电商企业的资深审计助理。
职责:
1. 处理多平台销售数据(Amazon/TikTok/Shopee)、外汇凭证、海关单据和境外关联方交易。
2. 识别跨境审计特有风险: 收入确认时点、汇率折算、转让定价、进口合规、存货NRV。
3. 输出格式: 风险发现 → 支持证据 → 潜在错报认定 → 建议审计程序。
限制:
- 不直接下最终审计意见。
- 指出多货币金额时须注明折算汇率及依据。
"""

CB_COMPLIANCE_CHECKER_PROMPT = """你是 Compliance_Checker，跨境电商财税合规专家。
职责:
1. 依据CAS 14(收入准则)、CAS 19(外币折算)、CAS 1(存货)及OECD转让定价指引进行合规分析。
2. 评估跨境增值税合规、进口关税HS编码准确性、BEPS第13号行动计划文档义务。
3. 必须引用检索依据编号，例如 [依据 1]，依据不足时明确说明。
限制:
- 境外税务法规仅作参考性分析，最终结论须由当地税务顾问确认。
- 不得凭空引用准则条款编号。
"""

CB_AUDIT_PARTNER_PROMPT = """你是 Audit_Partner，负责跨境电商客户的签字合伙人。
职责:
1. 对数据提取和合规分析结论进行专业质疑，重点关注管理层动机和证据链完整性。
2. 识别跨境业务特有的舞弊风险信号: 通过境外关联方转移利润、跨期确认收入、NRV低估等。
3. 形成最终审计意见，区分"已识别事实""推断风险""待补充证据"三类结论。
输出风格:
- 直接、审慎、可落入标准审计工作底稿。
- 针对每项高风险发现，明确后续必须执行的追加程序。
"""


@dataclass
class AgentTurn:
    speaker: str
    content: str


def build_audit_task(
    case_description: str,
    findings: list[Finding],
    rag_chunks: list[RetrievedChunk],
    data_prompt: str = "",
    compliance_prompt: str = "",
    partner_prompt: str = "",
) -> str:
    return f"""审计任务:
{case_description}

数据提取发现:
{format_findings(findings)}

RAG 检索依据:
{format_rag_context(rag_chunks)}

请三位 Agent 依次完成:
1. Data_Extractor 说明凭证异常和建议程序。
2. Compliance_Checker 引用依据进行合规分析。
3. Audit_Partner 进行复核质疑并输出最终审计意见。
"""


def run_mock_groupchat(case_description: str, findings: list[Finding], rag_chunks: list[RetrievedChunk]) -> list[AgentTurn]:
    findings_text = format_findings(findings)
    rag_text = format_rag_context(rag_chunks)

    data_turn = f"""我已对样例凭证执行规则扫描，初步发现如下:
{findings_text}

审计含义:
- 若 100 万支出实际形成可长期使用的服务器/设备，却计入管理费用，可能导致当期费用高估、固定资产低估、折旧费用跨期错误。
- 该金额超过样例重要性阈值 50 万，建议作为高风险样本执行细节测试。

建议程序:
1. 获取采购合同、发票、验收单、付款审批和资产入库记录。
2. 访谈信息技术部门，确认服务器是否已达到预定可使用状态。
3. 检查期末固定资产台账和折旧政策，量化重分类及折旧调整影响。"""

    compliance_turn = f"""我检索到的准则/教材依据如下:
{rag_text}

合规判断:
- 从会计处理看，若该服务器满足"为生产经营/管理而持有、使用寿命超过一个会计年度、经济利益很可能流入且成本能够可靠计量"等条件，应考虑确认为固定资产，而非一次性计入管理费用。
- 从审计准则看，该事项至少涉及分类认定和截止认定，也可能影响损益表期间费用、资产负债表固定资产及累计折旧。
- 如果管理层有通过费用化调节利润或规避资本开支审批的动机，还应上升为舞弊风险因素进行考虑。

限制说明:
- 当前依据来自样例知识片段。正式项目中需要接入官方 CPA 审计准则 PDF 和企业会计准则原文，并保留可追溯出处。"""

    partner_turn = """复核意见:
我同意该事项应列为高风险审计发现，但目前不能只凭摘要中的"服务器设备采购"直接下调整结论。关键缺口有三个:
1. 资产是否达到预定可使用状态，以及受益期是否超过一年。
2. 合同和验收单是否表明采购对象为硬件资产，还是包含运维、云服务或咨询服务。
3. 该错报金额对财务报表整体是否重大，以及是否存在同类事项系统性费用化。

最终审计意见:
- 初步风险定性: 资本性支出费用化导致固定资产低估、管理费用高估、利润低估或期间错配。
- 审计应对: 扩大管理费用中含"设备、服务器、工程、装修、硬件"等关键词的大额样本，执行合同/发票/验收/资产台账四方核对。
- 若证据支持资产确认，应建议管理层重分类至固定资产，并按达到预定可使用状态日期补提折旧。
- 若管理层拒绝调整，应汇总未更正错报，评价其对审计意见的影响。"""

    return [
        AgentTurn("Data_Extractor", data_turn),
        AgentTurn("Compliance_Checker", compliance_turn),
        AgentTurn("Audit_Partner", partner_turn),
    ]


def run_mock_cross_border_groupchat(
    case_description: str,
    findings: list[Finding],
    rag_chunks: list[RetrievedChunk],
) -> list[AgentTurn]:
    """High-quality mock for cross-border e-commerce audit scenario."""
    findings_text = format_findings(findings)
    rag_text = format_rag_context(rag_chunks)

    data_turn = f"""已对跨境电商客户凭证样本执行规则扫描及异常识别，结果如下:

{findings_text}

【多平台收入分析】
- Amazon US店铺结算款 605,200 元(USD 85,000 @ 7.12)及TikTok Shop回款 238,400 元已入账，但记账时点为平台结算日而非控制权转移日，存在收入确认时点偏差风险。
- 两项收入合计 843,600 元，占跨境收入比例较大，截止测试须按平台维度分层执行。

【转让定价高风险项】
- 向香港控股子公司支付管理及技术服务费 520,000 元，已超过重要性阈值。摘要提及"品牌授权使用费"混于服务费中，定价依据不明，无法判断是否符合独立交易原则。
- 该凭证供应商为关联方，一旦认定价格不公允，将同时引发转让定价调整和企业所得税补缴风险。

【存货NRV核查】
- FBA美国仓库计提跌价准备 315,000 元，库龄超180天标准为内部制定，尚无第三方验证。
- NRV = 估计售价 - 估计处置费用(FBA清仓费+物流回运费)。需核查管理层是否低估销售费用以减少减值金额。

【外汇及海关】
- 期末外汇汇兑损失 58,640 元，需验证外汇敞口期初余额及汇率差计算。
- 进口关税及增值税 142,000 元，须核对完税证明与HS编码税率表是否一致。

建议优先审计顺序: ①关联方服务费(转让定价) → ②FBA存货减值(NRV) → ③多平台收入截止测试 → ④外汇及关税合规。"""

    compliance_turn = f"""基于RAG检索知识及跨境电商财税法规，合规分析如下:

{rag_text}

【收入确认 — CAS 14/IFRS 15】
[依据 1] 根据企业会计准则第14号(2017年修订)，收入应在履行合同中的履约义务时确认，即控制权转移至买方时点。对于跨境电商，控制权转移点应为货物出关/买家签收，而非平台资金结算日，两者可能相差数周。当前凭证按结算日记账存在提前确认收入风险(认定: 截止、计量)。

【外币折算 — CAS 19】
[依据 2] 企业会计准则第19号规定，外币货币性项目期末应按资产负债表日即期汇率折算，折算差额计入当期损益(汇兑损益)。期末重估汇率须使用中国人民银行公布的基准汇率，非银行中间价或历史成本汇率。

【存货计量 — CAS 1】
[依据 3] 企业会计准则第1号要求存货以成本与可变现净值孰低计量。NRV = 估计售价 - 至完工估计将要发生的成本 - 估计销售费用 - 估计税金。FBA模式下销售费用包含平台佣金(约15%)、FBA配送费、广告费用等，管理层测算模型须逐项披露。

【转让定价及BEPS】
[依据 4] 根据OECD转让定价指引及《企业所得税法》第41条，关联方交易应遵循独立交易原则。向香港关联方支付的520,000元管理服务费中混入品牌授权使用费，应分拆核算并分别适用转让定价分析方法(服务费可用成本加成法；特许权使用费须参考可比非受控价格法)。根据BEPS第13号行动计划，年营业额超过一定规模须准备主体文档及本地文档。

依据完整性说明: 当前检索库为样例知识片段，正式项目须接入官方CPA审计准则PDF及OECD最新指引完整版。"""

    partner_turn = """【Audit Partner 复核意见】

本人对以上两位分析意见表示认可，但补充以下关键质疑和必要程序:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
已识别事实
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 关联方服务费 520,000 元:
   - 金额超过重要性阈值，服务费与品牌授权混合定价不符合分拆披露要求。
   - 已触发转让定价风险因素，须追加: 获取独立转让定价报告全文并评估分析方法和可比公司选取。

2. FBA存货跌价 315,000 元:
   - 库龄标准"180天"由管理层自定，无行业对标。NRV测算模型未经第三方验证。
   - 必须追加: 获取ASIN级别期后3个月实际销售记录，测试管理层估计准确性。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
推断风险
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. 多平台收入截止风险:
   - 存在通过延迟平台结算日、将下期收入计入本期的动机(若管理层有盈利压力)。
   - 舞弊风险信号: Amazon/TikTok双平台同日结算数字整齐，建议获取原始平台Sales Report逐单核对。

4. 汇兑损益操纵可能:
   - 汇率选取(7.18 vs 7.10)差异较大。若外汇敞口余额较大，微小汇率调整对损益影响显著。
   - 需独立复算外汇头寸 × (期末汇率 - 期初汇率)，核对银行确认外汇余额。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
待补充证据
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. 尚需获取:
   - 香港子公司服务协议全文 + 独立转让定价报告
   - FBA库龄明细 + ASIN级别NRV测算底稿
   - Amazon/TikTok平台原始Sales Report(逐单)
   - 期末银行外汇余额确认函
   - 进口报关单及HS编码完税证明

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
最终审计结论
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
当前证据下，以下两项应列为重大错报风险(高):
① 跨境关联方转让定价 — 价格公允性存疑，企业所得税补税敞口待量化
② FBA存货NRV — 管理层假设激进，减值准备充分性待补充证据支撑

收入截止、外汇折算列为显著风险(中)，执行实质性程序后重评级。
退货准备及进口关税合规待验证后定性，暂列关注事项。"""

    return [
        AgentTurn("Data_Extractor", data_turn),
        AgentTurn("Compliance_Checker", compliance_turn),
        AgentTurn("Audit_Partner", partner_turn),
    ]


def _select_prompts(case_type: str) -> tuple[str, str, str]:
    if case_type == "cross_border":
        return CB_DATA_EXTRACTOR_PROMPT, CB_COMPLIANCE_CHECKER_PROMPT, CB_AUDIT_PARTNER_PROMPT
    return DATA_EXTRACTOR_PROMPT, COMPLIANCE_CHECKER_PROMPT, AUDIT_PARTNER_PROMPT


def run_autogen_groupchat(
    settings: Settings,
    case_description: str,
    findings: list[Finding],
    rag_chunks: list[RetrievedChunk],
    case_type: str = "fixed_asset",
) -> list[AgentTurn]:
    """Run a real LLM-backed three-agent discussion.

    Prefer classic pyautogen GroupChat when the legacy `autogen` package is
    available. Newer pyautogen releases are proxy packages for autogen-agentchat
    and do not expose `import autogen`, so fall back to direct OpenAI-compatible
    calls while keeping the same three-agent workflow.
    """
    try:
        import autogen
    except Exception as exc:
        return run_openai_compatible_groupchat(settings, case_description, findings, rag_chunks, case_type)

    data_prompt, compliance_prompt, partner_prompt = _select_prompts(case_type)
    llm_config = build_llm_config(settings)
    rag_context = format_rag_context(rag_chunks)
    task = build_audit_task(case_description, findings, rag_chunks)

    data_extractor = autogen.AssistantAgent(
        name="Data_Extractor",
        system_message=data_prompt,
        llm_config=llm_config,
    )
    compliance_checker = autogen.AssistantAgent(
        name="Compliance_Checker",
        system_message=compliance_prompt + "\n\n当前可用 RAG 检索上下文:\n" + rag_context,
        llm_config=llm_config,
    )
    audit_partner = autogen.AssistantAgent(
        name="Audit_Partner",
        system_message=partner_prompt,
        llm_config=llm_config,
    )
    user_proxy = autogen.UserProxyAgent(
        name="Audit_Manager",
        human_input_mode="NEVER",
        code_execution_config=False,
        default_auto_reply="请继续。",
    )
    groupchat = autogen.GroupChat(
        agents=[user_proxy, data_extractor, compliance_checker, audit_partner],
        messages=[],
        max_round=settings.max_rounds,
        speaker_selection_method="round_robin",
        allow_repeat_speaker=False,
    )
    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)
    user_proxy.initiate_chat(manager, message=task)

    turns: list[AgentTurn] = []
    for message in groupchat.messages:
        speaker = str(message.get("name") or message.get("role") or "unknown")
        content = str(message.get("content") or "").strip()
        if content:
            turns.append(AgentTurn(speaker=speaker, content=content))
    return turns


def run_openai_compatible_groupchat(
    settings: Settings,
    case_description: str,
    findings: list[Finding],
    rag_chunks: list[RetrievedChunk],
    case_type: str = "fixed_asset",
) -> list[AgentTurn]:
    """Run the three audit agents through an OpenAI-compatible chat API."""
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is empty. Use --mode mock or set audit_multi_agent_rag/.env.")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("openai package is not installed. Run pip install -r audit_multi_agent_rag\\requirements-phase1.txt.") from exc

    data_prompt, compliance_prompt, partner_prompt = _select_prompts(case_type)
    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    task = build_audit_task(case_description, findings, rag_chunks)
    rag_context = format_rag_context(rag_chunks)

    data_content = _call_chat_agent(
        client=client,
        settings=settings,
        agent_name="Data_Extractor",
        system_prompt=data_prompt,
        user_message=task,
    )
    compliance_content = _call_chat_agent(
        client=client,
        settings=settings,
        agent_name="Compliance_Checker",
        system_prompt=compliance_prompt + "\n\n当前可用 RAG 检索上下文:\n" + rag_context,
        user_message=(
            f"{task}\n\nData_Extractor 已输出:\n{data_content}\n\n"
            "请基于数据发现和 RAG 依据进行合规分析。"
        ),
    )
    partner_content = _call_chat_agent(
        client=client,
        settings=settings,
        agent_name="Audit_Partner",
        system_prompt=partner_prompt,
        user_message=(
            f"{task}\n\nData_Extractor 输出:\n{data_content}\n\n"
            f"Compliance_Checker 输出:\n{compliance_content}\n\n"
            "请复核前两者结论并形成最终审计意见。"
        ),
    )

    return [
        AgentTurn("Data_Extractor", data_content),
        AgentTurn("Compliance_Checker", compliance_content),
        AgentTurn("Audit_Partner", partner_content),
    ]


def _call_chat_agent(client, settings: Settings, agent_name: str, system_prompt: str, user_message: str) -> str:
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=settings.temperature,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError(f"{agent_name} returned an empty response.")
    return content.strip()
