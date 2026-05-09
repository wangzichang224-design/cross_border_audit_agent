# 跨境电商多源资金流 AI 自动化审计 Agent

> Cross-border E-commerce Multi-source Fund Flow AI Audit Agent

一个具备"感知—决策—执行"循环的 AI Agent，自动完成跨境电商资金流的数据清洗、规则审计、LLM 智能分析与可视化报告生成。

---

## 项目架构

```
cross_border_audit_agent/
├── main.py                        # 入口：CLI 参数解析
├── config.py                      # 全局配置、审计阈值
├── requirements.txt
│
├── src/
│   ├── data_ingestion/
│   │   └── data_generator.py      # 模拟多平台原始账单（含人为注入异常）
│   │
│   ├── cleaning/
│   │   └── cleaner.py             # 多源数据清洗管道（去重/FX归一/异常标记）
│   │
│   ├── llm/
│   │   ├── prompts.py             # 审计 Prompt 集（含版本迭代记录）
│   │   └── classifier.py          # LLM 分类器 + AI 审计分析师
│   │
│   ├── audit/
│   │   └── anomaly_detector.py    # 规则引擎（10 项 ISA 标准审计规则）
│   │
│   ├── reporting/
│   │   ├── visualizer.py          # 6 张可视化图表
│   │   └── report_generator.py    # Markdown 报告生成
│   │
│   └── agent/
│       └── orchestrator.py        # Agent 主循环（感知→决策→执行）
│
├── data/raw/                       # 原始 CSV（自动生成）
├── data/processed/                 # 清洗后数据
└── reports/{run_id}/               # 每次运行的图表 + 报告
```

---

## 核心功能模块

### 模块 1：多源异构数据清洗
- **多平台模拟数据**：Amazon US/EU、TikTok Shop、Shopify、eBay，含多货币（USD/EUR/GBP/BRL）
- **人为注入异常**：大额交易、费用激增、退款潮、FX 汇率偏差、缺失值、重复记录
- **清洗管道**：类型转换 → 精确/近似去重 → 缺失值处理 → FX 归一化 → IQR 统计异常检测
- **数据质量报告**：每行 DQ Score，按严重程度（CRITICAL/WARNING/INFO）分类输出

### 模块 2：审计思维规则引擎（ISA 标准）
10 项规则，对应 ISA 240（舞弊风险）和 ISA 520（分析程序）：

| 规则 | 标准依据 | 触发条件 |
|------|---------|---------|
| LARGE_SINGLE_TXN | ISA 240 | 单笔 > $50K |
| OUTFLOW_SPIKE | ISA 520 | 日支出环比 > 50% |
| HIGH_DSO | ISA 520 | 回款天数 > 45 天 |
| HIGH_FEE_RATE | ISA 520 | 任意费用类别 > 20% 收入 |
| HIGH_REFUND_RATE | ISA 240 | 退款率 > 15% |
| CONCENTRATION_RISK | 内控 | 单平台收入 > 60% |
| FX_DEVIATION | ISA 240 | 汇率偏差 > 5% |
| SETTLEMENT_DELAY | ISA 520 | 非 Amazon 平台结算 > 14 天 |
| WEEKEND_LARGE_PAYMENT | ISA 240 | 周末大额出款 |
| ROUND_NUMBER_PATTERN | ISA 240 | 整数金额规律性出现（反结构化） |

### 模块 3：LLM 智能层（Claude Sonnet 4.6）
- **交易分类**：对 `Unclassified` 描述批量调用 Claude，带置信度 + 推理依据 + 风险标记
- **AI 审计分析**：将规则引擎输出 + 汇总指标传给 LLM，生成结构化 JSON 发现报告
- **执行报告生成**：Claude 按 CFO 报告标准输出 Markdown 周报（含业务洞察）
- **Prompt 缓存**：System Prompt 使用 `cache_control: ephemeral`，批量处理成本降低 ~80%

### Prompt 迭代记录（面试重点）

| 版本 | 变更 | 效果 |
|------|------|------|
| v1.0 | 基础分类，无置信度 | 准确率 ~72% |
| v1.1 | 加入置信度评分 + 推理依据 | ~81% |
| v1.2 | 加入舞弊风险标记 + Unclassified 兜底 | ~89% |
| v2.0 | 引入平台费率锚点 + ISA 框架上下文 | ~94% |

### 模块 4：可视化报告（6 张图）
1. 日净现金流（折线 + 柱状）
2. 平台收入分布（月度堆积柱 + 饼图）
3. 成本结构（横向柱状，标注收入占比）
4. 结算周期分布（各平台 DSO 直方图）
5. 异常标记热力图（ISO 周 × 平台）
6. 风险发现分类统计

---

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 离线演示（无需 API Key）
python main.py --offline --days 90

# 完整 LLM 运行
export ANTHROPIC_API_KEY=sk-ant-...
python main.py --days 90

# 复用已生成数据
python main.py --use-existing
```

输出目录：`reports/{run_id}/`
- `audit_report_*.md`  — 完整 Markdown 报告
- `01_daily_cashflow.png` — `06_risk_summary.png`

---

## 技术栈

| 层次 | 技术 |
|------|------|
| AI 模型 | Claude Sonnet 4.6 (Anthropic) |
| 数据处理 | Pandas, NumPy, SciPy |
| 可视化 | Matplotlib, Seaborn |
| CLI / 显示 | Rich |
| 模拟数据 | Faker |
| 合规框架 | ISA 240, ISA 520 |

---

## 与目标 JD 的对应关系

| JD 职责 | 本项目体现 |
|--------|----------|
| 多源数据清洗与对账 | `cleaner.py`：去重、FX归一、缺失值处理、DQ Score |
| 资金异常识别 | `anomaly_detector.py`：10 项 ISA 规则引擎 |
| 周报与数据可视化 | `visualizer.py` + `report_generator.py` |
| 财务严谨性 | 数据对账环节、FX偏差检测、材料性阈值参数化 |
| AI 工具应用 | LLM 分类 + 审计分析 + 执行报告，含 Prompt 迭代记录 |
