# JobFiller

JobFiller is a local-first job application preparation dashboard. It imports job records, keeps a reusable candidate profile, tracks missing facts, and generates reviewable application artifacts for each role.

The app helps prepare materials only. It never submits applications or clicks a final submit button.

## Prerequisites

- Python 3.10 or newer
- Node.js 20.19 or newer
- `npm` (bundled with Node.js); `pnpm` is also supported
- Optional: [Ollama](https://ollama.com/) for local LLM grading

## Quick Start

From the repository root:

```powershell
.\Start-JobFiller.ps1
```

For macOS, Linux, or a Python-only startup path on Windows:

```bash
python start_jobfiller.py
```

Both startup scripts create `.venv` when needed, install runtime Python dependencies from `requirements.txt`, install frontend dependencies, start the backend, and start the Vite dashboard.

The first cold run may take longer while Python and Node packages install. After dependencies are installed, startup should normally be a single warm-start command.
By default the PowerShell script restarts JobFiller's backend so code changes are picked up. Set `JOBFILLER_REUSE_BACKEND=true` before running the PowerShell script only when you intentionally want to reuse an already-running backend. The Python runner is non-destructive and chooses free ports when defaults are busy.
For release checks or quick local confidence without leaving servers running, use `python start_jobfiller.py --smoke`.

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
$env:JOBFILLER_FRONTEND_PORT_MAX = "5193"
$env:JOBFILLER_REUSE_BACKEND = "true"   # optional; reuse instead of restart
```

## Validation

Run the backend and frontend checks before sharing a branch or release:

```powershell
python scripts/verify_release.py
```

Or run the underlying checks individually:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m py_compile start_jobfiller.py scripts\doctor.py scripts\verify_release.py
python scripts/doctor.py
cd app\frontend
npm ci
npm test
npm run build
```

The expected result is a passing backend suite, passing frontend browser-flow tests, and a successful Vite production build.
`python scripts/verify_release.py` also runs `python start_jobfiller.py --smoke` to prove the app reaches a usable dashboard/API state and cleans up its child processes.
`python scripts/doctor.py` performs a fast clone-readiness check for Python, Node, package manager, config files, and privacy-sensitive ignore rules.

## Troubleshooting

- If the dashboard says it cannot fetch data, restart with `.\Start-JobFiller.ps1` or `python start_jobfiller.py` and check the backend URL printed by the script. Do not set `JOBFILLER_REUSE_BACKEND=true` while debugging stale backend behavior.
- Backend logs are written to `artifacts/jobfiller-backend-current.log` and `artifacts/jobfiller-backend-current.err.log`.
- Frontend logs are written to `artifacts/jobfiller-frontend-current.log` and `artifacts/jobfiller-frontend-current.err.log`.
- If port `5173` is busy, stop the existing Vite process and rerun the start script.
- If backend ports `8001-8005` are busy, stop the conflicting local services or widen the scan with `JOBFILLER_BACKEND_PORT_MAX`.
- If frontend ports `5173-5193` are busy when using the Python runner, widen the scan with `JOBFILLER_FRONTEND_PORT_MAX`.
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
- Practical agent prompts: [docs/agent-workflows.md](docs/agent-workflows.md)

The MCP tools call the same validated bulk-import API and do not submit applications.

Sample seed data lives in [examples/jobs.sample.json](examples/jobs.sample.json).
Sample MCP export data lives in [examples/mcp-export.sample.json](examples/mcp-export.sample.json).

## Publishing

This checkout includes GitHub Actions CI and a publish helper for turning a local
repo into a GitHub repository after `gh auth login`:

```powershell
.\scripts\Publish-JobFiller.ps1 -RepositoryName jobfiller -Visibility public
```

See [docs/publishing.md](docs/publishing.md) and [docs/release-checklist.md](docs/release-checklist.md).

## Privacy And License

JobFiller stores local candidate data, generated resumes, generated cover letters,
runtime tokens, logs, and workbooks under ignored directories such as `outputs/`
and `artifacts/`. Review generated files before sharing them.

JobFiller is distributed under the MIT license; see [LICENSE](LICENSE).
Contributor and security guidance live in [CONTRIBUTING.md](CONTRIBUTING.md)
and [SECURITY.md](SECURITY.md).
