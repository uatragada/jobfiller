# Security Policy

JobFiller is designed to run locally and store candidate/application data on the
user's machine. The app should never require committing personal job-search
materials or local runtime secrets to source control.

## Supported Use

- Run the backend on loopback addresses such as `127.0.0.1`.
- Keep `outputs/`, `artifacts/`, `.env`, local databases, generated resumes,
  generated cover letters, and runtime tokens untracked.
- Review all generated materials before sending them to an employer.
- Use upload assistance only as a local helper. Final application submission
  remains manual.

## Local API Protection

Protected API routes require the local `X-JobFiller-Token` written by the
startup scripts into `outputs/jobfiller-runtime.json`. The token is intended for
local MCP clients and the dashboard, not for remote deployment.

Remote Ollama endpoints are blocked unless `JOBFILLER_ALLOW_REMOTE_OLLAMA=1` is
set. Use that override only for infrastructure you control.

## Reporting Issues

If you find a security issue, open a private report or contact the maintainer
before publishing details. Include:

- affected version or commit
- reproduction steps
- expected and actual behavior
- whether personal data, tokens, generated materials, or local files may be
  exposed

Do not include real resumes, cover letters, runtime tokens, local databases, or
employer application materials in public issues.
