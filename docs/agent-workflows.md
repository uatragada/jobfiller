# Agent Workflows For Job Discovery

JobFiller does not need direct scraping credentials. Codex, Claude Code, or any
other MCP-capable local agent can browse job boards in the user's authenticated
browser/session, then export structured job records into JobFiller.

The local app never submits applications. It prepares job records, missing-fact
questions, tailored resumes, cover letters, workbook exports, and file paths for
manual review.

## Recommended Flow

1. Start JobFiller.
2. Open Codex or Claude Code in the cloned repository.
3. Confirm the `jobfiller` MCP server is available.
4. Ask the agent to scan job sources and export jobs through `export_jobs_to_jobfiller`.
5. Review imported jobs in JobFiller.
6. Answer queued missing-fact questions.
7. Generate or regenerate application packets.
8. Manually review every artifact before applying.

## Codex Prompt

```text
Use the local JobFiller MCP server.

Find recent jobs that match my profile and preferences. Prefer newest postings
first. Do not apply, save jobs, message recruiters, upload files, or click final
submit buttons.

For each promising posting, export a structured job record to JobFiller using
export_jobs_to_jobfiller with process=false. Include URL, apply_url when known,
company, title, location, work_model, role_family, key_requirements, keywords,
posting_age_text, salary when listed, materials, manual_questions, and concise
notes. Reject or skip unsafe/non-public URLs.

After exporting, summarize what was sent and any postings that were skipped.
```

## Claude Code Prompt

```text
Use the jobfiller MCP server from this repository.

Scan newest relevant job postings first from the sources I provide or from my
browser context. Import only structured job records into JobFiller. Do not apply
or submit anything.

Call export_jobs_to_jobfiller with process=false unless I explicitly ask you to
generate packets immediately. Include raw_text only when it is useful and keep it
under the import limit.

When done, tell me how many jobs were exported and what questions I should answer
inside JobFiller.
```

## Export Payload Shape

Use the same shape as [examples/mcp-export.sample.json](../examples/mcp-export.sample.json).
Every job must include a public `url`. Localhost, private IPs, credentialed URLs,
and malformed URLs are rejected by both the MCP bridge and API.

## Safety Rules For Agents

- Import data only; do not apply.
- Do not upload resumes or cover letters to employer sites.
- Do not click final submit, send messages, or save jobs to third-party accounts.
- Do not invent candidate facts to improve fit.
- Put missing or uncertain candidate claims into JobFiller questions.
- Prefer newer postings first, then fit score.
- Keep source URLs and apply URLs public `http` or `https`.
