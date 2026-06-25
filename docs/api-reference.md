# JobFiller API Reference

Last updated: 2026-06-24

## Overview

Base URL is printed by the launcher and is usually:

```text
http://127.0.0.1:8001/api
```

The API is unversioned and local-first. It is intended for the bundled dashboard, local scripts, and trusted local MCP clients.

## Authentication

Most `/api` routes require:

```http
X-JobFiller-Token: <local mutation token>
```

Fetch the token:

```http
GET /api/session
```

Public routes:

- `GET /api/health`
- `GET /api/session`
- public download routes such as `/api/workbook/latest`, `/api/export/latest.json`, `/api/export/latest.csv`, `/api/export/{export_id}/download`, and artifact download URLs.

Common auth error:

```json
{
  "detail": "Missing or invalid local JobFiller token."
}
```

## Common Errors

| Status | Meaning | Typical resolution |
|---|---|---|
| `400` | Valid request shape, but requested action cannot run | Generate artifacts before downloading or launching upload helper |
| `403` | Missing or invalid token | Refresh `/api/session` and send `X-JobFiller-Token` |
| `404` | Entity, route, static asset, or file does not exist | Recheck IDs and generated artifact paths |
| `409` | Explicit confirmation required | For `assist-upload`, send `confirm=review-before-submit` |
| `422` | Validation failure | Fix request body, URL, field length, or unsupported `kind` |
| `500` | Unexpected local error | Check backend logs in `artifacts/` |

## Health And Session

### `GET /health`

Same as `/api/health` when using the normalized API base.

Returns app status, version, and advertised capabilities.

Example response:

```json
{
  "status": "ok",
  "version": "0.2.0",
  "capabilities": {
    "question_answer_autoflush_fix": true,
    "local_mutation_token": true,
    "token_required_for_local_writes": true,
    "gmail_application_status_sync": true
  }
}
```

### `GET /session`

Returns the local mutation token.

```json
{
  "mutation_token": "local-token"
}
```

## Settings

### `GET /settings`

Returns merged default and local settings, plus local paths.

### `PUT /settings`

Updates settings.

Request:

```json
{
  "settings": {
    "candidate": {
      "name": "Candidate Name",
      "email": "candidate@example.com",
      "location": "Raleigh, NC",
      "summary": "Backend/data engineer..."
    },
    "scan": {
      "remote_first": true,
      "preferred_locations": "Remote, hybrid",
      "default_keywords": "Python, FastAPI, SQL",
      "default_limit": 20
    },
    "llm": {
      "provider": "ollama",
      "ollama_url": "http://127.0.0.1:11434",
      "model": "local-model:latest"
    }
  }
}
```

Remote Ollama URLs are rejected unless `JOBFILLER_ALLOW_REMOTE_OLLAMA=1` is set.

## Scans And Imports

### `POST /scans`

Runs a manual scan from configured sources.

Request:

```json
{
  "remote_first": true,
  "limit": 20,
  "source": "chrome",
  "scanner_keywords": "software engineer, fastapi, backend",
  "codex_agent": true
}
```

Response:

```json
{
  "run_id": 1,
  "imported": 3,
  "message": "Imported 3 jobs. Codex job-site scan request written to outputs/codex_scan_prompt.txt.",
  "codex_request_path": "outputs/codex_scan_request.json",
  "codex_prompt_path": "outputs/codex_scan_prompt.txt",
  "codex_launched": false
}
```

When `codex_agent` is true, the scan still runs the local configured sources and also creates a Codex-ready MCP handoff prompt for relevant job sites. Set `JOBFILLER_CODEX_SCAN_COMMAND` to a local command or wrapper script if you want the backend to attempt launching Codex automatically with the prompt path.

### `POST /jobs/import`

Imports one job and processes it immediately.

Request fields are defined by `ImportJobRequest`.

```json
{
  "url": "https://example.com/jobs/backend-engineer",
  "company": "ExampleCo",
  "title": "Backend Engineer",
  "location": "Remote",
  "work_model": "Remote",
  "apply_url": "https://example.com/jobs/backend-engineer/apply",
  "role_family": "Software Engineering",
  "key_requirements": "Python; FastAPI; SQL",
  "keywords": "Python; FastAPI; PostgreSQL",
  "fit_score": 86,
  "posting_age_text": "2 days ago",
  "salary": "$120k-$150k"
}
```

`url` and `apply_url` must be public `http` or `https` URLs.

Response: `JobOut`.

### `POST /imports/bulk`

Imports 1-100 job records. This is the preferred endpoint for agents and MCP clients.

Request:

```json
{
  "source": "codex",
  "process": true,
  "jobs": [
    {
      "url": "https://example.com/jobs/backend-engineer",
      "company": "ExampleCo",
      "title": "Backend Engineer",
      "location": "Remote",
      "work_model": "Remote",
      "keywords": "Python; FastAPI"
    }
  ]
}
```

Response:

```json
{
  "imported": 1,
  "errors": [],
  "job_ids": [42]
}
```

Batch-level HTTP status can still be `200` when individual rows fail; inspect `errors`.

### `POST /imports/gmail-alerts`

Parses Gmail job-alert messages and imports discovered jobs.

Request:

```json
{
  "source": "gmail-alert",
  "process": true,
  "emails": [
    {
      "id": "message-id",
      "thread_id": "thread-id",
      "from": "alerts@example.com",
      "subject": "New jobs for backend engineer",
      "snippet": "ExampleCo is hiring...",
      "body": "Full email body",
      "email_ts": "2026-06-24T12:00:00Z",
      "labels": ["INBOX"],
      "display_url": "https://mail.example.test/messages/application-status"
    }
  ]
}
```

Response includes parsed count, imported count, row-level errors, IDs, and compact job summaries.

## Email Status Sync

### `POST /email-sync/applications`

Classifies application-status emails and updates job pipeline state.

Request:

```json
{
  "source": "gmail",
  "messages": [
    {
      "id": "message-id",
      "thread_id": "thread-id",
      "sender": "careers@example.com",
      "subject": "Your application was received",
      "snippet": "Thanks for applying",
      "body": "Full message body",
      "received_at": "2026-06-24T12:00:00Z",
      "display_url": "https://mail.example.test/messages/application-status"
    }
  ]
}
```

Response:

```json
{
  "synced": 1,
  "job_ids": [42],
  "event_ids": [7],
  "states": {
    "APPLIED": 1
  }
}
```

### `GET /application-events?limit=50`

Returns recent application email events. `limit` is clamped to `1-200`.

## Jobs

### `GET /jobs`

Query parameters:

| Parameter | Default | Description |
|---|---|---|
| `sort` | `newest` | Sort mode: `newest`, `oldest`, `fit`, `fit-low`, `grade`, `grade-low`, `ready`, `recently-updated`, `needs-info`, `company`, `company-desc`, `role`, `role-desc`, `location`, `location-desc`, `status`, `status-desc`, `artifacts`, `artifacts-low`, `imported`, `imported-oldest` |
| `remote_first` | `true` | Bias newest sorting toward remote/hybrid roles |

Response: array of `JobOut`.

### `GET /jobs/{job_id}`

Returns job detail, latest grade, latest artifact, questions, and parsed post data.

### `PATCH /jobs/{job_id}`

Editable fields:

```json
{
  "company": "ExampleCo",
  "title": "Senior Backend Engineer",
  "location": "Remote",
  "work_model": "Remote",
  "status": "QA",
  "application_state": "APPLIED",
  "follow_up_action": "Complete assessment",
  "notes": "Use backend systems examples.",
  "key_requirements": "Python; APIs",
  "keywords": "Python; FastAPI"
}
```

Response: `JobOut`.

### `DELETE /jobs/{job_id}`

Deletes a job and dependent rows through relationships.

Response:

```json
{
  "status": "deleted"
}
```

### `POST /jobs/{job_id}/reprocess`

Forces missing-info checks, artifact generation if unblocked, and grading.

### `POST /jobs/{job_id}/artifacts/generate`

Alias-style generation endpoint for creating a new artifact set.

### `GET /jobs/{job_id}/artifacts`

Returns artifact revision history and latest artifact metadata.

### `GET /jobs/{job_id}/questions?status=OPEN`

Returns questions for a job. `status=all` includes answered and skipped questions.

## Questions And Profile Facts

### `GET /questions`

Query parameters:

| Parameter | Default | Description |
|---|---|---|
| `status` | `OPEN` | `OPEN`, `ANSWERED`, `SKIPPED`, or `all` |
| `sort` | `impact` | `impact`, `impact-low`, `recent`, `oldest`, `status` |
| `tag` | `all` | Filter by reusable fact tag |

### `POST /questions/{question_id}/answer`

Request:

```json
{
  "answer": "I am authorized to work in the United States."
}
```

Answering a question creates or updates a reusable profile fact, applies that fact to linked open questions with the same tag, and reprocesses unblocked jobs.

### `POST /questions/{question_id}/skip`

Marks a question `SKIPPED`.

### `GET /profile-facts`

Returns reusable facts ordered by most recently updated.

### `POST /profile-facts`

Request:

```json
{
  "tag": "work_authorization",
  "question_text": "Are you authorized to work in the US?",
  "answer": "Yes.",
  "confidence": 1.0
}
```

### `PATCH /profile-facts/{fact_id}`

Partial update for `tag`, `question_text`, `answer`, or `confidence`. Updating answer text can mark existing artifacts stale and unblock linked questions.

### `DELETE /profile-facts/{fact_id}`

Deletes the fact.

## Runs And Model Health

### `GET /runs`

Returns the latest 50 run rows.

### `GET /runs/{run_id}`

Returns run detail plus `duration_seconds` when finished.

### `GET /model-health`

Returns local LLM status, scanner/worker state, queue depth, export availability, job status counts, and run metrics.

## Exports And Checklists

### `POST /workbook/export`

Generates an XLSX workbook.

Response:

```json
{
  "status": "exported",
  "path": "C:\\path\\to\\jobfiller\\outputs\\jobfiller-feedback-loop.xlsx",
  "url": "/api/workbook/latest"
}
```

### `POST /export/workbook`

Generates XLSX, JSON, and CSV exports.

### `GET /export/{export_id}/download`

Downloads generated export. Accepted IDs include `workbook`, `xlsx`, `json`, and `csv`.

### `GET /workbook/latest`

Downloads latest XLSX workbook.

### `GET /export/latest.json`

Downloads latest JSON export.

### `GET /export/latest.csv`

Downloads latest CSV export.

### `GET /checklist/tomorrow`

Returns apply queue rows for jobs with artifacts or follow-up actions.

### `GET /checklist/apply-queue`

Alias for the same apply queue.

## Artifact Content And Downloads

### `GET /artifacts/{artifact_id}/content?kind=cover-letter`

Reads editable text content. Supported kinds: `cover-letter`, `latex`.

### `PATCH /artifacts/{artifact_id}/content`

Creates a new artifact revision from manual edits.

Request:

```json
{
  "kind": "cover-letter",
  "content": "Updated cover letter text..."
}
```

### `POST /artifacts/{artifact_id}/grade`

Grades the artifact and returns current grade summary.

### `GET /artifacts/{artifact_id}/resume`

Downloads resume PDF.

### `GET /artifacts/{artifact_id}/cover-letter`

Downloads the cover letter DOCX.

### `GET /artifacts/{artifact_id}/latex`

Downloads resume LaTeX source.

### `GET /artifacts/{artifact_id}/download?kind=resume`

Generic artifact download. `kind` can be `resume`, `cover-letter`, or `latex`.

### `POST /artifacts/{artifact_id}/open-folder`

Opens the local artifact folder with Explorer on Windows or `xdg-open` on Linux.

### `GET /artifacts/{artifact_id}/open`

Alias for opening the artifact folder.

## Upload Assistance

### `POST /jobs/{job_id}/assist-upload?kind=resume&confirm=review-before-submit`

Launches the local browser upload helper for the latest artifact. `kind` can be `resume` or `cover-letter`.

This endpoint requires explicit `confirm=review-before-submit` and still does not submit the employer application.

## Response Models

### `JobOut`

Important fields:

- identity: `id`, `company`, `title`, `location`, `work_model`
- links: `source_url`, `apply_url`
- processing: `status`, `fit_score`, `readiness_score`, `open_questions`
- application pipeline: `application_state`, `follow_up_action`, `last_status_email_*`
- tailoring: `role_family`, `key_requirements`, `keywords`, `materials`, `manual_questions`, `salary`
- artifacts: `latest_grade`, `ready_to_send`, `latest_resume_pdf_path`, `latest_cover_letter_path`, `latest_artifact_id`, `artifact_count`
- timestamps: `posted_at`, `first_seen_at`, `last_seen_at`, `updated_at`

### `QuestionOut`

Includes `id`, `job_id`, `company`, `title`, `tag`, `impact`, `impact_score`, `question_text`, `blocking`, `status`, `answer`, and `created_at`.

### `ProfileFactOut`

Includes `id`, `tag`, `question_text`, `answer`, `confidence`, and `updated_at`.
