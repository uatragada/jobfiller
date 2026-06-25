# Agent Bulk Import Contract

Agents and automation scripts can add job records through the bulk import endpoint.

MCP clients should prefer the bundled stdio server in [docs/mcp-integration.md](mcp-integration.md). It exposes `export_jobs_to_jobfiller`, validates inputs, and forwards successful batches to this same endpoint.

## Endpoint

```http
POST /api/imports/bulk
Content-Type: application/json
X-JobFiller-Token: <local session token>
```

Get the local session token from `GET /api/session` after starting JobFiller. The bundled MCP server reads the ignored runtime file and sends this header automatically.

## Request Body

```json
{
  "source": "agent",
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
      "fit_score": 86,
      "notes": "Imported from an agent run.",
      "posting_age_text": "2 days ago",
      "raw_text": "Optional source text from the job post.",
      "materials": "Optional application material notes.",
      "manual_questions": "Optional questions visible on the application form.",
      "salary": "Not listed"
    }
  ]
}
```

Top-level fields:

- `source`: optional string saved on imported jobs. Defaults to `agent`.
- `process`: optional compatibility boolean. Imports now always run the automatic missing-information and artifact pipeline; open blocking questions still prevent packet generation.
- `jobs`: array of job records. Batches must contain 1-100 jobs.

Job fields:

- `url`: required public `http` or `https` job URL. Unsafe local, private, reserved, credentialed, or malformed URLs are rejected.
- `company`, `title`, `location`, `work_model`, `role_family`: optional structured job metadata.
- `apply_url`: optional public `http` or `https` application URL. Unsafe local, private, reserved, credentialed, or malformed URLs are rejected.
- `key_requirements`, `keywords`: optional semicolon-separated text used for matching and artifact generation.
- `fit_score`: optional integer score supplied by the caller.
- `notes`, `posting_age_text`, `raw_text`, `materials`, `manual_questions`, `salary`: optional supporting context. `manual_questions` is split into blocking question queue rows for the imported job.

## Response Body

The endpoint returns HTTP 200 for the batch itself. Row-level failures are reported in `errors` so callers can retry only failed records.

```json
{
  "imported": 1,
  "errors": [
    {
      "index": 1,
      "url": "https://example.com/jobs/bad-record",
      "error": "422: Job import requires a valid URL."
    }
  ],
  "job_ids": [42]
}
```

Response fields:

- `imported`: number of records successfully created or updated.
- `errors`: per-record failures with the original zero-based `index`, `url`, and `error` message.
- `job_ids`: database IDs for successfully imported records.

## Gmail Job Alert Import

Agents with Gmail connector access can parse job-alert emails directly through:

```http
POST /api/imports/gmail-alerts
Content-Type: application/json
X-JobFiller-Token: <local session token>
```

```json
{
  "source": "gmail-alert",
  "process": true,
  "emails": [
    {
      "id": "gmail-message-id",
      "thread_id": "gmail-thread-id",
      "from_": "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>",
      "subject": "Backend Engineer at ExampleCo",
      "email_ts": "2026-06-24T14:30:00Z",
      "body": "[ExampleCo](https://www.linkedin.com/jobs/view/123) [Backend Engineer\nExampleCo · Raleigh, NC (Hybrid)](https://www.linkedin.com/jobs/view/123)"
    }
  ]
}
```

The importer treats email content as untrusted source text. It extracts known alert formats from LinkedIn, Indeed, Ladders, Glassdoor, and simple subject/link matches, scores parsed jobs against the configured candidate profile, adds manual questions for missing facts such as clearance or seniority fit, and then forwards each parsed job through the same validated import path as `POST /api/imports/bulk`.

## PowerShell Example

```powershell
$session = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/session"
$payload = Get-Content .\examples\jobs.sample.json -Raw | ConvertFrom-Json
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8001/api/imports/bulk" `
  -Headers @{ "X-JobFiller-Token" = $session.mutation_token } `
  -ContentType "application/json" `
  -Body (@{ source = "agent-example"; process = $true; jobs = $payload } | ConvertTo-Json -Depth 10)
```
