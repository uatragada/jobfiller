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

Both launchers create or reuse `.venv`, install Python dependencies when
needed, start the FastAPI backend, and serve the built dashboard. Set
`JOBFILLER_DEV_FRONTEND=true` or run `python start_jobfiller.py --dev-frontend`
when developing the React/Vite dashboard.

## Validation

Before opening a pull request or publishing a branch, run:

```powershell
python scripts/verify_release.py
```

To check startup without leaving background servers running:

```powershell
python start_jobfiller.py --smoke
```

For individual checks:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/doctor.py
python scripts/smoke_mcp.py
cd app\frontend
npm ci
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
