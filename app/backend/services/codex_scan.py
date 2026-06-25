from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from ..settings import OUTPUT_ROOT, scan_settings


REQUEST_JSON_PATH = OUTPUT_ROOT / "codex_scan_request.json"
REQUEST_PROMPT_PATH = OUTPUT_ROOT / "codex_scan_prompt.txt"


@dataclass(frozen=True)
class CodexScanRequest:
    request_path: Path
    prompt_path: Path
    prompt: str
    target_sites: list[dict[str, str]]
    launched: bool = False
    launch_error: str = ""


def _keywords(scanner_keywords: str | None = None) -> str:
    configured = str(scan_settings().get("default_keywords") or "").strip()
    return (scanner_keywords or configured or "software engineer backend python").strip()


def _location() -> str:
    settings = scan_settings()
    preferred = str(settings.get("preferred_locations") or "").split(",")[0].strip()
    return preferred or str(settings.get("default_location") or "Remote").strip() or "Remote"


def _configured_site_names() -> list[str]:
    raw = str(scan_settings().get("codex_job_sites") or "")
    names = [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]
    return names or ["LinkedIn", "Indeed", "Greenhouse", "Lever", "Built In", "company career pages"]


def _target_sites(keywords: str, location: str) -> list[dict[str, str]]:
    query = quote_plus(keywords)
    place = quote_plus(location)
    templates = {
        "linkedin": f"https://www.linkedin.com/jobs/search/?keywords={query}&location={place}&sortBy=DD",
        "indeed": f"https://www.indeed.com/jobs?q={query}&l={place}&sort=date",
        "greenhouse": f"https://www.google.com/search?q={quote_plus(f'site:greenhouse.io/jobs OR site:boards.greenhouse.io {keywords} {location}')}",
        "lever": f"https://www.google.com/search?q={quote_plus(f'site:jobs.lever.co {keywords} {location}')}",
        "built in": f"https://builtin.com/jobs?search={query}&location={place}",
        "company career pages": f"https://www.google.com/search?q={quote_plus(f'{keywords} {location} company careers jobs')}",
    }
    targets: list[dict[str, str]] = []
    for name in _configured_site_names():
        key = name.lower()
        url = next((value for token, value in templates.items() if token in key), "")
        if not url:
            url = f"https://www.google.com/search?q={quote_plus(f'{name} {keywords} {location} jobs')}"
        targets.append({"name": name, "url": url})
    return targets


def _prompt(target_sites: list[dict[str, str]], *, limit: int, keywords: str, location: str) -> str:
    site_lines = "\n".join(f"- {site['name']}: {site['url']}" for site in target_sites)
    return f"""Use the local JobFiller MCP server.

Scan recent job postings that match these preferences:
- Keywords: {keywords}
- Location preference: {location}
- Maximum records to export: {limit}

Relevant job sites/searches:
{site_lines}

Prefer newest postings first. Do not apply, save jobs, message recruiters,
upload files, or click final submit buttons.

For each promising posting, call export_jobs_to_jobfiller. JobFiller will
automatically generate application artifacts when a job is not blocked by
missing information.
Include URL, apply_url when known, company, title, location, work_model,
role_family, key_requirements, keywords, posting_age_text, salary when listed,
materials, manual_questions, and concise notes. Reject unsafe or non-public URLs.

After exporting, summarize how many jobs were sent to JobFiller and which
postings were skipped.
"""


def create_codex_scan_request(
    *,
    limit: int,
    scanner_keywords: str | None = None,
) -> CodexScanRequest:
    keywords = _keywords(scanner_keywords)
    location = _location()
    targets = _target_sites(keywords, location)
    prompt = _prompt(targets, limit=limit, keywords=keywords, location=location)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "kind": "codex_job_site_scan",
        "limit": limit,
        "keywords": keywords,
        "location": location,
        "target_sites": targets,
        "mcp_tool": "export_jobs_to_jobfiller",
        "process": True,
        "prompt": prompt,
    }

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    REQUEST_JSON_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    REQUEST_PROMPT_PATH.write_text(prompt, encoding="utf-8")

    launched = False
    launch_error = ""
    command = os.environ.get("JOBFILLER_CODEX_SCAN_COMMAND", "").strip()
    if command:
        try:
            command_parts = shlex.split(command, posix=os.name != "nt")
            subprocess.Popen(
                [*command_parts, str(REQUEST_PROMPT_PATH)],
                cwd=str(Path(__file__).resolve().parents[3]),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            launched = True
        except Exception as exc:  # Keep Scan Now useful even if optional launch wiring is wrong.
            launch_error = str(exc)

    return CodexScanRequest(
        request_path=REQUEST_JSON_PATH,
        prompt_path=REQUEST_PROMPT_PATH,
        prompt=prompt,
        target_sites=targets,
        launched=launched,
        launch_error=launch_error,
    )
