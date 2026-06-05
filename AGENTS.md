# Cross-Border Audit Agent Guide

This repository is a Python prototype for a trusted audit-oriented multi-agent workflow. Keep the mock path healthy so the project remains runnable in a classroom or interview without paid APIs.

## Entry Points

- Streamlit demo: `streamlit run streamlit_app.py`
- LAN demo: `streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501`
- CLI center: `python cli.py ...`
- Quick audit report: `python cli.py run --case-type cross_border --mode mock`
- Cash workpaper generation: `python cli.py workpaper --case-type cash --mode mock --materials-dir benchmarks/materials/case_001_minimal --template-root outputs/clean_templates --template-keyword 核心优化版`
- Environment diagnostics: `python cli.py doctor`

## Module Map

- `streamlit_app.py`: classroom UI, built-in demo path, and upload-to-workpaper workflow
- `cli.py`: command center for diagnostics, search, audit runs, and workpaper generation
- `audit_rag/agents.py`: Data Extractor, Compliance Checker, and Audit Partner roles
- `audit_rag/orchestrator.py`: Maker-Checker bounded review loop
- `audit_rag/hybrid_retriever.py`: BM25 + vector + RRF retrieval
- `audit_rag/reranker.py`: optional cross-encoder reranking
- `benchmarks/agent/cash_workpaper_filler.py`: formula-safe C cash workpaper filling engine
- `benchmarks/agent/pdf_confirmations.py`: bank confirmation PDF parser
- `assets/brand/`: original SVG/PNG project logo assets

## Boundaries

- `output/` contains generated reports, uploads, and workpapers; do not commit them.
- `benchmarks/ground_truth/` is hidden-answer material and should not be exposed to Agent runtime code.
- `outputs/clean_templates/` contains the clean workpaper template used by the demo.
- `mock` mode is the default demo path; `autogen` mode can call an external OpenAI-compatible API.

## Validation

Run these checks after meaningful changes:

```powershell
python -m pytest -q
python cli.py doctor
python cli.py where
python cli.py workpaper --case-type cash --mode mock --materials-dir benchmarks/materials/case_001_minimal --template-root outputs/clean_templates --template-keyword 核心优化版
```
