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
python -m pytest -q
python -m py_compile start_jobfiller.py
python scripts/doctor.py
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

Warm startup should normally complete in under 30 seconds once dependencies
are installed. Cold startup depends on Python and npm package download speed.

## Privacy Boundary

Do not commit `outputs/`, `artifacts/`, `.venv/`, `node_modules/`, generated
resumes, cover letters, workbooks, or local runtime files. These are ignored by
default because they can contain personal candidate data, local tokens, or job
application materials.
