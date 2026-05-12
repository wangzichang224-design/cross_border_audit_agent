# C 货币资金审计底稿 Agent（Cash Workpaper Agent）

## 一句话

这个底稿 Agent 不是聊天机器人，而是一个"材料结构化 + 审计规则聚合 + Excel 底稿写入"的自动化系统。用户上传试算平衡表、序时账、银行询证函回函，后端自动整理成标准材料包，再由填写引擎写入核心优化版 C 货币资金审计底稿。

---

## 项目根路径

```
D:\03_AI_Projects\cross_border_audit_agent\cross_border_audit_agent
```

## 核心文件

| 文件 | 用途 |
|------|------|
| `streamlit_app.py` | **前端入口** — 文件上传、底稿预览与下载 |
| `cli.py` | **命令行入口** — 支持 `workpaper --case-type cash` |
| `scripts/generate_workpaper.py` | 底稿生成调度（多 case 派发） |
| `benchmarks/agent/materials_loader.py` | 读取结构化材料包为 dataclass |
| `benchmarks/agent/cash_workpaper_filler.py` | **底稿填写引擎** — 构造上下文、聚合金额、写入 Excel |
| `benchmarks/agent/cell_map_clean.py` | 核心优化版模板的单元格坐标表 |
| `benchmarks/agent/pdf_confirmations.py` | **银行回函 PDF 解析器** — 提取银行名/账号/余额 |
| `benchmarks/agent/llm_enhancer.py` | 可选 LLM 增强层（不开 API 也能用规则填写） |
| `benchmarks/template_builder/build_optimized_cash_template.py` | 模板生成器 |
| `outputs/clean_templates/C_货币资金审计底稿_核心优化版_CN_CAS.xlsx` | 当前使用的干净底稿模板 |

## 整体架构

```
Streamlit 前端 (streamlit_app.py)
        │
        ▼
上传三类文件：试算平衡表(.xlsx/.csv) / 序时账(.xlsx/.csv) / 询证函回函(.pdf)
        │
        ▼
标准化为材料包 → output/uploaded_materials/<case_id>/
  ├── case_metadata.json     (客户信息、TE、SAD 等)
  ├── period_summary.csv     (试算平衡表 → 各科目余额)
  ├── bank_statement.csv     (序时账 → 银行流水)
  ├── confirmations.csv      (PDF 回函解析 / CSV 回函)
  └── reconciliation.csv     (调节项)
        │
        ▼
materials_loader.py 读取为 dataclass
        │
        ▼
cash_workpaper_filler.py 构建 FillContext
  金额汇总 / 函证核对 / 银行余额调节 / 截止性测试样本
        │
        ▼
cell_map_clean.py 定位核心优化版 Excel 的可写单元格
        │
        ▼
openpyxl 写入模板（保留公式区、check 行、tie-out）
        │
        ▼
生成 Excel 底稿 → output/workpapers/<stamp>_现金底稿.xlsx
        │
        ▼
前端提供下载按钮
```

## 上传材料说明

Agent 接收三类文件（任选其一或组合上传）：

| 文件类型 | 格式 | 关键列 |
|---------|------|--------|
| **试算平衡表** | `.xlsx` / `.csv` | 科目编码、科目名称、期末借方余额、期末贷方余额、上年末审定数 |
| **银行存款日记账** | `.xlsx` / `.csv` | 日期、银行名称、账号、币种、摘要、借方金额、贷方金额、余额 |
| **银行询证函回函** | `.pdf` | Agent 自动解析银行名、账号、确认余额（支持本生成器产生的回函 PDF） |

## 输出底稿包含的 sheet

| Sheet | 内容 |
|-------|------|
| 汇总 | 程序索引与状态 |
| 货币资金主表 | 客户信息、风险认定、余额波动分析、披露核对 |
| 货币资金明细 | 全量账户明细（公司/银行/账号/币种/金额/用途/函证状态） |
| 银行余额调节 | 调节表（账面 vs 对账单、银收企未收/银付企未付） |
| 截止性测试 | 期末前后银行间转账样本 |

## 离线/在线模式

- **Mock 模式（默认）**：纯规则聚合，无需任何 API
- **LLM 增强模式**：通过 `llm_enhancer.py` 调用 DeepSeek API 优化风险等级和说明文字
- 两种模式共用同一套填写引擎，切换只影响文本质量，不影响数值准确性

## 质量保证

- 所有公式区（SUM、IF、Check）**保留不动**
- Agent 只写入 cell_map 定义的可写 cell，越界写会被测试拦截
- 底稿中的"核对"行（如 `=F35-C35`）在公式层面校验账面=对账单
