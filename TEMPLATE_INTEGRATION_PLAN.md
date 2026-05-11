# 标准审计底稿模板集成方案

本方案用于把桌面上的标准审计底稿 Excel 模板，接入 `audit_multi_agent_rag` 多 Agent 审计原型。

模板位置:

```text
C:\Users\王子畅\Desktop\标准审计底稿模板第六版-使用版 (1)
```

## 结合原则

1. 不直接修改原始模板。
2. 每次生成底稿时，先复制一份模板到项目输出目录。
3. Agent 负责生成审计发现、依据、复核意见和建议程序。
4. Excel 模板负责承载标准格式、索引号、审计程序、复核痕迹和最终归档形态。
5. 模板内容如果涉及事务所版权或内部资料，不应整本发送给外部 API；只向模型提供必要字段、案例数据和局部上下文。

## 推荐目录

```text
audit_multi_agent_rag/
  data/
    template_inventory.json       # 自动扫描生成的模板索引
    template_field_map.json       # 手工维护的单元格映射
  output/
    audit_reports/                # 现有 Markdown 底稿
    workpapers/                   # 根据 Excel 模板生成的标准底稿副本
  scripts/
    inventory_swp_templates.py    # 扫描模板清单
    generate_workpaper.py         # 复制模板并写入 Agent 结果
```

## 当前模板初步分类

根据文件名和工作表名，当前模板可先这样使用:

| 审计场景 | 推荐模板 |
| --- | --- |
| 固定资产、资本性支出费用化 | `K1 SWP 固定资产 202YMMDD XYZ公司.xlsx` |
| 在建工程 | `J1 SWP 在建工程 202YMMDD XYZ公司.xlsx` |
| 费用详细测试 | `U_exp SWP VC&VD 202YMMDD XYZ公司.xlsx` |
| 收入时点确认 | `TOD SWP U_GP_收入时点 202YXXDD XYZ公司.xlsx` |
| 收入时段确认 | `TOD SWP U_GP_收入时段 202YXXDD XYZ公司.xlsx` |
| 应付账款、未入账负债 | `N SWP 应付账款 202YMMDD XYZ公司.xlsx`、`N&P SURL SWP 寻找未入账负债 202YMMDD XYZ公司.xlsx` |
| 货币资金 | `C SWP 货币资金 202YMMDD XYZ公司.xlsx` |
| 关联方 | `I1 SWP 关联方 202YMMDD XYZ公司.xlsx` |
| 应收账款或其他应收款减值 | `SWP ECL（应收账款） 202YMMDD XYZ公司.xlsm`、`SWP ECL（其他应收款） 202YMMDD XYZ公司.xlsm` |

## 与当前 Agent 输出的映射

当前程序已经能生成:

- 样本凭证数量。
- 异常发现数量。
- 每个发现的风险等级、问题、证据、建议程序。
- RAG 检索依据。
- 三个 Agent 的讨论过程。
- 最终审计意见。

建议先不要强行填入模板原有复杂单元格，而是在复制出的 Excel 底稿中新增一个工作表:

```text
AI_Audit_Assistant
```

写入字段:

| 字段 | 来源 |
| --- | --- |
| Case Description | CLI `--case` |
| Mode | `mock` 或 `autogen` |
| Voucher Count | `load_vouchers` |
| Finding Count | `analyze_vouchers` |
| Finding Detail | `Finding` 列表 |
| RAG Evidence | `AuditKnowledgeBase.search` |
| Data Extractor Output | `Data_Extractor` |
| Compliance Checker Output | `Compliance_Checker` |
| Audit Partner Output | `Audit_Partner` |
| Generated Markdown Report | `output/audit_reports/...md` |

这样做的好处:

- 不破坏原模板公式、宏、隐藏表和格式。
- 先把 AI 分析结果放进标准底稿文件，方便人工复核。
- 等确认每个模板的关键单元格后，再逐步做精确填表。

## 第一阶段落地方式

以当前固定资产案例为例:

1. 运行 DeepSeek 真实 Agent:

```powershell
python -m audit_multi_agent_rag.scripts.run_phase1_demo --mode autogen
```

2. 程序生成 Markdown 底稿。

3. 新增脚本复制 `K1 SWP 固定资产 202YMMDD XYZ公司.xlsx`。

4. 把复制文件重命名为类似:

```text
output\workpapers\K1_SWP_固定资产_20260412_XYZ公司_AI底稿.xlsx
```

5. 在副本里新增 `AI_Audit_Assistant` 工作表。

6. 把 Agent 结果写入该工作表，保留原始模板所有工作表。

## 第二阶段落地方式

人工打开模板，确认每类信息应该进入哪些单元格，例如:

- 项目名称。
- 审计期间。
- 编制人。
- 复核人。
- Lead Sheet 结论。
- 新增测试样本。
- 异常事项说明。
- 审计结论。

确认后维护:

```text
data\template_field_map.json
```

示例结构:

```json
{
  "fixed_asset": {
    "template_keyword": "K1 SWP 固定资产",
    "metadata_cells": {
      "client_name": "K.00 Lead Sheet!B2",
      "period_end": "K.00 Lead Sheet!B3"
    },
    "ai_sheet": "AI_Audit_Assistant"
  }
}
```

## 第三阶段落地方式

再把模板变成 Agent 的约束:

- `Data_Extractor` 输出必须能填入“样本、凭证、金额、异常说明、建议程序”。
- `Compliance_Checker` 输出必须能填入“准则依据、会计处理判断、审计认定”。
- `Audit_Partner` 输出必须能填入“复核意见、补充程序、最终结论”。

也就是说，模板不是简单附件，而是倒逼 Agent 输出更像真实审计底稿。

## 最推荐的下一步

先做一个最小可用版本:

- 只支持固定资产案例。
- 只复制 `K1 SWP 固定资产` 模板。
- 只新增 `AI_Audit_Assistant` 工作表。
- 不改原模板已有单元格。

跑通后，再扩展到收入、费用、应付账款、函证和 ECL 模板。

当前已实现最小脚本:

```powershell
python -m audit_multi_agent_rag.scripts.generate_workpaper --mode mock --template-root "C:\Users\王子畅\Desktop\标准审计底稿模板第六版-使用版 (1)" --template-keyword "K1 SWP 固定资产"
```

输出位置:

```text
audit_multi_agent_rag\output\workpapers\
```

当前固定资产模板已写入这些具体位置:

| 工作表 | 单元格 | 写入内容 |
| --- | --- | --- |
| `K.00 Lead Sheet` | `C2` | 客户名称 |
| `K.00 Lead Sheet` | `C4` | 分析日期 |
| `K.00 Lead Sheet` | `C7` | 适用会计准则 |
| `K.00 Lead Sheet` | `C8` | 记账本位币 |
| `K.00 Lead Sheet` | `B59` | AI 波动说明、异常事项和底稿链接 |
| `K.02.1 新增测试` | `B7` | 新增固定资产测试总体描述 |
| `K.02.1 新增测试` | `B20` | 关键项目选择理由 |
| `K.02.1 新增测试` | `F12` | 资本相关凭证金额合计 |
| `K.02.1 新增测试` | `F16` | 已测试关键项目金额 |
| `K.02.1 新增测试` | `B34:R34` | 第一条关键项目测试记录 |

公式列会尽量保留，例如 `K.02.1 新增测试!N34` 仍保留模板原公式 `=G34-L34`。
