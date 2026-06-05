# AGENTS.md - Cross-Border Audit Agent Notes

## Current Presentation Direction

The classroom demo, README, PPT, and runbook should focus on the **cross-border e-commerce fund-flow audit Agent**:

- synthetic Anker-style e-commerce fund-flow data;
- rule-based audit checks for cross-border transaction risks;
- optional DeepSeek / OpenAI-compatible audit narrative;
- settlement reconciliation;
- Markdown report, cleaned CSV, charts, and AI JSON for human review.

## Main Local Commands

```powershell
python cli.py doctor
python cli.py where
python cli.py run --case-type cross_border --mode mock
python cli.py search --query "跨境电商 收入确认 外币折算" --top-k 3
python -m pytest -q
```

## Demo Server

```powershell
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

Before class, update the PPT cover URL with the current WLAN IP by running:

```powershell
node scripts/build_class_demo_deck.mjs
```

## Important Paths

```text
streamlit_app.py
scripts/build_class_demo_deck.mjs
scripts/capture_demo_screenshots.py
docs/DEMO_RUNBOOK.md
docs/PROJECT_STRUCTURE.md
deliverables/cross-border-audit-agent-class-demo.pptx
```

## Git Hygiene

- Generated reports under `output/` should not be committed.
- PowerPoint lock files such as `deliverables/~$*.pptx` should not be committed.
- Keep `origin` pointed at `https://github.com/wangzichang224-design/cross_border_audit_agent.git`.
