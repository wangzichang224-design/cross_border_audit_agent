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
  t(slide, ctx, claim, 58, 64, 900, 68, { size: 31, color: C.ink, bold: true });
  if (speaker) t(slide, ctx, speaker, 1078, 38, 140, 26, { size: 13, color: C.muted, align: "right" });
  rule(slide, ctx, 58, 132, 160, C.blue);
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
  t(slide, ctx, value, x + 18, y + 16, w - 36, 40, { size: 33, color, bold: true });
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
  t(slide, ctx, "可信多 Agent 审计系统：从跨境资金流到 Excel 底稿", 70, 242, 860, 62, { size: 34, color: C.white, bold: true });
  t(slide, ctx, "数字金融课堂展示 · 两人讲解 · 现场打开局域网前端演示", 74, 316, 780, 30, { size: 18, color: "#bfdbfe" });
  box(slide, ctx, 76, 392, 512, 92, { fill: "#0f1f33", stroke: "#1d4ed8" });
  t(slide, ctx, "演示地址", 100, 410, 120, 26, { size: 16, color: "#93c5fd", bold: true });
  t(slide, ctx, DEMO_URL, 100, 444, 440, 32, { size: 25, color: C.white, bold: true });
  pill(slide, ctx, "Speaker A：问题与系统", 720, 410, 220, "#38bdf8");
  pill(slide, ctx, "Speaker B：架构与范式", 960, 410, 220, "#a78bfa");
  t(slide, ctx, "开场先演示，随后解释为什么做、怎么控风险、以及 Agent 主流架构如何落在审计场景里。", 74, 548, 980, 44, { size: 17, color: "#cbd5e1" });
  footer(slide, ctx, 1);
  return slide;
}

async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "LIVE DEMO", "先给同学看到可运行结果，再解释系统为什么可信。", "Speaker A");
  await ctx.addImage(slide, { path: ASSETS.resultShot, x: 58, y: 160, w: 760, h: 455, fit: "contain", alt: "Streamlit result screenshot" });
  card(slide, ctx, "课堂动作", "1. 打开封面 IP 地址\n2. 点击“使用内置示例生成底稿”\n3. 下载 Excel 工作底稿\n4. 回到 PPT 解释底层链路", 858, 166, 330, 160, C.blue);
  card(slide, ctx, "演示边界", "默认 mock 模式，不调用远端模型；示例材料来自仓库合成数据；适合课堂网络环境。", 858, 354, 330, 120, C.green);
  card(slide, ctx, "一句话讲法", "这不是聊天机器人，而是把材料、规则、证据和人工复核串起来的审计工作流。", 858, 502, 330, 100, C.violet);
  footer(slide, ctx, 2);
  return slide;
}

async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "HARD QUESTION 1", "数字金融里的 AI 审计，难点不是回答，而是可被信任。", "Speaker A");
  const rows = [
    ["普通聊天机器人", "输入问题后直接生成答案", "结论难复核，证据链和数据边界不稳定", C.amber],
    ["可信审计 Agent", "先结构化材料，再引用依据和输出底稿", "可追溯、可复核、可控制外发和公式写入", C.blue],
  ];
  rows.forEach((r, i) => {
    const y = 176 + i * 175;
    box(slide, ctx, 80, y, 1040, 132, { fill: i === 0 ? "#fff7ed" : "#eff6ff", stroke: i === 0 ? "#fed7aa" : "#bfdbfe" });
    t(slide, ctx, r[0], 112, y + 28, 220, 32, { size: 22, color: r[3], bold: true });
    t(slide, ctx, r[1], 376, y + 24, 260, 52, { size: 18, color: C.ink, bold: true });
    t(slide, ctx, r[2], 704, y + 24, 360, 70, { size: 16, color: C.muted });
  });
  t(slide, ctx, "核心观点：审计场景不能让 LLM 直接“拍板”，它应该被放进一个有材料边界、证据边界和人工复核边界的工作流。", 96, 526, 980, 50, { size: 20, color: C.ink, bold: true });
  footer(slide, ctx, 3);
  return slide;
}

async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "HARD QUESTION 2", "幻觉、证据缺口、公式误写和数据外发，都要在架构里被前置处理。", "Speaker A");
  const items = [
    ["幻觉结论", "RAG 依据 + mock 默认 + 人工复核", C.blue],
    ["证据缺口", "Audit Partner 质疑待补充证据", C.violet],
    ["公式误写", "cell_map 只允许写入可填区域", C.green],
    ["数据外发", "课堂 demo 不调用 API，真实资料先脱敏", C.amber],
  ];
  items.forEach((it, i) => {
    const x = 72 + (i % 2) * 548;
    const y = 176 + Math.floor(i / 2) * 178;
    card(slide, ctx, it[0], it[1], x, y, 486, 126, it[2]);
  });
  box(slide, ctx, 132, 548, 920, 64, { fill: "#0f172a", stroke: "#0f172a" });
  t(slide, ctx, "产品原则：让模型输出建议，让系统保留证据，让人负责最终判断。", 168, 566, 850, 30, { size: 22, color: C.white, bold: true, align: "center" });
  footer(slide, ctx, 4);
  return slide;
}

async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "SYSTEM MAP", "系统不是一层 LLM，而是“材料到审计结论”的五段链路。", "Speaker A");
  const stages = [
    ["01", "材料结构化", "试算平衡表\n序时账\n函证回函"],
    ["02", "规则扫描", "金额聚合\n余额调节\n风险识别"],
    ["03", "RAG 依据", "CAS / CPA\n跨境知识\nfallback 检索"],
    ["04", "多 Agent", "提取事实\n合规分析\n合伙人复核"],
    ["05", "底稿输出", "Markdown 报告\nExcel 工作底稿\nCheck 行"],
  ];
  stages.forEach((s, i) => {
    const x = 58 + i * 236;
    step(slide, ctx, s[0], s[1], s[2], x, 220, 188, 154, [C.blue, C.green, C.violet, C.amber, C.blue][i]);
    if (i < stages.length - 1) t(slide, ctx, "→", x + 194, 270, 36, 32, { size: 28, color: "#94a3b8", bold: true });
  });
  await ctx.addImage(slide, { path: ASSETS.homeShot, x: 92, y: 430, w: 480, h: 210, fit: "contain", alt: "Streamlit home screenshot" });
  card(slide, ctx, "当前演示链路", "前端一键示例走的是同一套 cash workpaper filler。上传真实材料时，只是把材料包从内置样例换成用户上传文件。", 640, 448, 470, 140, C.green);
  footer(slide, ctx, 5);
  return slide;
}

async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "TRUST DESIGN", "可信不是一句口号，而是四个控制点同时工作。", "Speaker A");
  metric(slide, ctx, "Mock", "默认本地演示", "无 API Key 也可运行", 74, 184, 244, C.blue);
  metric(slide, ctx, "Cell Map", "公式区保护", "只写模板可填区域", 368, 184, 244, C.green);
  metric(slide, ctx, "RAG", "证据可追溯", "检索依据进入报告", 662, 184, 244, C.violet);
  metric(slide, ctx, "Review", "Maker-Checker", "结构化 verdict + 重试", 956, 184, 244, C.amber);
  card(slide, ctx, "课堂要强调的边界", "AI 辅助的是材料整理、风险识别和说明生成；最终审计判断仍然由专业人员负责。这个边界让项目更像真实的 B2B AI 产品，而不是玩具 demo。", 160, 372, 900, 126, C.blue);
  card(slide, ctx, "产品经理视角", "好的 Agent 不是“全自动替代人”，而是把高频、重复、可结构化的审计动作做成可信辅助，并把低置信度问题交回人工。", 160, 524, 900, 86, C.green);
  footer(slide, ctx, 6);
  return slide;
}

async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "ENGINEERING EVIDENCE", "当前工程证据能支撑课堂展示，而不是只停留在概念图。", "Speaker A / B");
  metric(slide, ctx, "52", "pytest passed", "检索、复核、底稿填表", 82, 180, 300, C.green);
  metric(slide, ctx, "8", "跨境风险类别", "关联方、NRV、汇兑、关税等", 490, 180, 300, C.blue);
  metric(slide, ctx, "3", "Agent roles", "Data / Compliance / Partner", 898, 180, 300, C.violet);
  card(slide, ctx, "Benchmark 隔离", "materials 可见，ground_truth 不可见。后续可以接 Precision / Recall / F1，防止 Agent 看到答案。", 110, 382, 470, 128, C.blue);
  card(slide, ctx, "生成物隔离", "output/ 下的报告、上传材料和底稿被 Git 忽略，避免把运行产物和课堂截图混入代码历史。", 660, 382, 470, 128, C.green);
  footer(slide, ctx, 7);
  return slide;
}

async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "THREE AGENTS", "三 Agent 分工模拟审计团队，而不是让一个模型承担所有角色。", "Speaker B");
  card(slide, ctx, "Data Extractor", "读取材料和凭证\n提取异常金额、账户、平台、币种\n输出：已识别事实 + 建议程序", 78, 188, 330, 240, C.blue);
  card(slide, ctx, "Compliance Checker", "匹配 CAS / CPA / OECD 依据\n标注准则和合规关注点\n输出：依据编号 + 合规分析", 476, 188, 330, 240, C.green);
  card(slide, ctx, "Audit Partner", "质疑证据链和资料缺口\n区分事实、推断、待补充资料\n输出：最终意见 + 后续程序", 874, 188, 330, 240, C.violet);
  t(slide, ctx, "讲法：Agent 的价值不在“人格化”，而在把不同专业视角拆成可追踪的审计任务。", 124, 548, 1000, 42, { size: 22, color: C.ink, bold: true, align: "center" });
  footer(slide, ctx, 8);
  return slide;
}

async function slide09(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "RAG LAYER", "RAG 的作用是把模型回答拉回审计依据，而不是装饰性检索。", "Speaker B");
  const layers = [
    ["Knowledge", "CPA / CAS / 跨境审计片段", C.blue],
    ["Retrieve", "BM25 + vector + RRF", C.green],
    ["Rerank", "cross-encoder optional", C.violet],
    ["Fallback", "关键词 fallback 保底", C.amber],
    ["Report", "依据片段进入 Markdown / Agent 上下文", C.blue],
  ];
  layers.forEach((l, i) => {
    const y = 168 + i * 82;
    step(slide, ctx, String(i + 1).padStart(2, "0"), l[0], l[1], 90, y, 430, 70, l[2]);
  });
  card(slide, ctx, "为什么要 fallback", "课堂/本地环境里向量库、模型或 reranker 都可能暂时不可用；fallback 让 demo 不因为依赖缺失而整体崩掉。", 620, 188, 470, 130, C.green);
  card(slide, ctx, "为什么要保留来源", "审计不是写作文。每个风险说明都需要能回看材料、准则或知识片段，方便复核和追问。", 620, 362, 470, 130, C.blue);
  footer(slide, ctx, 9);
  return slide;
}

async function slide10(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "AGENT PATTERNS", "把主流 Agent 范式放回这套项目，就很容易讲清楚。", "Speaker B");
  card(slide, ctx, "Rule Engine", "确定性过滤：金额阈值、余额核对、字段规范。\n适合可枚举、可解释、可测试的审计规则。", 74, 178, 250, 240, C.amber);
  card(slide, ctx, "Workflow", "流程编排：材料摄入、检索、复核、输出。\n适合把复杂动作拆成稳定步骤。", 366, 178, 250, 240, C.blue);
  card(slide, ctx, "Multi-Agent", "角色分工：事实提取、合规判断、合伙人质疑。\n适合需要多视角检查的问题。", 658, 178, 250, 240, C.violet);
  card(slide, ctx, "Human-in-the-loop", "人工兜底：证据缺口、低置信度、最终判断。\n适合高责任、高风险业务。", 950, 178, 250, 240, C.green);
  t(slide, ctx, "本项目组合：规则引擎处理确定性，Workflow 保证顺序，Multi-Agent 生成审计判断，HITL 保留责任边界。", 110, 524, 1010, 58, { size: 22, color: C.ink, bold: true, align: "center" });
  footer(slide, ctx, 10);
  return slide;
}

async function slide11(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  title(slide, ctx, "PRODUCTIZATION", "从课堂 Demo 到企业 AI 产品，重点是边界、指标和部署。", "Speaker B");
  const columns = [
    ["边界", "可信辅助\n不替代审计结论\n敏感材料默认本地"],
    ["指标", "材料解析成功率\n风险命中率\n人工节省时间\n复核退回率"],
    ["部署", "私有化模型\n权限与日志\n模板版本控制\n审计轨迹留存"],
  ];
  columns.forEach((c, i) => card(slide, ctx, c[0], c[1], 114 + i * 360, 200, 300, 260, [C.blue, C.green, C.violet][i]));
  card(slide, ctx, "数字金融价值", "企业效率提升不是来自“让模型自己做审计”，而是来自把材料整理、证据检索、底稿生成和复核流转做成可控闭环。", 164, 520, 900, 86, C.blue);
  footer(slide, ctx, 11);
  return slide;
}

async function slide12(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx, C.dark);
  await ctx.addImage(slide, { path: ASSETS.mark, x: 92, y: 88, w: 130, h: 130, fit: "contain", alt: "project mark" });
  t(slide, ctx, "总结：可信 Agent 的关键，是把 AI 放进可检查的业务流程。", 270, 96, 840, 72, { size: 36, color: C.white, bold: true });
  t(slide, ctx, "下一步可以继续扩展：评测器、更多审计底稿、私有化模型、权限与审计日志。", 274, 188, 820, 34, { size: 20, color: "#cbd5e1" });
  const next = [
    ["评测器", "Precision / Recall / F1"],
    ["底稿扩展", "应收、存货、收入截止"],
    ["私有化", "Qwen / Ollama / vLLM"],
    ["治理", "权限、日志、人工签批"],
  ];
  next.forEach((n, i) => card(slide, ctx, n[0], n[1], 104 + i * 278, 322, 220, 130, [C.blue, C.green, C.violet, C.amber][i]));
  box(slide, ctx, 168, 532, 940, 70, { fill: "#0f1f33", stroke: "#1d4ed8" });
  t(slide, ctx, "Q&A 重点准备：为什么不直接全自动？如何控幻觉？为什么要保留人工复核？", 210, 554, 850, 28, { size: 21, color: C.white, bold: true, align: "center" });
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
