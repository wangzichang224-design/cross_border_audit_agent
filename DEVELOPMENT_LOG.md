# 开发留痕

## 2026-05-11

### RAG 升级: Hybrid Search + Cross-Encoder Rerank

**痛点定位**
- 原检索链路是 `ChromaDB 向量召回 → keyword fallback`。
- 纯向量检索对**审计准则编号**（"第 1141 号"、"ISA 240"）这种字面 token 召回率低。
- Legacy keyword fallback 的分词器把整段中文当一个 token，短查询根本匹配不上。

**改动**
- 新增 `audit_rag/hybrid_retriever.py`:
  - `BM25Retriever` — 优先使用 `rank_bm25`，未安装时自动降级到内置纯 Python BM25。
  - `tokenize_for_bm25()` — CJK unigram + bigram + 字母数字 run 整体保留（保护 "1141 号"、"ISA240" 不被切碎）。
  - `reciprocal_rank_fusion()` — RRF 合并多路召回结果，无需对齐分数尺度。
  - `run_hybrid_search()` — 编排 BM25 + 向量检索；任一路失败自动降级。
- 新增 `audit_rag/reranker.py`:
  - `CrossEncoderReranker` — 默认 `BAAI/bge-reranker-base`，懒加载，加载失败时透传输入。
- 改造 `AuditKnowledgeBase.search()`:
  - 新增 `enable_hybrid` / `enable_rerank` 构造参数。
  - 三段式路由: hybrid (新) → 纯向量 (legacy) → keyword fallback (legacy)。
  - 默认 `enable_hybrid=True`（BM25 零额外依赖）、`enable_rerank=False`（reranker 模型~280MB）。
- `audit_rag/config.py` 新增三个环境变量开关:
  - `RAG_ENABLE_HYBRID`（默认 on）
  - `RAG_ENABLE_RERANK`（默认 off）
  - `RAG_RERANKER_MODEL`（默认 `BAAI/bge-reranker-base`）
- `audit_rag/pipeline.py` 把上述配置接到 `AuditKnowledgeBase`。
- `requirements.txt` 新增 `rank-bm25>=0.2.2`（可选，pure-python 已有 fallback）。

**测试**
- 新增 `tests/test_hybrid_retriever.py`，16 个测试覆盖:
  - 分词正确性（CJK bigram、字母数字保留、跨脚本不组对）
  - BM25 召回（准则编号定位、空查询、top-k、严格正分）
  - RRF 合并（共识优先、top-k 截断、按 chunk_id 去重）
  - 集成（向量失败容错、hybrid > legacy 在短查询上的提升）
- 全部通过；不依赖 `rank_bm25` / `sentence-transformers` / `chromadb` 即可跑。
- 端到端 smoke test：`run_audit_pipeline(mode='mock')` 在 hybrid 默认开启下正常返回 4 chunks。

**面试讲点**
- 纯向量检索在 audit 领域有结构性缺陷：会计准则编号是字符串而非语义。
- 用 BM25 + 向量混合 + RRF 合并 + cross-encoder 重排的工程手段补偿模型局限。
- 全链路 graceful degradation，每一层依赖都可缺失而不破坏 mock 模式。

## 2026-04-12

### FinRobot 参考优化

- 参考 FinRobot 的 agent/workflow/toolkit 分层思路，新增统一工作流层:
  - `audit_rag/pipeline.py`
- 新增统一命令入口:
  - `python -m audit_multi_agent_rag.cli where`
  - `python -m audit_multi_agent_rag.cli doctor`
  - `python -m audit_multi_agent_rag.cli run --mode mock`
  - `python -m audit_multi_agent_rag.cli run --mode autogen`
  - `python -m audit_multi_agent_rag.cli workpaper --mode mock`
  - `python -m audit_multi_agent_rag.cli workpaper --mode autogen`
- 新增入门说明:
  - `START_HERE.md`
- `run_phase1_demo.py` 和 `generate_workpaper.py` 已改为复用统一 pipeline，减少重复逻辑。
- 输出文件名增加毫秒级时间戳，避免同一秒连续生成时互相覆盖。
- 新增本地正式知识库目录:
  - `knowledge_sources/`
- RAG 检索已升级为同时支持:
  - `sample_knowledge/` 下的 Markdown
  - `knowledge_sources/` 下的本地 Markdown/PDF
- 新增统一建库入口:
  - `python -m audit_multi_agent_rag.cli index`
- 新增统一知识检索入口:
  - `python -m audit_multi_agent_rag.cli search --query "..." --top-k 5`
- `doctor` 现在会显示本地知识库目录和 `pypdf/chromadb/sentence_transformers` 依赖状态。
- `knowledge_sources/README.md` 已说明如何放置合法持有的 PDF 资料。
- 已支持本地 PDF 解析:
  - 当前通过 `pypdf` 读取 `knowledge_sources/中国注册会计师审计准则_财政部_2023.pdf`
- PDF chunk 规则已优化:
  - 优先按条文 `第X条` 切分
  - 保留文件名、页码、章节/条文、标题元数据
- 检索结果中的引用定位已回填到:
  - Markdown 底稿的 RAG 检索依据
  - `AI_Audit_Assistant` 工作表
  - `K.00 Lead Sheet!B59`
  - `K.02.1 新增测试!B20`
  - `K.02.1 新增测试!M34`
- `pipeline.py` 的 RAG 查询已改为根据 `--case` 动态生成，避免固定资产案例一直使用写死查询词。
- 参考 `zhayujie/chatgpt-on-wechat` 的通道层设计，新增独立飞书 webhook 通道:
  - `audit_rag/feishu.py`
- 新增统一启动入口:
  - `python -m audit_multi_agent_rag.cli feishu`
- 飞书通道支持:
  - URL 验证 challenge
  - 文本消息接收
  - `#help`
  - `#doctor`
  - `#search ...`
  - 默认将普通文本当作审计问题，复用现有 audit pipeline
- 飞书回复会异步处理，避免 webhook 回调阻塞。
- 新增本地模拟脚本:
  - `python -m audit_multi_agent_rag.scripts.simulate_feishu`
- `.env.example` 已增加 `FEISHU_*` 配置项。

验证命令:

```powershell
python -m compileall audit_multi_agent_rag
python -m audit_multi_agent_rag.cli where
python -m audit_multi_agent_rag.cli doctor
python -m audit_multi_agent_rag.cli index
python -m audit_multi_agent_rag.cli search --query "会计估计 重大错报风险 审计证据" --top-k 5
python -m audit_multi_agent_rag.scripts.simulate_feishu
python -m audit_multi_agent_rag.cli run --mode mock
python -m audit_multi_agent_rag.cli workpaper --mode mock
python -m audit_multi_agent_rag.cli run --mode autogen --case "简要测试固定资产费用化风险，并输出审计关注点。"
python -m audit_multi_agent_rag.cli workpaper --mode autogen --case "简要测试固定资产费用化风险，并输出审计关注点。"
```

验证结果:

- `where` 能正确显示项目目录、报告目录、Excel 底稿目录和桌面模板目录。
- `doctor` 显示 DeepSeek API Key 已配置，`openai/openpyxl/pandas/autogen_agentchat` 已安装，并显示本地知识库目录。
- `index` 在未安装 `chromadb` 时给出明确提示，并提示安装 `requirements.txt`。
- `search` 能返回本地 PDF 的文件名、页码和条文，例如第 10 页第二十五条、第二十六条。
- `simulate_feishu` 已验证:
  - URL verification 返回 `challenge`
  - `#search` 可生成带页码/条文的检索回复
  - 普通文本可触发 audit pipeline 并生成审计摘要回复
- `mock` 模式生成 Markdown 报告。
- `workpaper` 模式自动找到 K1 固定资产模板并生成 Excel 底稿。
- `autogen` 模式成功调用 DeepSeek 并生成 Markdown 报告。
- `workpaper --mode autogen` 成功调用 DeepSeek，并生成带 `K.00 Lead Sheet`、`K.02.1 新增测试`、`AI_Audit_Assistant` 写入结果的 Excel 底稿。

### 已完成

- 新建独立项目目录 `audit_multi_agent_rag`，避免影响原小说网站代码。
- 实现 Phase 1 可运行原型:
  - `Data_Extractor`
  - `Compliance_Checker`
  - `Audit_Partner`
- 实现 `mock` 模式，无需 API Key 也能跑通三 Agent 审计讨论。
- 实现 classic `pyautogen` GroupChat 适配器，配置 DeepSeek API 后可尝试真实多 Agent 对话。
- 实现样例凭证扫描:
  - 识别“100 万服务器设备采购计入管理费用”的资本性支出费用化风险。
  - 识别咨询费、往来款、其他应收等敏感关键词。
- 实现 RAG 检索器:
  - 优先使用 ChromaDB + `BAAI/bge-small-zh-v1.5`。
  - 未安装依赖时自动退回关键词检索，方便本地快速演示。
- 增加样例知识库:
  - 审计准则第 1101 号学习片段。
  - 审计准则第 1141 号学习片段。
  - 审计准则第 1231 号学习片段。
  - 审计准则第 1251 号学习片段。
  - 企业会计准则第 4 号固定资产学习片段。
- 生成演示审计底稿:
  - `audit_multi_agent_rag/output/audit_reports/20260412_190015_fixed_asset_case_mock.md`

### 已验证

```powershell
python -m audit_multi_agent_rag.scripts.run_phase1_demo --mode mock
python -m compileall audit_multi_agent_rag
```

验证结果:

- Phase 1 demo completed.
- 样本凭证数: 4。
- 识别发现数: 3。
- Python 编译检查通过。

### 当前限制

- 样例知识库不是官方 PDF 原文，只用于原型开发和 RAG 联调。
- 未在本机安装完整 `pyautogen/chromadb/sentence-transformers` 重依赖。
- `autogen` 模式需要 DeepSeek API Key，并可能因 `pyautogen` 版本差异需要微调适配器。
- 当前凭证解析只覆盖 CSV；Excel/PDF/年报结构化解析留到后续阶段。

### 下一步建议

1. 在 WSL2/Ubuntu 22.04 下创建 Python 3.10 Conda 环境。
2. 安装 `requirements.txt`。
3. 配置 DeepSeek API，跑 `--mode autogen`。
4. 收集正式 CPA 审计准则、CPA 教材、企业会计准则 PDF。
5. 用 `build_knowledge_base.py` 构建 ChromaDB。
6. 后续上 AutoDL 后，将 DeepSeek API 替换为 Qwen + vLLM/OpenAI-compatible endpoint。
