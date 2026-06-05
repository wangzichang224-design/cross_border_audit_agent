# 从这里开始

这个项目是你的“跨境电商资金流审计 Agent + RAG + Excel 标准底稿”课堂展示原型。它的核心不是让模型自由聊天，而是把审计材料、准则依据、Agent 复核和底稿写入组织成可演示、可检查、可继续评测的工作流。

## 推荐演示顺序

1. 启动前端：`streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501`
2. 打开局域网地址：`http://<WLAN-IP>:8501`
3. 点击“使用内置示例生成底稿”
4. 下载生成的 C 货币资金 Excel 底稿
5. 回到 PPT 讲为什么要做、怎么控风险、怎么从 Demo 走向产品化

局域网 IP 检查和课堂流程见 [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md)。

## 你应该先看

```text
README.md
docs/PROJECT_STRUCTURE.md
AGENT_OVERVIEW.md
docs/DEMO_RUNBOOK.md
```

核心代码：

```text
streamlit_app.py
cli.py
audit_rag/pipeline.py
audit_rag/agents.py
audit_rag/orchestrator.py
audit_rag/hybrid_retriever.py
benchmarks/agent/cash_workpaper_filler.py
benchmarks/agent/pdf_confirmations.py
```

## 最简单的检查命令

```powershell
python cli.py doctor
python cli.py where
python -m pytest -q
```

`doctor` 会检查 API Key、模板目录和关键依赖。mock 演示不需要 API Key。

## 免费跑一次跨境审计报告

```powershell
python cli.py run --case-type cross_border --mode mock
```

输出在：

```text
output/audit_reports/
```

## 免费生成一次 C 货币资金底稿

```powershell
python cli.py workpaper --case-type cash --mode mock `
  --materials-dir benchmarks/materials/case_001_minimal `
  --template-root outputs/clean_templates `
  --template-keyword 核心优化版
```

输出在：

```text
output/workpapers/
```

## 搜索审计知识库

```powershell
python cli.py search --query "转让定价 BEPS 关联方" --top-k 3
```

## 真实模型模式

如果要调用 DeepSeek / OpenAI-compatible API，复制 `.env.example` 为 `.env` 并配置密钥，然后运行：

```powershell
python cli.py run --case-type cross_border --mode autogen
```

真实客户数据请先脱敏，或接私有化模型。课堂展示优先使用 mock 模式。
