# 从这里开始

这个项目的课堂主线是“跨境电商资金流 AI 审计 Agent”。它演示的是平台交易流水如何进入数据清洗、规则扫描、DeepSeek/离线审计叙述、资金核对和报告输出。

## 推荐演示顺序

1. 启动前端：`streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501`
2. 打开局域网地址：`http://<WLAN-IP>:8501`
3. 左侧保持“演示数据（自动生成）”
4. 点击“开始审计”
5. 展示关键财务指标、审计发现清单、AI 审计叙述和下载区
6. 回到 PPT 讲为什么这个 Agent 需要证据链、规则边界和人工复核

局域网 IP 检查和课堂流程见 [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md)。

## 你应该先看

```text
README.md
docs/PROJECT_STRUCTURE.md
docs/DEMO_RUNBOOK.md
ARCHITECTURE.md
```

核心代码：

```text
streamlit_app.py
cli.py
src/agent/orchestrator.py
src/data_ingestion/data_generator.py
src/audit/anomaly_detector.py
src/llm/deepseek_client.py
src/reporting/report_generator.py
audit_rag/pipeline.py
audit_rag/agents.py
audit_rag/hybrid_retriever.py
```

## 最简单的检查命令

```powershell
python cli.py doctor
python cli.py where
python -m pytest -q
```

`doctor` 会检查 API Key、依赖和本地目录。课堂演示优先使用合成数据；如果不调用 DeepSeek，也能跑规则引擎和报告输出。

## 免费跑一次跨境审计报告

```powershell
python cli.py run --case-type cross_border --mode mock
```

输出在：

```text
output/audit_reports/
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

真实客户数据请先脱敏，或接私有化模型。课堂展示优先使用演示数据。
