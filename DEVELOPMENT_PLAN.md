# Agent 开发计划

这个计划用于推进 `audit_multi_agent_rag` 从当前可演示原型，逐步变成可接入真实审计资料、可检索正式准则、可替换本地大模型的多 Agent 审计助手。

## 当前定位

当前版本是 Phase 1 原型:

- `Data_Extractor`: 读取凭证并识别异常线索。
- `Compliance_Checker`: 从知识库检索准则和会计处理依据。
- `Audit_Partner`: 复核前两个 Agent 的结论并形成审计意见。
- `mock` 模式: 不需要 API Key，适合本地演示和调业务逻辑。
- `autogen` 模式: 配置 DeepSeek API 后，尝试真实 AutoGen GroupChat。

## 使用这个计划

1. 每次开发前，先看“推荐执行顺序”，只选一个小任务开始做。
2. 完成任务后，把对应条目标成 `[x]`，并把实际命令和结果写入 `DEVELOPMENT_LOG.md`。
3. 每个阶段都先用 `mock` 跑通，再切到 `autogen` 或本地模型。
4. 只有当“完成标准”全部满足时，才进入下一阶段。

## 快速运行基线

在仓库外层目录运行，也就是:

```powershell
cd "C:\Users\王子畅\Documents\New project"
```

先跑无 Key 演示。`mock` 模式只依赖 Python 标准库，不需要先安装一堆包:

```powershell
python -m audit_multi_agent_rag.scripts.run_phase1_demo --mode mock
```

只有准备使用 DeepSeek/AutoGen、Excel 读取或遇到缺包错误时，再安装轻量依赖:

```powershell
python -m pip install -r audit_multi_agent_rag\requirements-phase1.txt
```

查看输出底稿:

```text
audit_multi_agent_rag\output\audit_reports\
```

## 推荐执行顺序

### Phase 1: 稳定本地演示

- [x] 建立三 Agent 原型。
- [x] 支持 `mock` 模式。
- [x] 输出 Markdown 审计工作底稿。
- [ ] 增加 2 到 3 个新的样例案例，例如收入截止、往来款异常、费用跨期。
- [ ] 给样例案例增加预期发现，方便后续自动测试。
- [ ] 增加一个 `--case-id` 参数，用案例编号选择样例数据。

完成标准:

- `python -m audit_multi_agent_rag.scripts.run_phase1_demo --mode mock` 稳定运行。
- 每个样例案例都能生成审计底稿。
- `DEVELOPMENT_LOG.md` 记录运行命令和输出文件路径。

### Phase 2: 接入正式知识库

- [ ] 收集正式 CPA 审计准则、CPA 教材、企业会计准则 PDF。
- [ ] 新建原始资料目录，例如 `knowledge_sources/`，不要直接覆盖样例文件。
- [ ] 增加 PDF 文本抽取脚本。
- [ ] 按准则号、章节、标题切分 chunk。
- [ ] 使用 `BAAI/bge-small-zh-v1.5` 和 ChromaDB 构建向量库。
- [ ] 让 `Compliance_Checker` 的输出必须包含引用依据。

完成标准:

- `python -m audit_multi_agent_rag.scripts.build_knowledge_base` 能构建本地向量库。
- 检索结果能返回来源文件、章节或准则号。
- 审计底稿中能看到明确引用，而不是泛泛描述。

### Phase 3: 扩展数据输入

- [ ] 支持 Excel 凭证表或科目余额表。
- [ ] 增加字段映射配置，兼容不同表头。
- [ ] 增加金额阈值、敏感科目、摘要关键词规则配置。
- [ ] 输出结构化发现，例如风险类型、金额、凭证号、建议程序。
- [ ] 为 CSV 和 Excel 输入增加最小测试样本。

完成标准:

- 同一审计案例可以从 CSV 或 Excel 读取。
- 异常发现字段稳定，方便后续前端或报告生成复用。

### Phase 4: 真实多 Agent 对话

- [ ] 配置 `.env` 中的 DeepSeek API。
- [ ] 跑通 `--mode autogen`。
- [ ] 固化三个 Agent 的 system prompt。
- [ ] 限制轮次和输出格式，避免对话发散。
- [ ] 增加失败降级: API 失败时自动提示切回 `mock`。

完成标准:

- `python -m audit_multi_agent_rag.scripts.run_phase1_demo --mode autogen` 可以生成底稿。
- Agent 输出包含数据发现、准则依据、复核意见三段信息。

### Phase 5: 本地 GPU 或 AutoDL 部署

- [ ] 在 AutoDL 或本地 GPU 上部署 Qwen 系列模型。
- [ ] 使用 Ollama、vLLM 或 OpenAI-compatible server 暴露接口。
- [ ] 把 `.env` 的 base url 和 model 切到本地模型。
- [ ] 对比 DeepSeek、本地 Qwen、mock 三种模式的输出质量。
- [ ] 记录显存、响应时间、上下文长度和成本。

完成标准:

- 不依赖公网 LLM API 也能跑真实对话。
- 同一案例可以在不同模型后端之间切换。

## 日常开发流程

每次改代码建议按这个顺序:

```powershell
cd "C:\Users\王子畅\Documents\New project"
python -m audit_multi_agent_rag.scripts.run_phase1_demo --mode mock
python -m compileall audit_multi_agent_rag
```

如果改了知识库:

```powershell
python -m audit_multi_agent_rag.scripts.build_knowledge_base
python -m audit_multi_agent_rag.scripts.run_phase1_demo --mode mock
```

如果改了真实 Agent 适配:

```powershell
python -m audit_multi_agent_rag.scripts.run_phase1_demo --mode autogen
```

## 文件怎么用

- `README.md`: 给自己或别人快速了解项目和运行命令。
- `DEVELOPMENT_PLAN.md`: 放开发路线、阶段目标、任务清单。
- `DEVELOPMENT_LOG.md`: 记录每次实际做了什么、跑了什么、结果是什么。
- `sample_data/`: 放演示用结构化数据。
- `sample_knowledge/`: 放开发联调用知识片段。
- `output/audit_reports/`: 放每次生成的审计底稿。

## 下一步最推荐做的事

先做 Phase 1 的“多案例样例库”。它不需要 API Key，也不依赖重型 RAG 环境，但能快速提升原型可信度。建议新增:

- 固定资产费用化案例。
- 收入提前确认案例。
- 关联方或往来款长期挂账案例。

做完后，再进入正式 PDF 知识库和真实 AutoGen 对话，会更稳。
