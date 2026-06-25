# Developer Guide

Last updated: 2026-06-24

## Service Summary

JobFiller is a local FastAPI + React application for preparing job application materials. It stores local candidate and job data in SQLite, generates local artifacts, and exposes a stdio MCP bridge for job-discovery agents.

**Service type:** local web app, API, background processor, MCP stdio server.

**Primary consumers:** the bundled React dashboard, local MCP clients such as Codex and Claude Code, browser-assisted scripts, and user-run API scripts.

**External dependencies:** Python packages from `requirements.txt`, optional Node/npm for frontend development, optional Ollama for local grading, optional `tectonic` for LaTeX compilation, optional GitHub CLI for publishing.

## Repository Orientation

```text
C:\path\to\JobFiller\
+-- app\
|   +-- backend\                 # FastAPI app, models, services, settings
|   +-- frontend\                # Vite/React dashboard, tests, built dist
+-- docs\                        # Project documentation
+-- examples\                    # Sample job and MCP payloads
+-- helpers\                     # Browser/file-upload helper scripts
+-- integrations\mcp\            # stdio MCP server
+-- scripts\                     # doctor, smoke, release, publish scripts
+-- tests\                       # backend and contract tests
+-- Start-JobFiller.ps1          # Windows launcher
+-- start_jobfiller.py           # cross-platform launcher
+-- requirements.txt             # runtime Python dependencies
+-- requirements-dev.txt         # test/development Python dependencies
+-- requirements-optional.txt    # optional PDF extraction/grading extras
```

Start reading in this order:

1. `README.md` for product intent and quick start.
2. `app/backend/main.py` for the API surface and orchestration.
3. `app/backend/models.py` for persistent entities.
4. `app/backend/services/processor.py` for job lifecycle rules.
5. `app/frontend/src/api.js` for frontend/backend contracts.
6. `integrations/mcp/jobfiller_mcp_server.py` for agent import behavior.

## Local Setup

Prerequisites:

- Python 3.10 or newer.
- Node.js 20.19 or newer if developing or rebuilding the frontend.
- `npm`, or `pnpm` if you prefer it.
- Optional: Ollama for local model grading.
- Optional: `tectonic` for LaTeX-to-PDF compilation.

Start the app:

```powershell
.\Start-JobFiller.ps1
```

Cross-platform start:

```powershell
python start_jobfiller.py
```

Dev frontend mode:

```powershell
$env:JOBFILLER_DEV_FRONTEND = "true"
.\Start-JobFiller.ps1
```

or:

```powershell
python start_jobfiller.py --dev-frontend
```

## Useful Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `JOBFILLER_OUTPUT_DIR` | Override local output directory | `outputs/` |
| `JOBFILLER_SETTINGS_PATH` | Override settings JSON path | `outputs/settings.json` |
| `JOBFILLER_LOCAL_TOKEN` | Fixed API mutation token | generated token |
| `JOBFILLER_ALLOWED_ORIGINS` | Extra CORS origins | local Vite ports |
| `JOBFILLER_BACKEND_PORT` | Preferred backend port | `8001` |
| `JOBFILLER_BACKEND_PORT_MAX` | Backend port scan upper bound | `8005` in PowerShell launcher |
| `JOBFILLER_FRONTEND_PORT` | Preferred Vite port | `5173` |
| `JOBFILLER_FRONTEND_PORT_MAX` | Frontend port scan upper bound | `5193` |
| `JOBFILLER_REUSE_BACKEND` | Reuse an existing backend in PowerShell launcher | unset/false |
| `JOBFILLER_DEV_FRONTEND` | Start Vite frontend instead of serving built dashboard | unset/false |
| `JOBFILLER_PYTHON` | Override Python executable discovery | auto |
| `JOBFILLER_NPM` | Override npm executable discovery | auto |
| `JOBFILLER_PNPM` | Override pnpm executable discovery | auto |
| `JOBFILLER_API_BASE` | MCP bridge API base override | runtime file or `http://127.0.0.1:8001/api` |
| `JOBFILLER_RUNTIME_CONFIG` | MCP bridge runtime JSON override | `outputs/jobfiller-runtime.json` |
| `JOBFILLER_CODEX_SCAN_COMMAND` | Optional local command/script launched with `outputs/codex_scan_prompt.txt` after a Codex scan handoff is created | unset |
| `OLLAMA_URL` | Local Ollama base URL | `http://127.0.0.1:11434` |
| `JOBFILLER_OLLAMA_MODEL` | Ollama model used for grading | empty |
| `JOBFILLER_ALLOW_REMOTE_OLLAMA` | Allow non-local Ollama URLs | unset/false |

## Development Commands

Backend tests:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Script compile check:

```powershell
python -m py_compile start_jobfiller.py scripts\doctor.py scripts\verify_release.py scripts\smoke_mcp.py
```

Doctor:

```powershell
python scripts/doctor.py
```

MCP smoke:

```powershell
python scripts/smoke_mcp.py
```

Frontend:

```powershell
cd app\frontend
npm ci
npm test
npm run build
```

Targeted frontend suites:

```powershell
npm run test:rebuild      # route smoke, screenshots, layout overflow, responsive checks
npm run test:buttons      # core dashboard controls and mocked API workflows
npm run test:downloads    # artifact/export download link behavior
npm run test:api-auth     # API discovery and local token propagation
npm run test:performance  # large-list rendering and interaction budget
```

Full release verification:

```powershell
python scripts/verify_release.py
```

Startup smoke:

```powershell
python start_jobfiller.py --smoke --mcp-export-smoke
```

## Development Patterns

- Use Pydantic request/response models in `app/backend/schemas.py`.
- Keep API mutations behind the local token middleware in `app/backend/main.py`.
- Put reusable business logic under `app/backend/services/` rather than inside route handlers.
- Prefer row-level errors for batch imports so one bad job does not discard a whole agent export.
- Add contract tests in `tests/test_api_contracts.py` when endpoint behavior changes.
- Add API edge-case tests in `tests/test_api_edge_cases.py` when token boundaries, batch resilience, cascade behavior, artifact error paths, or helper-launch guards change.
- Add email/import status tests in `tests/test_email_status_contracts.py` when Gmail status classification, action-link safety, or job-alert parsing changes.
- Add MCP tests in `tests/test_mcp_server.py` when tool schemas or transport behavior changes.
- Add frontend flow tests under `app/frontend/tests/` when dashboard controls or API contracts change.
- Preserve the privacy boundary: no candidate data, generated application files, runtime tokens, or logs should become tracked files.

## Things That Might Surprise You

- `GET /api/session` returns the local mutation token. This is acceptable only because the app is local-first and not designed as an internet-facing service.
- Public artifact download routes intentionally do not require the token so browser downloads work smoothly.
- The PowerShell launcher restarts the backend by default; stale processes have historically caused misleading local verification.
- `app/frontend/dist/` is tracked for clone-readiness even though most generated output directories are ignored.
- Database migrations are currently lightweight startup backfills in `database.py`, not a migration framework.
- The MCP bridge never bypasses API validation; it validates records locally and then calls `POST /api/imports/bulk`.

## Troubleshooting

If the dashboard cannot fetch data:

1. Restart with `.\Start-JobFiller.ps1`.
2. Do not set `JOBFILLER_REUSE_BACKEND=true` while debugging.
3. Check `artifacts/jobfiller-backend-current.log`.
4. Verify `/api/health` and `/api/session` at the printed backend URL.

If protected API calls return `403`:

1. Fetch `GET /api/session`.
2. Send `X-JobFiller-Token: <mutation_token>`.
3. If a backend restarted, refresh the dashboard or clear the cached token.

If artifact generation produces fallback PDFs:

1. Install or repair `tectonic` if true LaTeX compilation is required.
2. Inspect the artifact compile status.
3. Confirm candidate profile settings are valid JSON.

If Ollama grading fails:

1. Run `ollama serve`.
2. Confirm `OLLAMA_URL` points to localhost.
3. Pull the configured model.
4. Use `/api/model-health` or the Model Health dashboard page.

## Before Opening A PR

- Run `python scripts/verify_release.py`.
- Confirm no private outputs are tracked.
- Confirm `README.md` and `docs/` match any changed commands or endpoints.
- For API changes, update `docs/api-reference.md` and contract tests.
- For workflow changes, update `docs/workflows.md` and relevant UI tests.
