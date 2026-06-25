# Frontend And UX Documentation

Last updated: 2026-06-24

## Overview

The dashboard is a Vite/React app in `app/frontend`. It can run as a development frontend or be served as static built assets from FastAPI. Built assets under `app/frontend/dist/` are tracked so a fresh clone can run without installing frontend dependencies.

## Main Files

| Path | Purpose |
|---|---|
| `app/frontend/src/main.jsx` | App state, pages, workflows, table sorting/filtering, settings, artifact controls |
| `app/frontend/src/api.js` | API base discovery, session token handling, fetch wrappers |
| `app/frontend/src/styles.css` | Dashboard styling |
| `app/frontend/src/components/jobfiller-ui.jsx` | Local UI wrappers used by the app |
| `app/frontend/src/components/untitled-ui/` | Imported UI primitives/icons/components |
| `app/frontend/tests/button-flows.mjs` | Browser-flow control tests |
| `app/frontend/tests/downloads.mjs` | Download behavior tests |
| `app/frontend/tests/performance.mjs` | Basic performance checks |
| `app/frontend/vite.config.js` | Vite/test config |

## API Base Discovery

The frontend does not assume one fixed port. `api.js` builds candidate bases from:

1. `VITE_API_BASE`.
2. `window.__JOBFILLER_API_BASE`.
3. `?api_base=...` query parameter.
4. Same-origin `/api`.
5. Local fallback ports `8000-8120`.

A candidate is accepted only when:

- `/api/health` returns JSON.
- `/api/session` returns a mutation token.
- token-protected `/api/settings` returns JSON.
- token-protected `/api/model-health` returns JSON.

This avoids accidentally treating dashboard HTML as API JSON.

## Token Handling

The frontend caches the mutation token from `/api/session`. For protected requests it sends:

```http
X-JobFiller-Token: <token>
```

On a `403`, it refreshes the token once and retries. This handles backend restarts with regenerated tokens.

## Dashboard Pages

| Page | Purpose |
|---|---|
| Jobs | Search, filter, sort, select, inspect, import, patch notes/status, access artifacts |
| Questions | Resolve missing facts by impact, tag, status, and search |
| Profile Facts | Create, update, and delete reusable candidate facts |
| Runs & Logs | Inspect recent processing runs and messages |
| Auto Generate | Monitor automatic packet generation for imported jobs |
| Agent Import / MCP | Copy MCP payload shape and inspect worker/model status |
| Assist Upload | Parse local files into facts and launch upload helper for selected job |
| Export Workbook | Generate and download XLSX, JSON, and CSV exports |
| Settings | Candidate profile, scan preferences, local LLM settings |
| Model Health | Local LLM status, scanner/worker state, queue and export metrics |
| Apply Queue | Ordered checklist for manual application work |

## Sorting And Filtering

The frontend supports both API-level and client-side sorting. Job rows can be sorted by posting date, import date, company, role, location/model, status, fit, grade, readiness, artifact count, and recently updated. The remote-first preference influences tie-breaking and scan behavior.

Filters include:

- search text
- status
- source
- work model
- location chips
- custom location
- remote-only toggle

## Settings Shape

Frontend settings are mapped to backend settings:

```json
{
  "candidate": {
    "name": "",
    "email": "",
    "location": "",
    "summary": "",
    "education": [],
    "experience": [],
    "projects": [],
    "skills": []
  },
  "scan": {
    "remote_first": true,
    "preferred_locations": "Remote, hybrid",
    "default_keywords": "software engineer, data analyst",
    "default_limit": 20
  },
  "llm": {
    "provider": "ollama",
    "model": "",
    "ollama_url": "http://127.0.0.1:11434"
  }
}
```

The settings page validates full candidate profile JSON before saving.

## Testing

Run frontend tests:

```powershell
cd app\frontend
npm test
```

Build:

```powershell
npm run build
```

The release verifier also runs these commands.

## Extension Notes

- Add API wrappers in `api.js` before wiring controls in `main.jsx`.
- Keep dashboard controls aligned with backend token requirements.
- When adding a new protected endpoint, include it in frontend validation only if it is required to prove the chosen API base is real.
- For artifact download links, prefer direct `href` download routes rather than JSON fetches.
- Add `data-testid` values for new critical controls so browser-flow tests can verify them.
- Keep user-facing copy concise and operational; this is a work dashboard, not a marketing page.
