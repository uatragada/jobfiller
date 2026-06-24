# JobFiller Release Checklist

Use this checklist before making a GitHub release or asking another user to run
JobFiller from a fresh clone.

- Git worktree is clean except ignored local runtime artifacts.
- `python scripts/verify_release.py` passes.
- Runtime dependencies stay in `requirements.txt`; test/development dependencies stay in `requirements-dev.txt`; optional PDF-grading extras stay in `requirements-optional.txt`.
- `python -m pytest -q` passes.
- `python -m py_compile start_jobfiller.py scripts\doctor.py scripts\verify_release.py scripts\smoke_mcp.py` passes.
- `python scripts/doctor.py` passes.
- `python scripts/smoke_mcp.py` launches the stdio MCP server and verifies Codex/Claude export tools.
- `npm ci`, `npm test`, and `npm run build` pass in `app/frontend`.
- `python start_jobfiller.py --smoke --mcp-export-smoke` starts the backend, serves the built dashboard, verifies readiness, verifies a live MCP export into a temporary smoke database, finishes within the warm-start budget, and cleans up child processes.
- `.\Start-JobFiller.ps1` starts the backend and dashboard and logs elapsed startup time on Windows.
- `python start_jobfiller.py` starts the backend and dashboard on a free local port.
- Dashboard loads at the URL printed by the startup script, usually `http://127.0.0.1:8001` for the built dashboard or `http://127.0.0.1:5173` in dev-frontend mode.
- Protected API routes reject missing `X-JobFiller-Token`.
- MCP status works after startup because `outputs/jobfiller-runtime.json` exists locally.
- Codex and Claude Code project MCP configs point to `integrations/mcp/jobfiller_mcp_server.py`.
- Codex and Claude Code scanning workflow docs are present in `docs/agent-workflows.md`.
- `outputs/`, `artifacts/`, generated resumes, generated cover letters, and runtime tokens are not tracked.
- `.env.example` is tracked, but real `.env` files are ignored.
- README quick-start, validation, MCP, and publishing instructions match the current scripts.
- `CONTRIBUTING.md` and `SECURITY.md` describe local development, privacy boundaries, and responsible reporting.
