from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from . import __version__


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = Path(os.environ.get("JOBFILLER_OUTPUT_DIR", ROOT / "outputs")).resolve()
SETTINGS_PATH = Path(os.environ.get("JOBFILLER_SETTINGS_PATH", OUTPUT_ROOT / "settings.json")).resolve()


DEFAULT_SETTINGS: dict[str, Any] = {
    "app": {
        "name": "JobFiller",
        "version": __version__,
    },
    "candidate": {
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "website": "",
        "linkedin": "",
        "summary": "",
        "education": [],
        "experience": [],
        "projects": [],
        "skills": [],
    },
    "scan": {
        "remote_first": True,
        "default_location": "Remote",
        "default_work_model": "Remote",
        "preferred_locations": "Remote, hybrid, candidate-selected regions",
        "default_keywords": "software engineer, data analyst, product, operations, remote, hybrid",
        "default_limit": 20,
        "seed_data_path": str(ROOT / "examples" / "jobs.sample.json"),
    },
    "llm": {
        "provider": "ollama",
        "ollama_url": os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"),
        "model": os.environ.get("JOBFILLER_OLLAMA_MODEL", ""),
        "temperature": 0.1,
        "num_ctx": 8192,
    },
    "artifacts": {
        "resume_filename_template": "{candidate_slug}-resume-{company_slug}.pdf",
        "cover_letter_filename_template": "{candidate_slug}-cover-letter-{company_slug}.md",
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings() -> dict[str, Any]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.exists():
        return deepcopy(DEFAULT_SETTINGS)
    try:
        loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_SETTINGS)
    if not isinstance(loaded, dict):
        return deepcopy(DEFAULT_SETTINGS)
    return _deep_merge(DEFAULT_SETTINGS, loaded)


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_merge(DEFAULT_SETTINGS, settings)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
    try:
        SETTINGS_PATH.chmod(0o600)
    except OSError:
        pass
    return merged


def public_settings() -> dict[str, Any]:
    settings = load_settings()
    return {
        **settings,
        "paths": {
            "settings_path": str(SETTINGS_PATH),
            "output_root": str(OUTPUT_ROOT),
        },
    }


def candidate_profile() -> dict[str, Any]:
    return load_settings().get("candidate", {})


def scan_settings() -> dict[str, Any]:
    return load_settings().get("scan", {})


def llm_settings() -> dict[str, Any]:
    return load_settings().get("llm", {})


def candidate_slug() -> str:
    from .services.text_utils import slugify

    name = str(candidate_profile().get("name") or "").strip()
    return slugify(name) if name else "candidate"
