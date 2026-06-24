from __future__ import annotations

from pathlib import Path
import json

from app.backend import __version__


def test_release_artifacts_exist_for_github_distribution() -> None:
    required_paths = [
        Path(".github/workflows/ci.yml"),
        Path("start_jobfiller.py"),
        Path("scripts/doctor.py"),
        Path("scripts/verify_release.py"),
        Path("scripts/Publish-JobFiller.ps1"),
        Path("docs/publishing.md"),
        Path("docs/release-checklist.md"),
        Path("docs/agent-workflows.md"),
        Path("examples/mcp-export.sample.json"),
        Path("CHANGELOG.md"),
        Path("CONTRIBUTING.md"),
        Path("SECURITY.md"),
        Path(".env.example"),
        Path(".editorconfig"),
        Path(".gitattributes"),
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
    assert "python -m py_compile start_jobfiller.py scripts/doctor.py scripts/verify_release.py" in workflow
    assert "python scripts/doctor.py" in workflow
    assert "python start_jobfiller.py --smoke --startup-budget 30" in workflow
    assert "npm ci" in workflow
    assert "npm test" in workflow
    assert "npm run build" in workflow


def test_release_verification_script_runs_core_checks() -> None:
    source = Path("scripts/verify_release.py").read_text(encoding="utf-8")

    assert '"pytest", "-q"' in source
    assert '"scripts/verify_release.py"' in source
    assert '"scripts/doctor.py"' in source
    assert '"npm", "test"' in source or 'npm, "test"' in source
    assert '"npm", "run", "build"' in source or 'npm, "run", "build"' in source
    assert '"start_jobfiller.py", "--smoke", "--startup-budget", "30"' in source
    assert "node_modules" in source


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
    assert '"--smoke"' in source
    assert "Startup smoke passed" in source
    assert "stop_process_tree(frontend" in source
    assert "JOBFILLER_BACKEND_PORT_MAX" in source
    assert "JOBFILLER_FRONTEND_PORT_MAX" in source
    assert "frontend_start + 20" in source
    assert "--strictPort" in source
    assert "Startup completed in" in source


def test_clone_readiness_docs_and_examples_cover_agent_imports() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    workflow_doc = Path("docs/agent-workflows.md").read_text(encoding="utf-8")
    sample = Path("examples/mcp-export.sample.json").read_text(encoding="utf-8")

    assert "docs/agent-workflows.md" in readme
    assert "examples/mcp-export.sample.json" in readme
    assert "scripts/verify_release.py" in readme
    assert "CONTRIBUTING.md" in readme
    assert "SECURITY.md" in readme
    assert "export_jobs_to_jobfiller" in workflow_doc
    assert "Do not apply" in workflow_doc
    assert '"process": false' in sample


def test_env_example_is_tracked_but_real_env_files_are_ignored() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert ".env" in gitignore
    assert ".env.*" in gitignore
    assert "!.env.example" in gitignore
    assert "JOBFILLER_OLLAMA_MODEL" in env_example
    assert "JOBFILLER_ALLOW_REMOTE_OLLAMA=false" in env_example


def test_release_version_metadata_is_consistent() -> None:
    backend_init = Path("app/backend/__init__.py").read_text(encoding="utf-8")
    backend_settings = Path("app/backend/settings.py").read_text(encoding="utf-8")
    frontend_source = Path("app/frontend/src/main.jsx").read_text(encoding="utf-8")
    frontend_package = json.loads(Path("app/frontend/package.json").read_text(encoding="utf-8"))
    frontend_lock = json.loads(Path("app/frontend/package-lock.json").read_text(encoding="utf-8"))
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")

    assert __version__ == "0.2.0"
    assert f'__version__ = "{__version__}"' in backend_init
    assert '"version": __version__' in backend_settings
    assert f'const APP_VERSION = "{__version__}";' in frontend_source
    assert frontend_package["version"] == __version__
    assert frontend_lock["version"] == __version__
    assert frontend_lock["packages"][""]["version"] == __version__
    assert f"## {__version__}" in changelog
