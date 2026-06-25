# User And Agent Workflows

Last updated: 2026-06-24

## Core Manual Workflow

1. Start JobFiller with `.\Start-JobFiller.ps1`.
2. Open the dashboard URL printed by the launcher.
3. Open Settings and save candidate profile details.
4. Import jobs manually, through browser-tab scan, Gmail alert import, or MCP.
5. Review imported jobs in the Jobs table.
6. Answer open Questions with truthful reusable facts.
7. Generate or reprocess selected jobs.
8. Review resume, LaTeX, cover letter, local LLM grade, and risks.
9. Export the apply queue or open artifact folders.
10. Manually apply on employer sites.

## Manual URL Import

Use the dashboard import field or call `POST /api/jobs/import`.

Good records include:

- source job URL
- direct apply URL when known
- company and title
- location and work model
- key requirements
- keywords
- salary when listed
- materials required by the employer
- manual application questions visible on the form

The API processes manual imports immediately. If missing facts are detected, the job becomes `NEEDS_INFO`. Otherwise JobFiller generates artifacts and grades them.

## Browser Tab Scan

The scan flow can inspect supported open browser job tabs through the ingestion service. Use scan settings to bias remote-first sorting, location defaults, keywords, and scan limits.

Recommended use:

1. Open promising job posts in the browser.
2. Start JobFiller.
3. Use scan source `Browser job tabs`.
4. Review imported rows and discard weak matches.

When the dashboard Scan Now action requests a Codex handoff, JobFiller also writes:

- `outputs/codex_scan_request.json`
- `outputs/codex_scan_prompt.txt`

The prompt targets relevant job sites from scan settings and asks Codex to import discovered roles through `export_jobs_to_jobfiller`. JobFiller automatically processes imported jobs that are not blocked by missing information. If `JOBFILLER_CODEX_SCAN_COMMAND` is set, JobFiller attempts to launch that local command with the prompt path as its only argument. Otherwise the handoff file is created for manual or agent pickup.

## Agent Import Through MCP

Best when using Codex, Claude Code, or another MCP-capable local agent.

1. Start JobFiller.
2. Ensure `outputs/jobfiller-runtime.json` exists.
3. Open the agent from the repo root so project MCP config is found.
4. Ask the agent to discover jobs and call `export_jobs_to_jobfiller`, or give it the latest `outputs/codex_scan_prompt.txt`.
5. Review the Questions page for any blockers created during import.
6. Review generated materials after JobFiller finishes automatic processing.

Safety rules for agents:

- Import data only.
- Do not apply, submit, save jobs externally, message recruiters, or upload files.
- Do not invent candidate facts.
- Put uncertainty into `manual_questions`, `materials`, or JobFiller questions.
- Skip unsafe URLs.

## Gmail Job Alert Import

`POST /api/imports/gmail-alerts` accepts Gmail-like message records and extracts job postings from common alert formats. It deduplicates by URL within the batch and imports row-level successes even if one email fails to parse.

Useful fields:

- `from`
- `subject`
- `snippet`
- `body`
- `email_ts`
- `display_url`

Default `process=true` means parsed jobs immediately enter the normal missing-info and artifact pipeline.

## Application Status Email Sync

`POST /api/email-sync/applications` accepts application-status emails and classifies them into pipeline states. It can create or update matching jobs, create `ApplicationEvent` rows, set `application_state`, update latest status email evidence, and produce follow-up actions.

Signals include:

- application received / submitted
- rejection
- interview request
- assessment, identity verification, or action-needed request

The dashboard exposes recent events through the application-events API and shows status/follow-up context in job and apply queue views.

## Questions And Profile Facts

Missing-info rules create tagged questions. Answering one question:

1. Saves a reusable `ProfileFact` by tag.
2. Applies the answer to linked open questions with the same tag.
3. Reprocesses jobs that are no longer blocked.
4. Marks unrelated existing artifacts stale when the fact could affect previous materials.

This is why answers should be truthful, reusable, and stable. Avoid role-specific embellishment in profile facts unless the tag/question is explicitly role-specific.

## Artifact Generation

When a job is unblocked, JobFiller:

1. Builds resume LaTeX.
2. Tries to compile with `tectonic`.
3. Falls back to an internal PDF writer if needed.
4. Generates a cover letter.
5. Writes revisioned copies and latest delivery copies.
6. Grades the resume with local deterministic checks and optional Ollama.
7. Sets job status to `READY` or `QA`.

Manual edits to cover letters or LaTeX create new artifact revisions rather than modifying history in place.

## Apply Queue

The apply queue includes jobs with generated artifacts or follow-up actions. It is available in the dashboard and through:

- `GET /api/checklist/apply-queue`
- `GET /api/checklist/tomorrow`
- workbook sheet `Apply Queue`

Use it as a checklist, not as an automation script. Open the apply URL, attach files manually, and verify employer questions before submission.

## Assist Upload

The upload helper endpoint is:

```http
POST /api/jobs/{job_id}/assist-upload?kind=resume&confirm=review-before-submit
```

It requires `confirm=review-before-submit`. Without it, the API returns `409`. The helper starts a local PowerShell script that assists with file selection/upload mechanics, but the user remains responsible for reviewing files and submitting manually.

## Export Workflow

Use the Export page or call:

```http
POST /api/export/workbook
```

This creates:

- XLSX workbook
- JSON export
- CSV export

Download through:

- `/api/workbook/latest`
- `/api/export/latest.json`
- `/api/export/latest.csv`
- `/api/export/{workbook|json|csv}/download`

## Local LLM Workflow

JobFiller works without Ollama. Without a configured model, grading falls back to deterministic checks.

To enable local grading:

```powershell
ollama serve
ollama pull <model-name>
$env:JOBFILLER_OLLAMA_MODEL = "<model-name>"
.\Start-JobFiller.ps1
```

Keep Ollama local unless deliberately opting into remote endpoints.
