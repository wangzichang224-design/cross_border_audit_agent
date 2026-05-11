# 从这里开始

这个项目是你的“审计多 Agent + RAG + 标准底稿”原型。它现在可以做三件事:

1. 读取样例凭证，识别审计异常。
2. 让三个审计 Agent 生成分析、准则依据和复核意见。
3. 把结果写入 Markdown 底稿和 K1 固定资产 Excel 标准底稿副本。

## 你应该从哪里看

优先看这几个文件:

```text
audit_multi_agent_rag\START_HERE.md
audit_multi_agent_rag\README.md
audit_multi_agent_rag\DEVELOPMENT_PLAN.md
audit_multi_agent_rag\TEMPLATE_INTEGRATION_PLAN.md
```

核心代码看这里:

```text
audit_multi_agent_rag\cli.py
audit_multi_agent_rag\audit_rag\pipeline.py
audit_multi_agent_rag\audit_rag\agents.py
audit_multi_agent_rag\audit_rag\data_tools.py
audit_multi_agent_rag\audit_rag\rag.py
audit_multi_agent_rag\scripts\generate_workpaper.py
```

输出文件看这里:

```text
audit_multi_agent_rag\output\audit_reports\
audit_multi_agent_rag\output\workpapers\
audit_multi_agent_rag\knowledge_sources\
```

## 最简单的检查命令

```powershell
cd "C:\Users\王子畅\Documents\New project"
python -m audit_multi_agent_rag.cli where
```

它会告诉你:

- 项目根目录在哪里。
- README 和计划文档在哪里。
- 最新 Markdown 底稿在哪里。
- 最新 Excel 标准底稿在哪里。
- 是否能自动找到桌面上的标准底稿模板目录。

## 检查环境

```powershell
python -m audit_multi_agent_rag.cli doctor
```

它会检查:

- DeepSeek API Key 是否已配置。
- 当前模型名。
- 标准底稿模板目录是否找到。
- `openai`、`openpyxl`、`pandas`、`autogen` 等包是否安装。

提示: 当前新版 `pyautogen` 不一定提供经典 `import autogen`，所以 `autogen` 显示 missing 不代表项目不能用。项目已经有 DeepSeek/OpenAI-compatible fallback。

## 先查一条知识库

```powershell
python -m audit_multi_agent_rag.cli search --query "会计估计 重大错报风险 审计证据" --top-k 5
```

这个命令会直接输出:

- 命中的文件名
- 页码
- 章节或条文
- 对应片段正文

## 免费跑一次 Agent 演示

```powershell
python -m audit_multi_agent_rag.cli run --mode mock
```

这个命令不调用 API，不花钱。它会生成 Markdown 审计底稿。

## 用 DeepSeek 跑一次真实 Agent

```powershell
python -m audit_multi_agent_rag.cli run --mode autogen
```

这个命令会调用 `.env` 里的 DeepSeek API。生成的 Markdown 底稿在:

```text
audit_multi_agent_rag\output\audit_reports\
```

## 生成 Excel 标准底稿

免费 mock 版:

```powershell
python -m audit_multi_agent_rag.cli workpaper --mode mock
```

DeepSeek 真实 Agent 版:

```powershell
python -m audit_multi_agent_rag.cli workpaper --mode autogen
```

生成的 Excel 底稿在:

```text
audit_multi_agent_rag\output\workpapers\
```

如果没有自动找到模板目录，就手动指定:

```powershell
python -m audit_multi_agent_rag.cli workpaper --mode mock --template-root "C:\Users\王子畅\Desktop\标准审计底稿模板第六版-使用版 (1)"
```

## 如何打开输出文件

PowerShell 推荐用:

```powershell
Invoke-Item -LiteralPath "完整文件路径"
```

打开输出目录:

```powershell
explorer "C:\Users\王子畅\Documents\New project\audit_multi_agent_rag\output\workpapers"
```

## 接入本地 PDF 知识库

把你合法持有的 PDF 放到:

```text
C:\Users\王子畅\Documents\New project\audit_multi_agent_rag\knowledge_sources
```

然后运行:

```powershell
python -m audit_multi_agent_rag.cli index
```

之后再跑:

```powershell
python -m audit_multi_agent_rag.cli run --mode autogen
```

说明:

- PDF 片段会尽量按“第几条”切分。
- 检索结果会保留文件名、页码、章节/条文。
- Markdown 底稿和 Excel 底稿会回填这些引用定位。

## 接入飞书

先在本地跑飞书 webhook:

```powershell
python -m audit_multi_agent_rag.cli feishu
```

默认监听:

```text
http://0.0.0.0:8001/feishu/webhook
```

飞书消息支持:

- 直接发送审计问题
- `#help`
- `#doctor`
- `#search 会计估计 重大错报风险 审计证据`

本地模拟测试:

```powershell
python -m audit_multi_agent_rag.scripts.simulate_feishu
```

## 当前参考 FinRobot 后做的优化

FinRobot 的工程思路是: Agent 层、Workflow 层、数据源/工具层、配置和教程分开。这个项目已经按类似思路整理为:

- `audit_rag/agents.py`: Agent 角色和模型调用。
- `audit_rag/pipeline.py`: 统一审计工作流。
- `audit_rag/data_tools.py`: 凭证读取和异常识别。
- `audit_rag/rag.py`: 审计准则 RAG 检索。
- `scripts/generate_workpaper.py`: 标准 Excel 底稿生成。
- `cli.py`: 统一命令入口。

后续继续扩展时，优先在 `pipeline.py` 接入新流程，而不是在每个脚本里重复写一套逻辑。
