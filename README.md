# JobFiller

JobFiller is a local-first job application preparation dashboard. It imports job records, keeps a reusable candidate profile, tracks missing facts, and generates reviewable application artifacts for each role.

The app helps prepare materials only. It never submits applications or clicks a final submit button.

## Prerequisites

- Windows PowerShell
- Python 3.10 or newer
- Node.js 20.19 or newer
- `npm` (bundled with Node.js); `pnpm` is also supported
- Optional: [Ollama](https://ollama.com/) for local LLM grading

## Quick Start

From the repository root:

```powershell
.\Start-JobFiller.ps1
```

The startup script creates `.venv` when needed, installs Python dependencies from `requirements.txt`, installs frontend dependencies, starts the backend, and starts the Vite dashboard.

The first cold run may take longer while Python and Node packages install. After dependencies are installed, startup should normally be a single warm-start command.
By default the script restarts JobFiller's backend so code changes are picked up. Set `JOBFILLER_REUSE_BACKEND=true` before running the script only when you intentionally want to reuse an already-running backend.

- Dashboard: `http://127.0.0.1:5173`
- Backend API: printed by the startup script, usually `http://127.0.0.1:8001/api`
- Logs and generated artifacts: `artifacts/`
- Local settings and database: `outputs/`
- MCP runtime port file: `outputs/jobfiller-runtime.json`

Useful startup overrides:

```powershell
$env:JOBFILLER_BACKEND_PORT = "8001"
$env:JOBFILLER_BACKEND_PORT_MAX = "8005"
$env:JOBFILLER_FRONTEND_PORT = "5173"
$env:JOBFILLER_REUSE_BACKEND = "true"   # optional; reuse instead of restart
```

## Validation

Run the backend and frontend checks before sharing a branch or release:

```powershell
python -m pytest -q
cd app\frontend
npm ci
npm test
npm run build
```

The expected result is a passing backend suite, passing frontend browser-flow tests, and a successful Vite production build.

## Troubleshooting

- If the dashboard says it cannot fetch data, restart with `.\Start-JobFiller.ps1` and check the backend URL printed by the script. Do not set `JOBFILLER_REUSE_BACKEND=true` while debugging stale backend behavior.
- Backend logs are written to `artifacts/jobfiller-backend-current.log` and `artifacts/jobfiller-backend-current.err.log`.
- Frontend logs are written to `artifacts/jobfiller-frontend-current.log` and `artifacts/jobfiller-frontend-current.err.log`.
- If port `5173` is busy, stop the existing Vite process and rerun the start script.
- If backend ports `8001-8005` are busy, stop the conflicting local services or widen the scan with `JOBFILLER_BACKEND_PORT_MAX`.
- Set `JOBFILLER_PYTHON`, `JOBFILLER_NPM`, or `JOBFILLER_PNPM` to known executable paths if auto-detection picks the wrong runtime.

## Settings And Profile

Open **Settings** in the dashboard before generating materials. Add your candidate profile, preferred locations, scan keywords, and scan limits. Use **Profile Facts** and **Assist Upload** to add reusable, truthful facts from your own source materials.

Generated resumes and cover letters are drafts. Review every artifact before uploading it to an employer site.

## Optional Local LLM

JobFiller works without an Ollama model configured and falls back to deterministic grading checks. To enable local model grading:

```powershell
ollama serve
ollama pull <model-name>
$env:JOBFILLER_OLLAMA_MODEL = "<model-name>"
.\Start-JobFiller.ps1
```

If Ollama runs somewhere other than `http://127.0.0.1:11434`, set:

```powershell
$env:OLLAMA_URL = "http://127.0.0.1:11434"
```

You can also configure the Ollama URL and model from the dashboard Settings page.

## Bulk Imports

Agents and scripts can import multiple job records with `POST /api/imports/bulk`. See [docs/agent-import-contract.md](docs/agent-import-contract.md) for the payload and response contract.

## MCP For Codex And Claude Code

JobFiller includes a local stdio MCP server so Codex, Claude Code, and other MCP clients can export discovered jobs directly into the dashboard.

- MCP server: `integrations/mcp/jobfiller_mcp_server.py`
- Codex project config: `.codex/config.toml`
- Claude Code project config: `.mcp.json`
- Setup and tool details: [docs/mcp-integration.md](docs/mcp-integration.md)

The MCP tools call the same validated bulk-import API and do not submit applications.

Sample seed data lives in [examples/jobs.sample.json](examples/jobs.sample.json).
