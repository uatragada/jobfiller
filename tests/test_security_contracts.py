from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.database import DB_PATH, OUTPUT_ROOT, init_db
from app.backend.main import app


client = TestClient(app)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def test_local_database_is_private_to_output_root() -> None:
    init_db()

    assert DB_PATH.exists()
    assert _is_relative_to(DB_PATH, OUTPUT_ROOT)
    assert not _is_relative_to(DB_PATH, Path("app/frontend").resolve())
    assert not (Path("app/frontend/src") / DB_PATH.name).exists()
    assert not (Path("app/frontend/dist") / DB_PATH.name).exists()


def test_model_health_response_does_not_expose_secret_material() -> None:
    token = client.get("/api/session").json()["mutation_token"]
    response = client.get("/api/model-health", headers={"X-JobFiller-Token": token})

    assert response.status_code == 200
    serialized = json.dumps(response.json(), default=str)
    forbidden_patterns = [
        r"sk-[A-Za-z0-9_-]{12,}",
        r"OPENAI_API_KEY",
        r"ANTHROPIC_API_KEY",
        r"GITHUB_TOKEN",
        r"LINKEDIN_PASSWORD",
        r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY",
    ]
    for pattern in forbidden_patterns:
        assert not re.search(pattern, serialized, flags=re.IGNORECASE), pattern


def test_source_tree_does_not_embed_static_credentials() -> None:
    source_roots = [
        Path("app/frontend/src"),
        Path("app/frontend/tests"),
        Path("app/backend"),
        Path("docs"),
        Path("helpers"),
        Path("integrations"),
        Path("scripts"),
        Path("tests"),
        Path("examples"),
        Path(".codex"),
    ]
    source_files = [
        Path("README.md"),
        Path("Start-JobFiller.ps1"),
        Path("start_jobfiller.py"),
        Path("CHANGELOG.md"),
        Path("CONTRIBUTING.md"),
        Path("SECURITY.md"),
        Path(".mcp.json"),
        Path(".gitignore"),
        Path("requirements.txt"),
        Path("pytest.ini"),
    ]
    private_terms = ["U" + "day", "Atra" + "gada", "Gem" + "ma", "N" + "YC", "New " + "York"]
    forbidden_patterns = [
        r"sk-proj-[A-Za-z0-9_-]+",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"OPENAI_API_KEY\s*=\s*['\"]",
        r"ANTHROPIC_API_KEY\s*=\s*['\"]",
        r"GITHUB_TOKEN\s*=\s*['\"]",
        r"LINKEDIN_PASSWORD\s*=\s*['\"]",
        r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY",
        "G:" + r"\\",
    ] + [rf"\b{re.escape(term)}\b" for term in private_terms]

    scanned_files = 0
    for root in source_roots:
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if file_path.resolve() == Path(__file__).resolve():
                continue
            if file_path.suffix.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".json", ".toml", ".ps1"}:
                continue
            scanned_files += 1
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for pattern in forbidden_patterns:
                assert not re.search(pattern, text, flags=re.IGNORECASE), f"{pattern} found in {file_path}"

    for file_path in source_files:
        if not file_path.exists():
            continue
        scanned_files += 1
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for pattern in forbidden_patterns:
            assert not re.search(pattern, text, flags=re.IGNORECASE), f"{pattern} found in {file_path}"

    assert scanned_files > 0
