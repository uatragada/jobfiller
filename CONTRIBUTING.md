# Contributing

JobFiller is a local-first application. Treat candidate data, generated resumes,
cover letters, logs, workbooks, local databases, and runtime tokens as private
machine-local artifacts.

## Development Setup

From a fresh clone:

```powershell
python start_jobfiller.py
```

On Windows, the PowerShell launcher is also supported:

```powershell
.\Start-JobFiller.ps1
```

Both launchers create or reuse `.venv`, install Python and frontend
dependencies when needed, start the FastAPI backend, and start the Vite
dashboard.

## Validation

Before opening a pull request or publishing a branch, run:

```powershell
python scripts/verify_release.py
```

For individual checks:

```powershell
python -m pytest -q
python scripts/doctor.py
cd app\frontend
npm test
npm run build
```

## Data Boundary

Do not commit:

- `outputs/`
- `artifacts/`
- `.env` or `.env.*`
- `.venv/`
- `node_modules/`
- generated resumes, cover letters, workbooks, PDFs, CSVs, or databases

Use `examples/` for safe sample data and keep samples generic.

## Agent Integrations

Codex, Claude Code, and other MCP clients should use the MCP server documented
in [docs/mcp-integration.md](docs/mcp-integration.md). Agent workflows should
prepare materials only and must not submit applications.
