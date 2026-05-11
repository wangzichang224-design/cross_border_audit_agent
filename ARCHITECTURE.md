# 系统架构图

跨境电商资金流 AI 审计 Agent —— Perceive → Decide → Act 循环

---

## 一、整体五阶段流水线

```mermaid
flowchart TB
    %% ========= 输入层 =========
    subgraph IN["📥 数据输入层"]
        DS1["📊 演示数据生成器<br/>（90 天合成交易）"]
        DS2["📁 用户上传 CSV<br/>（真实账单）"]
    end

    %% ========= 五阶段流水线 =========
    subgraph PIPE["🔄 五阶段审计流水线（Orchestrator 编排）"]
        S1["Stage 1 · 数据摄入<br/><i>data_ingestion</i><br/>生成 / 加载交易记录"]
        S2["Stage 2 · 数据清洗<br/><i>cleaning.DataCleaner</i><br/>去重 · 补缺 · 质量评分"]
        S3["Stage 3 · 规则引擎审计<br/><i>audit.RuleBasedAnomalyDetector</i><br/>ISA 240 / ISA 520 检查"]
        S4["Stage 4 · AI 深度分析<br/><i>llm.DeepSeekClient</i><br/>分类未知 + 异常推理"]
        S5["Stage 5 · 报告生成<br/><i>reporting</i><br/>Markdown + 6 张图表"]
    end

    %% ========= 输出层 =========
    subgraph OUT["📤 输出层"]
        O1["🚨 审计发现清单<br/>CRITICAL / HIGH / MEDIUM / LOW"]
        O2["📄 Markdown 报告<br/>（中文 · 可下载）"]
        O3["📊 可视化图表<br/>现金流 · 平台占比 · 热力图"]
        O4["📦 清洗后 CSV<br/>（可追溯审计底稿）"]
    end

    %% ========= 前端 =========
    UI["🖥️ Streamlit Web UI<br/>侧边栏配置 · KPI 卡片 · 多 Tab 图表"]

    DS1 --> S1
    DS2 --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> S5
    S5 --> O1
    S5 --> O2
    S5 --> O3
    S5 --> O4
    UI -.触发.-> S1
    O1 -.展示.-> UI
    O2 -.下载.-> UI
    O3 -.展示.-> UI

    classDef stage fill:#dbeafe,stroke:#2563eb,color:#1e3a8a
    classDef io fill:#f0fdf4,stroke:#16a34a,color:#14532d
    classDef ui fill:#fef3c7,stroke:#d97706,color:#78350f
    class S1,S2,S3,S4,S5 stage
    class DS1,DS2,O1,O2,O3,O4 io
    class UI ui
```

---

## 二、模块依赖关系（Perceive · Decide · Act）

```mermaid
flowchart LR
    subgraph P["🔍 PERCEIVE 感知"]
        DG["data_generator.py<br/>合成跨境交易"]
        UP["上传 CSV"]
    end

    subgraph D["🧠 DECIDE 决策"]
        CL["cleaner.py<br/>数据清洗 + DQ 评分"]
        RB["anomaly_detector.py<br/>7 条审计规则"]
    end

    subgraph A["⚡ ACT 行动"]
        DC["deepseek_client.py<br/>LLM 分类 + 推理"]
        RG["report_generator.py<br/>Markdown 拼装"]
        VZ["visualizer.py<br/>matplotlib / seaborn"]
    end

    ORC["orchestrator.py<br/>🎯 Agent 编排器"]

    ORC --> DG
    ORC --> UP
    ORC --> CL
    ORC --> RB
    ORC --> DC
    ORC --> RG
    ORC --> VZ
    DG --> CL
    UP --> CL
    CL --> RB
    RB --> DC
    DC --> RG
    RB --> VZ
    VZ --> RG

    classDef perc fill:#e0f2fe,stroke:#0284c7
    classDef dec fill:#fef9c3,stroke:#ca8a04
    classDef act fill:#fce7f3,stroke:#be185d
    classDef orc fill:#1e293b,stroke:#0f172a,color:#fff
    class DG,UP perc
    class CL,RB dec
    class DC,RG,VZ act
    class ORC orc
```

---

## 三、规则引擎（Stage 3）的 7 条 ISA 审计规则

```mermaid
flowchart TB
    INPUT["清洗后交易表 df_clean"]
    INPUT --> R1
    INPUT --> R2
    INPUT --> R3
    INPUT --> R4
    INPUT --> R5
    INPUT --> R6
    INPUT --> R7

    R1["① 大额单笔预警<br/>（>$50K）"]
    R2["② 日支出突增<br/>（DoD >50%）"]
    R3["③ 应收账款逾期<br/>（DSO >45 天）"]
    R4["④ 异常手续费率<br/>（>20%）"]
    R5["⑤ 高退款率<br/>（>15%）"]
    R6["⑥ 平台集中度风险<br/>（单平台 >60%）"]
    R7["⑦ 汇率偏离参考<br/>（>5%）"]

    R1 --> AGG["🎯 异常发现汇总<br/>Finding 列表"]
    R2 --> AGG
    R3 --> AGG
    R4 --> AGG
    R5 --> AGG
    R6 --> AGG
    R7 --> AGG

    AGG --> RANK["按风险等级排序<br/>CRITICAL > HIGH > MEDIUM > LOW"]
    RANK --> NEXT["→ 进入 Stage 4 (DeepSeek AI)"]

    classDef rule fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef io fill:#dbeafe,stroke:#2563eb
    class R1,R2,R3,R4,R5,R6,R7 rule
    class INPUT,AGG,RANK,NEXT io
```

---

## 四、AI 分析（Stage 4）双任务

```mermaid
flowchart LR
    IN["规则引擎输出 + 未分类交易"]

    subgraph LLM["🤖 DeepSeek API（OpenAI 兼容协议）"]
        T1["任务 A：DeepSeekClassifier<br/>给 'Unclassified' 交易分类<br/>（批大小 20）"]
        T2["任务 B：DeepSeekAuditAnalyst<br/>对汇总 JSON 做 ISA 240/520 推理<br/>→ 风险叙述 + 补充发现"]
    end

    OUT1["补全 category 列<br/>+ llm_confidence / llm_rationale"]
    OUT2["AI 叙述报告<br/>+ 补充发现清单"]
    DEG["⚠️ 离线降级模式<br/>（无 API Key 时跳过）"]

    IN --> T1 --> OUT1
    IN --> T2 --> OUT2
    IN -.无 Key.-> DEG

    classDef llm fill:#ede9fe,stroke:#7c3aed
    classDef out fill:#d1fae5,stroke:#059669
    classDef deg fill:#fef3c7,stroke:#d97706
    class T1,T2 llm
    class OUT1,OUT2 out
    class DEG deg
```

---

## 五、部署架构

```mermaid
flowchart LR
    DEV["💻 本地开发<br/>Windows + Python 3.12"]
    GH["📦 GitHub<br/>wangzichang224-design/<br/>cross_border_audit_agent"]
    SC["☁️ Streamlit Cloud<br/>Linux + Python 3.12<br/>自动构建 / 重启"]
    USER["👤 终端用户<br/>（面试官 / 审计师）"]

    DEV -- "git push" --> GH
    GH -- "webhook 自动拉取" --> SC
    SC -- "https://*.streamlit.app" --> USER
    USER -. "侧边栏粘贴<br/>DEEPSEEK_API_KEY" .-> SC

    classDef cloud fill:#dbeafe,stroke:#2563eb
    classDef dev fill:#f3e8ff,stroke:#9333ea
    class SC,GH cloud
    class DEV dev
```

---

## 关键设计原则

| 原则 | 体现 |
|------|------|
| **优雅降级** | 没有 API Key 也能跑（规则引擎 + 报告），不会整体崩溃 |
| **可追溯审计底稿** | 每次运行生成独立 `run_id` 目录，CSV + 图表 + 报告齐全 |
| **合规性** | 严格遵循 ISA 240（舞弊风险）和 ISA 520（分析程序） |
| **可移植性** | `config._writable()` 自动检测只读环境，云端兼容 |
| **可扩展性** | LLM 客户端抽象，可替换 Claude / GPT 而不改业务逻辑 |
