# JobFiller MCP Integration

JobFiller ships a local stdio MCP server at `integrations/mcp/jobfiller_mcp_server.py`.
It lets Codex, Claude Code, and other MCP clients export discovered job records into the local JobFiller app without bypassing validation.

The MCP server exposes three tools:

- `export_jobs_to_jobfiller`: sends one or more jobs to `POST /api/imports/bulk`.
- `validate_jobfiller_export`: validates a job batch locally without calling the API.
- `jobfiller_status`: checks `/api/health` and `/api/model-health`.

The server only imports or validates job data. It does not submit applications, click apply buttons, or upload files.

## Prerequisite

Start JobFiller first:

```powershell
.\Start-JobFiller.ps1
```

The startup script writes `outputs/jobfiller-runtime.json` with the selected backend API base and a local mutation token. The MCP server reads that ignored runtime file automatically, so it keeps working if the backend starts on a port other than `8001`. You can still override the API base with `JOBFILLER_API_BASE` when needed, or provide `JOBFILLER_LOCAL_TOKEN` for custom launches.

## Smoke Test

Before connecting an agent client, verify the stdio server and project configs:

```powershell
python scripts/smoke_mcp.py
```

The smoke test launches the server the same way Claude Code's project config does, calls `initialize`, lists tools, and validates a sample public job record without contacting the JobFiller API.

To verify a live import against a running JobFiller API, start the app and run:

```powershell
python scripts/smoke_mcp.py --live-export --api-base http://127.0.0.1:8001/api
```

The cross-platform startup smoke also runs this live export when called as:

```powershell
python start_jobfiller.py --smoke --mcp-export-smoke
```

## Codex

This repo includes `.codex/config.toml` with a project-scoped `jobfiller` MCP server:

```toml
[mcp_servers.jobfiller]
command = "python"
args = ["integrations/mcp/jobfiller_mcp_server.py"]
```

For a user-level Codex setup, add the same block to `~/.codex/config.toml`, replacing the script path with an absolute path if you want to use it outside this repo.

## Claude Code

This repo includes a project-scoped `.mcp.json`:

```json
{
  "mcpServers": {
    "jobfiller": {
      "type": "stdio",
      "command": "python",
      "args": ["integrations/mcp/jobfiller_mcp_server.py"]
    }
  }
}
```

You can also add it from Claude Code with:

```powershell
claude mcp add --transport stdio jobfiller -- python .\integrations\mcp\jobfiller_mcp_server.py
```

Run `/mcp` inside Claude Code to inspect or approve the server.

Project-scoped MCP configs assume Codex or Claude Code is opened from the repository root. Use an absolute script path for machine-level configs or when launching an agent from another working directory.

## Example Tool Payload

Use `export_jobs_to_jobfiller` with this shape:

```json
{
  "source": "codex",
  "process": true,
  "jobs": [
    {
      "url": "https://example.com/jobs/backend-software-engineer",
      "company": "Northstar Analytics",
      "title": "Backend Software Engineer",
      "location": "Remote",
      "work_model": "Remote",
      "apply_url": "https://example.com/jobs/backend-software-engineer/apply",
      "role_family": "Software Engineering",
      "key_requirements": "Python; REST APIs; SQL; automated testing",
      "keywords": "Python; FastAPI; PostgreSQL; pytest",
      "posting_age_text": "2 days ago"
    }
  ]
}
```

Row-level import errors are returned by JobFiller and are not hidden by the MCP bridge. JobFiller automatically runs missing-information checks and generates artifacts for imported jobs that are not blocked.

`materials`, `manual_questions`, and `raw_text` are text fields. The MCP bridge does not upload arbitrary files or externally generated PDFs; JobFiller creates and manages local resume and cover-letter artifacts after the job record is imported.

For copy-pasteable Codex and Claude Code scanning prompts, see [agent-workflows.md](agent-workflows.md).
