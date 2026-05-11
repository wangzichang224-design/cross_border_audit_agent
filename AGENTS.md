# audit_multi_agent_rag Agent Guide

This is a separate Python prototype for an audit-oriented multi-agent + RAG workflow. Do not mix its logic with the root `novel_game` app.

## Operating Mode

- Default development mode is `mock`.
- `autogen` mode depends on external packages and environment configuration.
- Favor keeping `mock` mode healthy so the prototype remains runnable without paid APIs.

## Entry Points

- CLI center: `python -m audit_multi_agent_rag.cli ...`
- Quick run: `python -m audit_multi_agent_rag.cli run --mode mock`
- Workpaper generation: `python -m audit_multi_agent_rag.cli workpaper --mode mock`
- Environment diagnostics: `python -m audit_multi_agent_rag.cli doctor`

## Module Map

- `audit_rag/agents.py`: agent setup and conversation orchestration
- `audit_rag/pipeline.py`: pipeline execution and result assembly
- `audit_rag/rag.py`: retrieval layer with fallback behavior
- `audit_rag/data_tools.py`: voucher parsing and anomaly detection
- `audit_rag/reporting.py`: Markdown output generation
- `audit_rag/config.py`: settings and path resolution

## Boundaries

- `output/` contains generated reports and workpapers; do not hand-edit them unless asked.
- `sample_data/` and `sample_knowledge/` are fixtures and seed knowledge, not production truth.
- Template discovery logic in `cli.py` may inspect the user's Desktop; be careful when changing filesystem behavior.

## Validation

- Prefer CLI-level checks after meaningful changes so the full prototype flow still works.
- Keep docs in `START_HERE.md`, `README.md`, and the development plans aligned if you change core usage.
