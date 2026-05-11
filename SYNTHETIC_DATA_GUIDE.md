# 模拟业务数据指南

这份指南对应你的审计 Agent 数据层。

目标不是“随便造几张凭证”，而是生成一套能勾稽、能复核、能直接喂给审计流程的训练数据：

- 借贷平衡
- 科目符合中国会计准则常见口径
- 业务链条可追溯
- 能产出凭证、分录、试算平衡、存货流转和模拟单据

## 一条命令生成

在项目外层目录运行：

```powershell
cd "C:\Users\王子畅\Documents\New project"
python -m audit_multi_agent_rag.cli seed-data
```

可选参数：

```powershell
python -m audit_multi_agent_rag.cli seed-data --company-name "华东智造科技有限公司"
python -m audit_multi_agent_rag.cli seed-data --period-start 2025-12-01
python -m audit_multi_agent_rag.cli seed-data --seed 42
python -m audit_multi_agent_rag.cli seed-data --profile audit_training
python -m audit_multi_agent_rag.cli seed-data --profile clean
```

## 会生成什么

输出目录在：

```text
C:\Users\王子畅\Documents\New project\audit_multi_agent_rag\output\synthetic_data\
```

每次会新建一个时间戳文件夹，里面包含：

- `vouchers.csv`：给当前审计 Agent 直接读取的凭证样本
- `journal_entries.csv`：分录明细
- `source_documents.csv`：来源单据索引
- `trial_balance.csv`：试算平衡
- `inventory_movements.csv`：原材料/产成品收发存
- `documents\*.html`：可直接打开的模拟账单/发票/回单
- `expected_findings.json`：这套数据里预埋的训练风险
- `dataset_summary.md`：本批数据的说明和推荐命令

## 当前内置的业务链

这套模拟账目前是一家制造型企业的月度闭环，覆盖：

1. 原材料采购入库
2. 采购付款
3. 生产领料
4. 工资计提
5. 制造费用归集
6. 完工入库
7. 销售确认收入
8. 结转成本
9. 回款
10. 固定资产购置
11. 折旧计提

`audit_training` 模式还会额外注入三类审计风险：

1. 资本性支出费用化
2. 大额咨询费
3. 员工借款挂在其他应收款

## 如何喂给现有 Agent

生成数据后，CLI 会打印推荐命令。你也可以自己运行：

```powershell
python -m audit_multi_agent_rag.cli run --mode mock --voucher-file output\synthetic_data\你的批次\vouchers.csv
```

如果已经配置了 DeepSeek：

```powershell
python -m audit_multi_agent_rag.cli run --mode autogen --voucher-file output\synthetic_data\你的批次\vouchers.csv
```

生成标准底稿：

```powershell
python -m audit_multi_agent_rag.cli workpaper --mode mock --voucher-file output\synthetic_data\你的批次\vouchers.csv
```

## 如何看模拟账单

直接打开生成目录下的 `documents` 文件夹：

```powershell
explorer "C:\Users\王子畅\Documents\New project\audit_multi_agent_rag\output\synthetic_data"
```

每张单据是一个 `.html` 文件，适合后续做：

- OCR 识别实验
- 单据到凭证勾稽
- RAG 引用测试
- 飞书回传附件

## 我建议你怎么找“更可靠”的数据

优先级建议是：

1. 先用这套模拟账，把审计 Agent 流程跑稳
2. 再从合法来源补“种子资料”
3. 用合法种子资料去扩展模板和业务类型

优先考虑这些合法来源：

1. 会计综合实训教材和配套案例
2. 金蝶、用友演示账套
3. 审计实训软件教学版
4. 你自己能合法持有的内部培训资料

不建议把来源不清的资料直接并入项目知识库或训练数据。

## 下一步最值得扩展的方向

1. 增加应付账款、预付账款、存货跌价准备、收入截止等专题账套
2. 增加固定资产卡片、应收应付明细台账
3. 增加银行流水、发票清单、合同台账
4. 把单据 HTML 再升级成更接近真实版式的 PDF
5. 把 `expected_findings.json` 接进自动评测，比较 Agent 输出和标准答案
