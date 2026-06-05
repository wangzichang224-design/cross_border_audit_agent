#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SKILL_DIR = "C:/Users/王子畅/.codex/plugins/cache/openai-primary-runtime/presentations/26.601.10930/skills/presentations";
const THREAD_ID = process.env.CODEX_THREAD_ID || "manual-class-demo";
const WORKSPACE = path.join(ROOT, "outputs", THREAD_ID, "presentations", "cross-border-audit-agent");
const SLIDES_DIR = path.join(WORKSPACE, "slides");
const PREVIEW_DIR = path.join(WORKSPACE, "preview");
const LAYOUT_DIR = path.join(WORKSPACE, "layout");
const OUTPUT_DIR = path.join(ROOT, "deliverables");
const FINAL_PPTX = path.join(OUTPUT_DIR, "cross-border-audit-agent-class-demo.pptx");
const NODE = process.execPath;

function ps(command) {
  return spawnSync("powershell", ["-NoProfile", "-Command", command], {
    encoding: "utf8",
    windowsHide: true,
  }).stdout.trim();
}

function getWlanIp() {
  const ip = ps(`Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.InterfaceAlias -eq "WLAN" -and $_.AddressState -eq "Preferred" } |
    Select-Object -First 1 -ExpandProperty IPAddress`);
  return ip || "10.5.52.230";
}

function safePath(filePath) {
  return filePath.replaceAll("\\", "/");
}

function slideModule(n) {
  const padded = String(n).padStart(2, "0");
  return `import { buildSlide } from "./common.mjs";\n\nexport async function slide${padded}(presentation, ctx) {\n  return buildSlide(presentation, ctx, ${n});\n}\n`;
}

function commonModule({ demoUrl }) {
  const logo = safePath(path.join(ROOT, "assets", "brand", "crossagent-logo.png"));
  const mark = safePath(path.join(ROOT, "assets", "brand", "crossagent-mark.png"));
  const homeShot = safePath(path.join(ROOT, "docs", "assets", "streamlit-demo-home.png"));
  const resultShot = safePath(path.join(ROOT, "docs", "assets", "streamlit-demo-result.png"));

  return String.raw`
const C = {
  ink: "#0f172a",
  muted: "#64748b",
  line: "#dbe3ef",
  blue: "#2563eb",
  cyan: "#38bdf8",
  green: "#16a34a",
  violet: "#7c3aed",
  amber: "#b45309",
  red: "#dc2626",
  dark: "#08111f",
  paper: "#f8fafc",
  white: "#ffffff",
};

const ASSETS = {
  logo: ${JSON.stringify(logo)},
  mark: ${JSON.stringify(mark)},
  homeShot: ${JSON.stringify(homeShot)},
  resultShot: ${JSON.stringify(resultShot)},
};

const DEMO_URL = ${JSON.stringify(demoUrl)};

function bg(slide, ctx, fill = C.paper) {
  ctx.addShape(slide, { x: 0, y: 0, w: ctx.W, h: ctx.H, fill, line: ctx.line() });
}

function t(slide, ctx, text, x, y, w, h, opt = {}) {
  return ctx.addText(slide, {
    text,
    x, y, w, h,
    fontSize: opt.size ?? 24,
    color: opt.color ?? C.ink,
    bold: opt.bold ?? false,
    typeface: opt.face ?? "Microsoft YaHei",
    align: opt.align ?? "left",
    valign: opt.valign ?? "top",
    fill: opt.fill ?? "#00000000",
    line: opt.line ?? ctx.line(),
    insets: opt.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
    name: opt.name,
  });
}

function box(slide, ctx, x, y, w, h, opt = {}) {
  ctx.addShape(slide, {
    x, y, w, h,
    fill: opt.fill ?? C.white,
    line: opt.line ?? ctx.line(opt.stroke ?? C.line, opt.strokeWidth ?? 1),
    name: opt.name,
  });
}

function rule(slide, ctx, x, y, w, color = C.blue) {
  ctx.addShape(slide, { x, y, w, h: 3, fill: color, line: ctx.line() });
}

function title(slide, ctx, kicker, claim, speaker = "") {
  t(slide, ctx, kicker, 58, 34, 500, 24, { size: 13, color: C.blue, bold: true });
  t(slide, ctx, claim, 58, 64, 930, 76, { size: 31, color: C.ink, bold: true });
  if (speaker) t(slide, ctx, speaker, 1058, 38, 160, 26, { size: 13, color: C.muted, align: "right" });
  rule(slide, ctx, 58, 146, 160, C.blue);
}

function footer(slide, ctx, n) {
  t(slide, ctx, "Cross-Border Audit Agent · 数字金融课堂展示", 58, 690, 620, 18, { size: 10, color: "#94a3b8" });
  t(slide, ctx, String(n).padStart(2, "0"), 1180, 687, 42, 20, { size: 11, color: "#94a3b8", align: "right" });
}

function pill(slide, ctx, text, x, y, w, color = C.blue) {
  box(slide, ctx, x, y, w, 34, { fill: "#eff6ff", stroke: "#bfdbfe" });
  t(slide, ctx, text, x + 12, y + 8, w - 24, 18, { size: 12, color, bold: true, align: "center" });
}

function metric(slide, ctx, value, label, note, x, y, w, color = C.blue) {
  box(slide, ctx, x, y, w, 124, { fill: C.white, stroke: C.line });
  t(slide, ctx, value, x + 18, y + 15, w - 36, 40, { size: 32, color, bold: true });
  t(slide, ctx, label, x + 18, y + 57, w - 36, 22, { size: 15, color: C.ink, bold: true });
  t(slide, ctx, note, x + 18, y + 88, w - 36, 22, { size: 11, color: C.muted });
}

function card(slide, ctx, heading, body, x, y, w, h, color = C.blue) {
  box(slide, ctx, x, y, w, h, { fill: C.white, stroke: C.line });
  ctx.addShape(slide, { x, y, w: 5, h, fill: color, line: ctx.line() });
  t(slide, ctx, heading, x + 18, y + 16, w - 36, 24, { size: 16, color: C.ink, bold: true });
  t(slide, ctx, body, x + 18, y + 48, w - 36, h - 58, { size: 12.5, color: C.muted });
}

function step(slide, ctx, idx, heading, body, x, y, w, h, color = C.blue) {
  box(slide, ctx, x, y, w, h, { fill: C.white, stroke: C.line });
  t(slide, ctx, idx, x + 14, y + 12, 34, 24, { size: 14, color, bold: true });
  t(slide, ctx, heading, x + 50, y + 12, w - 62, 24, { size: 15, color: C.ink, bold: true });
  t(slide, ctx, body, x + 14, y + 48, w - 28, Math.max(24, h - 70), { size: 11.5, color: C.muted });
}

async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx, C.dark);
  await ctx.addImage(slide, { path: ASSETS.logo, x: 62, y: 54, w: 560, h: 160, fit: "contain", alt: "project logo" });
  t(slide, ctx, "可信财务 AI：把 Agent 关进确定性流程", 70, 242, 860, 62, { size: 36, color: C.white, bold: true });
  t(slide, ctx, "数字金融课堂展示 · 两人讲解 · 现场打开局域网前端演示", 74, 316, 780, 30, { size: 18, color: "#bfdbfe" });
  box(slide, ctx, 76, 392, 512, 92, { fill: "#0f1f33", stroke: "#1d4ed8" });
  t(slide, ctx, "演示地址", 100, 410, 120, 26, { size: 16, color: "#93c5fd", bold: true });
  t(slide, ctx, DEMO_URL, 100, 444, 440, 32, { size: 25, color: C.white, bold: true });
  pill(slide, ctx, "Speaker A：问题与系统", 720, 410, 220, "#38bdf8");
  pill(slide, ctx, "Speaker B：架构与范式", 960, 410, 220, "#a78bfa");
  t(slide, ctx, "开场先演示收敛后的底稿生成，再回到一个更真实的问题：为什么最初那个多 Agent 虽然能跑，但还不能被审计人员信任。", 74, 548, 980, 44, { size: 17, color: "#cbd5e1" });
  footer(slide, ctx, 1);
  return slide;
}

async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "LIVE DEMO", "先演示收敛后的底稿 Workflow，再讲为什么我不再相信自由 Agent。", "Speaker A");
  await ctx.addImage(slide, { path: ASSETS.resultShot, x: 58, y: 160, w: 760, h: 455, fit: "contain", alt: "Streamlit result screenshot" });
  card(slide, ctx, "课堂动作", "1. 打开封面 IP 地址\n2. 点击“使用内置示例生成底稿”\n3. 下载 Excel 工作底稿\n4. 回到 PPT 解释为什么这样设计", 858, 166, 330, 160, C.blue);
  card(slide, ctx, "这版演示是什么", "内置合成材料 + mock 模式 + Excel 底稿。重点展示可运行路径，不展示真实客户敏感数据。", 858, 354, 330, 120, C.green);
  card(slide, ctx, "它不是什么", "不是让模型自由查账、自由下结论；而是把材料、规则、证据和复核点串起来。", 858, 502, 330, 100, C.violet);
  footer(slide, ctx, 2);
  return slide;
}

async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "PERSONAL STARTING POINT", "最初的跨境资金多 Agent 能跑，但问题不是运行，而是不可信。", "Speaker A");
  const stages = [
    ["01", "第一版：多 Agent + 前端", "让不同 Agent 分别做数据提取、合规分析和审计合伙人复核，前端可以上传材料并输出风险判断。", C.blue],
    ["02", "发现问题：结论像真的", "模型说一笔交易有风险，但很难知道它基于哪条规则、哪段材料、哪个字段。", C.red],
    ["03", "需求收敛：先刷底稿", "把目标从“自由审计 Agent”收敛到自动填写底稿、报销单审核这类更稳定的流程节点。", C.green],
  ];
  stages.forEach((s, i) => {
    const x = 82 + i * 372;
    step(slide, ctx, s[0], s[1], s[2], x, 196, 300, 190, s[3]);
    if (i < stages.length - 1) t(slide, ctx, "→", x + 316, 270, 42, 34, { size: 28, color: "#94a3b8", bold: true, align: "center" });
  });
  box(slide, ctx, 150, 506, 900, 78, { fill: "#0f172a", stroke: "#0f172a" });
  t(slide, ctx, "能跑不等于能进高责任场景；财务 AI 的门槛不是“会回答”，而是“能被复核”。", 190, 530, 820, 30, { size: 22, color: C.white, bold: true, align: "center" });
  footer(slide, ctx, 3);
  return slide;
}

async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "HARD QUESTION 1", "一个风险结论如果不能回答三个问题，就不能进入审计流程。", "Speaker A");
  const qs = [
    ["这个结论从哪里来？", "需要看到原始字段、命中的规则、引用的材料片段，而不是只看一段自然语言判断。", C.blue],
    ["中间哪一步错了？", "错误可能来自数据提取、规则理解、RAG 检索、模型推理或最终汇总，必须能定位。", C.red],
    ["审计人员怎么复核？", "输出必须告诉复核人哪些证据充分、哪些证据缺口、哪些地方需要追加程序。", C.green],
  ];
  qs.forEach((q, i) => card(slide, ctx, q[0], q[1], 86 + i * 380, 196, 310, 210, q[2]));
  card(slide, ctx, "最初多 Agent 的结构性问题", "每个 Agent 都在生成自然语言，输出链路很长；一旦结论错了，很难判断是提取错、检索错、理解错，还是汇总时把语气写得太确定。", 166, 500, 850, 88, C.violet);
  footer(slide, ctx, 4);
  return slide;
}

async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "WHITE BOX", "财务 AI 的第一原则：黑盒必须变成白盒。", "Speaker A");
  const controls = [
    ["用了什么数据", "字段、表名、期间、金额口径"],
    ["命中哪条规则", "准则、制度、阈值、例外条件"],
    ["引用哪段证据", "原始材料片段和来源路径"],
    ["置信度与缺口", "低置信度原因和缺失材料"],
    ["哪里人工复核", "复核动作、责任人、留痕"],
  ];
  controls.forEach((c, i) => {
    const x = 70 + i * 230;
    metric(slide, ctx, String(i + 1).padStart(2, "0"), c[0], c[1], x, 190, 190, [C.blue, C.green, C.violet, C.amber, C.red][i]);
  });
  box(slide, ctx, 124, 406, 940, 92, { fill: "#eff6ff", stroke: "#bfdbfe" });
  t(slide, ctx, "审计和报销审核本质上都是高责任场景。AI 不能只给结论，必须把判断过程拆开，让人能追溯、能质疑、能复核。", 168, 430, 850, 44, { size: 22, color: C.ink, bold: true, align: "center" });
  card(slide, ctx, "一句话讲法", "财务 AI 不是把专业判断交给模型，而是让模型先做材料整理、证据引用和初步判断，再把低确定性的部分交还给人。", 220, 540, 760, 78, C.blue);
  footer(slide, ctx, 5);
  return slide;
}

async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "WORKFLOW FIRST", "在财务场景里，Workflow 通常优于完全自主 Agent。", "Speaker A");
  const steps = [
    ["01", "材料识别", "票据/流水/底稿"],
    ["02", "制度检索", "准则/报销政策"],
    ["03", "字段比对", "金额/日期/主体"],
    ["04", "异常判断", "规则 + 模型"],
    ["05", "证据引用", "来源留痕"],
    ["06", "人工复核", "低置信度兜底"],
    ["07", "结果归档", "Excel/日志"],
  ];
  steps.forEach((s, i) => {
    const x = 56 + i * 168;
    step(slide, ctx, s[0], s[1], s[2], x, 182, 134, 122, [C.blue, C.green, C.violet, C.amber, C.blue, C.red, C.green][i]);
    if (i < steps.length - 1) t(slide, ctx, "→", x + 136, 224, 30, 26, { size: 20, color: "#94a3b8", bold: true, align: "center" });
  });
  card(slide, ctx, "Agent 的位置", "Agent 只应该在某些节点里做智能任务，比如识别异常、检索制度、解释证据，而不是自己控制整个财务流程。", 112, 384, 430, 120, C.blue);
  box(slide, ctx, 612, 382, 520, 126, { fill: "#0f172a", stroke: "#0f172a" });
  t(slide, ctx, "财务 AI 不是让模型自由发挥，而是把模型的不确定性，关进一个确定性的流程里。", 648, 416, 448, 58, { size: 24, color: C.white, bold: true, align: "center" });
  footer(slide, ctx, 6);
  return slide;
}

async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "WHY NOT FULL AUTO", "全流程自动化很难，因为三件事绕不开。", "Speaker A");
  card(slide, ctx, "幻觉不可接受", "财务和审计不是写作场景。模型一旦把缺失证据说成确定事实，后果会直接进入工作底稿和复核链条。", 86, 186, 310, 210, C.red);
  card(slide, ctx, "数据高度保密", "真实客户材料不适合随意走远端 API 或公开 Agent 工具。更现实的方向是脱敏、权限隔离和私有化部署。", 486, 186, 310, 210, C.blue);
  card(slide, ctx, "责任归属必须是人", "像实习生底稿一样，最后需要正式人员复核把关。Agent 只能辅助，不能替代责任主体。", 886, 186, 310, 210, C.green);
  box(slide, ctx, 156, 496, 880, 88, { fill: "#fff7ed", stroke: "#fed7aa" });
  t(slide, ctx, "所以我不把这个项目包装成“全自动审计”，而是讲成可信辅助：降低低风险重复劳动，把关键判断留给人。", 204, 524, 790, 34, { size: 22, color: C.ink, bold: true, align: "center" });
  footer(slide, ctx, 7);
  return slide;
}

async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "WHY IT STILL MATTERS", "不能全自动，不代表没有商业价值：替代实习生 dirtywork 可能更早发生。", "Speaker A");
  box(slide, ctx, 128, 170, 940, 92, { fill: "#0f172a", stroke: "#0f172a" });
  t(slide, ctx, "人做的时间 -（AI 做的时间 + 人核对并修改的时间）> 0", 166, 196, 870, 38, { size: 28, color: C.white, bold: true, align: "center" });
  card(slide, ctx, "最先被改造的任务", "货币资金底稿、简单抽凭、复制粘贴、筛选和查找函数等高频模板化工作。", 86, 330, 310, 170, C.blue);
  card(slide, ctx, "Harness 约束降低风险", "用模板、字段 schema、规则扫描、cell_map 和 mock/私有部署，把模型限制在可检查的动作里。", 486, 330, 310, 170, C.violet);
  card(slide, ctx, "复核人兜底责任", "产出像实习生交底稿一样进入 Maker-Checker 流程；AI 负责提效，人负责最终判断。", 886, 330, 310, 170, C.green);
  t(slide, ctx, "课堂里可以把这个观点讲得更尖锐：全流程自动化很难，但低风险重复劳动会先被重构。", 134, 590, 940, 28, { size: 20, color: C.ink, bold: true, align: "center" });
  footer(slide, ctx, 8);
  return slide;
}

async function slide09(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "CURRENT DESIGN", "这版项目就是把最初的大问题收敛成一个可复核的底稿 Workflow。", "Speaker A / B");
  const stages = [
    ["01", "材料包", "合成案例/上传文件"],
    ["02", "规则扫描", "8 类跨境风险"],
    ["03", "RAG 证据", "准则片段/fallback"],
    ["04", "三 Agent", "提取/合规/复核"],
    ["05", "底稿输出", "Excel/Markdown"],
    ["06", "人工复核", "证据缺口留痕"],
  ];
  stages.forEach((s, i) => {
    const x = 58 + i * 196;
    step(slide, ctx, s[0], s[1], s[2], x, 184, 150, 118, [C.blue, C.green, C.violet, C.amber, C.blue, C.red][i]);
    if (i < stages.length - 1) t(slide, ctx, "→", x + 152, 224, 32, 26, { size: 20, color: "#94a3b8", bold: true, align: "center" });
  });
  await ctx.addImage(slide, { path: ASSETS.homeShot, x: 92, y: 386, w: 430, h: 210, fit: "contain", alt: "Streamlit home screenshot" });
  metric(slide, ctx, "52", "tests passed", "pytest 验证基础链路", 590, 388, 178, C.green);
  metric(slide, ctx, "Mock", "默认演示模式", "课堂不调用远端 API", 800, 388, 178, C.blue);
  metric(slide, ctx, "Cell Map", "公式区保护", "只写入模板可填区域", 1010, 388, 178, C.violet);
  footer(slide, ctx, 9);
  return slide;
}

async function slide10(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "AGENT PATTERNS", "后半段把主流 Agent 范式讲简单：从自由对话，到流程中的智能节点。", "Speaker B");
  card(slide, ctx, "Single Agent", "一个模型调用工具完成任务。适合问题小、风险低、上下文边界清楚的场景。", 74, 178, 250, 240, C.blue);
  card(slide, ctx, "Workflow Agent", "固定步骤编排，输入输出可检查\n适合财务和审计流程", 366, 178, 250, 240, C.green);
  card(slide, ctx, "Multi-Agent", "用角色拆分任务，例如事实提取、合规判断、复核质疑。适合需要多视角检查的问题。", 658, 178, 250, 240, C.violet);
  card(slide, ctx, "Human-in-the-loop", "低置信度、证据缺口和最终判断交给人\n高责任业务必须保留", 950, 178, 250, 240, C.amber);
  box(slide, ctx, 150, 528, 900, 62, { fill: "#eff6ff", stroke: "#bfdbfe" });
  t(slide, ctx, "本项目组合：Workflow 定顺序，RAG 给证据，多 Agent 给视角，人工复核定责任。", 198, 548, 805, 26, { size: 22, color: C.ink, bold: true, align: "center" });
  footer(slide, ctx, 10);
  return slide;
}

async function slide11(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "FLOW + REPO", "一页看懂：业务流程怎么跑，代码结构怎么承接。", "Speaker B");
  t(slide, ctx, "运行流程", 78, 166, 180, 24, { size: 17, color: C.blue, bold: true });
  t(slide, ctx, "项目结构", 690, 166, 180, 24, { size: 17, color: C.green, bold: true });

  const flow = [
    ["输入层", "CSV / PDF / 示例材料\n审计知识片段", C.blue],
    ["Pipeline", "data_tools 结构化\nRAG 检索与 fallback", C.green],
    ["Agent 讨论", "Data Extractor\nCompliance Checker\nAudit Partner", C.violet],
    ["输出层", "Markdown 报告\nExcel 标准底稿\n人工复核点", C.amber],
  ];
  flow.forEach((f, i) => {
    const y = 206 + i * 100;
    box(slide, ctx, 76, y, 470, 72, { fill: i % 2 === 0 ? C.white : "#f1f5f9", stroke: C.line });
    t(slide, ctx, f[0], 102, y + 14, 120, 22, { size: 15, color: f[2], bold: true });
    t(slide, ctx, f[1], 246, y + 13, 260, 42, { size: 13, color: C.ink });
    if (i < flow.length - 1) t(slide, ctx, "↓", 304, y + 76, 28, 24, { size: 18, color: "#94a3b8", bold: true, align: "center" });
  });

  box(slide, ctx, 608, 206, 548, 380, { fill: "#ffffff", stroke: C.line });
  const tree = [
    ["audit_rag/", "核心能力包", C.blue],
    ["  agents.py", "三 Agent 提示词 / mock 响应", C.violet],
    ["  pipeline.py", "流程编排：材料 → RAG → Agent", C.green],
    ["  rag.py", "ChromaDB 检索 + 关键词 fallback", C.green],
    ["  data_tools.py", "凭证加载与风险规则扫描", C.amber],
    ["  reporting.py", "Markdown 工作底稿草稿", C.blue],
    ["cli.py / streamlit_app.py", "命令行入口 / 课堂前端", C.blue],
    ["benchmarks/", "合成材料与隔离评测设计", C.red],
    ["outputs/", "生成报告与 Excel 底稿", C.green],
    ["docs/ & assets/", "README 截图、Logo、说明文档", C.violet],
  ];
  tree.forEach((row, i) => {
    const y = 228 + i * 32;
    t(slide, ctx, row[0], 636, y, 210, 22, { size: 12.5, color: row[2], bold: i === 0 || !row[0].startsWith("  "), face: "Consolas" });
    t(slide, ctx, row[1], 858, y, 260, 22, { size: 12.5, color: C.muted });
  });

  box(slide, ctx, 138, 606, 904, 48, { fill: "#eff6ff", stroke: "#bfdbfe" });
  t(slide, ctx, "讲法：左边说明数据和证据如何流动，右边说明每一层在仓库里对应哪些文件，避免只讲概念不讲工程落点。", 172, 620, 836, 22, { size: 17, color: C.ink, bold: true, align: "center" });
  footer(slide, ctx, 11);
  return slide;
}

async function slide12(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx, C.dark);
  await ctx.addImage(slide, { path: ASSETS.mark, x: 92, y: 88, w: 130, h: 130, fit: "contain", alt: "project mark" });
  t(slide, ctx, "总结：能跑是第一步，可信才是财务 AI 的生产门槛。", 270, 94, 850, 72, { size: 36, color: C.white, bold: true });
  t(slide, ctx, "这个项目的价值不是证明 Agent 可以全自动审计，而是证明它能在确定流程里承担可复核的高频工作。", 274, 188, 820, 44, { size: 20, color: "#cbd5e1" });
  const next = [
    ["评测器", "合成数据 + Precision / Recall / F1"],
    ["对比实验", "和真实审计师底稿做差异分析"],
    ["底稿扩展", "应收、存货、收入截止"],
    ["私有化治理", "模型、权限、日志、审计轨迹"],
  ];
  next.forEach((n, i) => card(slide, ctx, n[0], n[1], 104 + i * 278, 322, 220, 130, [C.blue, C.green, C.violet, C.amber][i]));
  box(slide, ctx, 146, 532, 980, 70, { fill: "#0f1f33", stroke: "#1d4ed8" });
  t(slide, ctx, "Q&A 准备：为什么不全自动？怎么控幻觉？数据是否外发？谁承担最终责任？", 190, 554, 890, 28, { size: 21, color: C.white, bold: true, align: "center" });
  footer(slide, ctx, 12);
  return slide;
}

const slides = [slide01, slide02, slide03, slide04, slide05, slide06, slide07, slide08, slide09, slide10, slide11, slide12];

export async function buildSlide(presentation, ctx, n) {
  return slides[n - 1](presentation, ctx);
}
`;
}

async function main() {
  const wlanIp = getWlanIp();
  const demoUrl = `http://${wlanIp}:8501`;
  await fs.rm(WORKSPACE, { recursive: true, force: true });
  await fs.mkdir(SLIDES_DIR, { recursive: true });
  await fs.mkdir(OUTPUT_DIR, { recursive: true });
  await fs.writeFile(path.join(SLIDES_DIR, "common.mjs"), commonModule({ demoUrl }), "utf8");
  for (let i = 1; i <= 12; i += 1) {
    await fs.writeFile(path.join(SLIDES_DIR, `slide-${String(i).padStart(2, "0")}.mjs`), slideModule(i), "utf8");
  }

  const buildScript = path.join(SKILL_DIR, "scripts", "build_artifact_deck.mjs");
  const result = spawnSync(
    NODE,
    [
      buildScript,
      "--workspace", WORKSPACE,
      "--slides-dir", SLIDES_DIR,
      "--out", FINAL_PPTX,
      "--preview-dir", PREVIEW_DIR,
      "--layout-dir", path.join(LAYOUT_DIR, "final"),
      "--contact-sheet", path.join(PREVIEW_DIR, "contact-sheet.png"),
      "--manifest", path.join(WORKSPACE, "artifact-build-manifest.json"),
      "--slide-count", "12",
      "--slide-size", "1280x720",
    ],
    {
      cwd: ROOT,
      encoding: "utf8",
      env: {
        ...process.env,
        HOME: process.env.HOME || process.env.USERPROFILE || "C:/Users/王子畅",
        PYTHON: "python",
      },
      windowsHide: true,
    },
  );

  if (result.status !== 0) {
    process.stdout.write(result.stdout || "");
    process.stderr.write(result.stderr || "");
    throw new Error(`Deck build failed with status ${result.status}`);
  }

  const manifest = JSON.parse(result.stdout);
  await fs.writeFile(
    path.join(WORKSPACE, "class-demo-build-summary.json"),
    JSON.stringify({ demoUrl, ...manifest }, null, 2) + "\n",
    "utf8",
  );
  console.log(JSON.stringify({ demoUrl, finalPptx: FINAL_PPTX, contactSheet: path.join(PREVIEW_DIR, "contact-sheet.png") }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
