# Operations Runbook

Last updated: 2026-06-24

## Local Startup

Windows default:

```powershell
.\Start-JobFiller.ps1
```

Cross-platform:

```powershell
python start_jobfiller.py
```

Expected outputs:

- dashboard URL
- backend API URL
- log paths under `artifacts/`
- runtime config path `outputs/jobfiller-runtime.json`

## Startup Modes

| Mode | Command |
|---|---|
| Built dashboard served by FastAPI | `.\Start-JobFiller.ps1` |
| Cross-platform built dashboard | `python start_jobfiller.py` |
| Vite dev frontend | `python start_jobfiller.py --dev-frontend` |
| Smoke only | `python start_jobfiller.py --smoke` |
| Smoke plus MCP live export | `python start_jobfiller.py --smoke --mcp-export-smoke` |

The PowerShell launcher restarts the backend by default. Use `JOBFILLER_REUSE_BACKEND=true` only when you intentionally want to keep an existing backend process.

## Health Checks

Public checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/health
Invoke-RestMethod http://127.0.0.1:8001/api/session
```

Protected check:

```powershell
$session = Invoke-RestMethod http://127.0.0.1:8001/api/session
Invoke-RestMethod `
  -Uri http://127.0.0.1:8001/api/model-health `
  -Headers @{ "X-JobFiller-Token" = $session.mutation_token }
```

## Logs

| File | Meaning |
|---|---|
| `artifacts/jobfiller-backend-current.log` | backend stdout |
| `artifacts/jobfiller-backend-current.err.log` | backend stderr |
| `artifacts/jobfiller-frontend-current.log` | Vite stdout in dev frontend mode |
| `artifacts/jobfiller-frontend-current.err.log` | Vite stderr in dev frontend mode |

## Validation Ladder

Fast backend confidence:

```powershell
python -m pytest -q
```

MCP confidence:

```powershell
python scripts/smoke_mcp.py
```

Frontend confidence:

```powershell
cd app\frontend
npm test
npm run build
```

Full confidence:

```powershell
python scripts/verify_release.py
```

## Release Procedure

1. Confirm no private outputs are tracked.
2. Run `python scripts/verify_release.py`.
3. Confirm README and docs are current.
4. Confirm `app/frontend/dist/` assets are current after frontend changes.
5. Confirm `.env.example` is tracked and real `.env` files are ignored.
6. Use `scripts/Publish-JobFiller.ps1` only after GitHub CLI auth and a clean worktree.

## Recovery Procedures

### Dashboard Cannot Reach API

1. Restart with `.\Start-JobFiller.ps1`.
2. Confirm the printed backend URL.
3. Check backend logs.
4. Verify `/api/health` and `/api/session`.
5. If in dev frontend mode, ensure the Vite URL is using the right API base.

### Stale Backend Behavior

1. Unset `JOBFILLER_REUSE_BACKEND`.
2. Restart with the PowerShell launcher.
3. Verify the backend log timestamp changed.

### Port Conflict

Set a different range:

```powershell
$env:JOBFILLER_BACKEND_PORT = "8010"
$env:JOBFILLER_BACKEND_PORT_MAX = "8020"
python start_jobfiller.py
```

For Vite:

```powershell
$env:JOBFILLER_FRONTEND_PORT = "5180"
$env:JOBFILLER_FRONTEND_PORT_MAX = "5199"
python start_jobfiller.py --dev-frontend
```

### Token Errors

1. Fetch `GET /api/session`.
2. Send the returned token as `X-JobFiller-Token`.
3. If the backend restarted, refresh the dashboard or clear cached frontend state.
4. Check `outputs/jobfiller-runtime.json` for MCP clients.

### MCP Client Cannot Import

1. Start JobFiller first.
2. Run `python scripts/smoke_mcp.py`.
3. Confirm the client was launched from the repo root or uses an absolute MCP server path.
4. Confirm `outputs/jobfiller-runtime.json` points to the active backend.
5. Use `JOBFILLER_API_BASE` and `JOBFILLER_LOCAL_TOKEN` only when intentionally overriding runtime discovery.

### Artifact File Missing

1. Regenerate artifacts for the job.
2. Check whether local files under `outputs/` were deleted.
3. Inspect artifact revision history through `/api/jobs/{job_id}/artifacts`.

### Ollama Not Reachable

1. Run `ollama serve`.
2. Pull the configured model.
3. Keep the URL local: `http://127.0.0.1:11434`.
4. Check `/api/model-health`.

## Privacy Boundary

Never commit:

- `outputs/`
- `artifacts/`
- `.venv/`
- `node_modules/`
- local logs
- generated resumes
- generated cover letters
- workbooks
- runtime tokens
- real `.env` files

Before publishing or sharing:

```powershell
git status --short
```

Review every tracked file that contains candidate, employer, or application data.
