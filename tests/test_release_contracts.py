from __future__ import annotations

from pathlib import Path


def test_release_artifacts_exist_for_github_distribution() -> None:
    required_paths = [
        Path(".github/workflows/ci.yml"),
        Path("start_jobfiller.py"),
        Path("scripts/Publish-JobFiller.ps1"),
        Path("docs/publishing.md"),
        Path("docs/release-checklist.md"),
        Path("LICENSE"),
    ]

    for path in required_paths:
        assert path.exists(), f"Missing release artifact: {path}"


def test_ci_runs_backend_and_frontend_validation() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "uses: actions/checkout@v4" in workflow
    assert "uses: actions/setup-python@v5" in workflow
    assert "uses: actions/setup-node@v4" in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m py_compile start_jobfiller.py" in workflow
    assert "npm ci" in workflow
    assert "npm test" in workflow
    assert "npm run build" in workflow


def test_publish_script_requires_clean_authenticated_github_cli() -> None:
    source = Path("scripts/Publish-JobFiller.ps1").read_text(encoding="utf-8")

    assert "gh auth status" in source
    assert "Refusing to publish with uncommitted changes" in source
    assert "gh repo create" in source
    assert "--remote origin --push" in source


def test_cross_platform_start_script_writes_mcp_runtime_config() -> None:
    source = Path("start_jobfiller.py").read_text(encoding="utf-8")

    assert "RUNTIME_CONFIG = OUTPUTS_DIR / \"jobfiller-runtime.json\"" in source
    assert "\"mutation_token\": token" in source
    assert "JOBFILLER_BACKEND_PORT_MAX" in source
    assert "JOBFILLER_FRONTEND_PORT_MAX" in source
    assert "Startup completed in" in source
