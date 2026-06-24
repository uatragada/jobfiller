# Publishing JobFiller To GitHub

JobFiller is ready to publish when the local validation commands pass and the
Git worktree is clean except ignored runtime artifacts.

## One-Time GitHub Setup

Install and authenticate the GitHub CLI:

```powershell
gh auth login
```

Then publish from the repository root:

```powershell
.\scripts\Publish-JobFiller.ps1 -RepositoryName jobfiller -Visibility public
```

If you want to publish under a specific owner or organization installation:

```powershell
.\scripts\Publish-JobFiller.ps1 -Owner your-github-owner -RepositoryName jobfiller -Visibility public
```

The script refuses to publish uncommitted changes. It creates `origin` only
when one is missing; if `origin` already exists, it pushes the current branch.

## Manual Equivalent

```powershell
gh repo create jobfiller --public --source . --remote origin --push
```

or, for an existing repository:

```powershell
git remote add origin https://github.com/<owner>/<repo>.git
git push -u origin master
```

## Release Checks

Run these before publishing:

```powershell
python scripts/verify_release.py
```

Or run the same checks manually:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m py_compile start_jobfiller.py scripts\doctor.py scripts\verify_release.py scripts\smoke_mcp.py
python scripts/doctor.py
python scripts/smoke_mcp.py
cd app\frontend
npm ci
npm test
npm run build
```

Then confirm the app starts locally:

```powershell
.\Start-JobFiller.ps1
```

or:

```powershell
python start_jobfiller.py
```

Startup should normally complete in under 30 seconds from a fresh clone because
the dashboard build is committed and served by FastAPI. Frontend dependencies
are only required when rebuilding `app/frontend/dist` or developing the UI.
The release verifier enforces the startup expectation with
`python start_jobfiller.py --smoke --mcp-export-smoke --startup-budget 30`.

## Privacy Boundary

Do not commit `outputs/`, `artifacts/`, `.venv/`, `node_modules/`, generated
resumes, cover letters, workbooks, or local runtime files. These are ignored by
default because they can contain personal candidate data, local tokens, or job
application materials.
