from __future__ import annotations

"""Local Ollama grading and PDF validation service."""

import json
import os
import re
from dataclasses import dataclass
import urllib.request
from typing import Any

from ..settings import llm_settings
from ..models import Artifact, Grade, Job
from .normalize import unsafe_loopback_http_url_reason


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def allow_remote_ollama() -> bool:
    return os.environ.get("JOBFILLER_ALLOW_REMOTE_OLLAMA", "").strip().lower() in {"1", "true", "yes"}


def ollama_url_policy(value: str | None = None) -> dict[str, object]:
    configured = str(value if value is not None else llm_settings().get("ollama_url") or DEFAULT_OLLAMA_URL).strip().rstrip("/")
    reason = unsafe_loopback_http_url_reason(configured)
    allowed_remote = allow_remote_ollama()
    blocked = bool(reason and not allowed_remote)
    return {
        "configured_url": configured,
        "effective_url": DEFAULT_OLLAMA_URL if blocked else configured,
        "blocked": blocked,
        "reason": reason or "",
        "mode": "remote" if reason and allowed_remote else "local",
    }


def ollama_base_url() -> str:
    return str(ollama_url_policy()["effective_url"]).rstrip("/")


def ollama_generate_url() -> str:
    return f"{ollama_base_url()}/api/generate"


def ollama_tags_url() -> str:
    return f"{ollama_base_url()}/api/tags"


def configured_model() -> str:
    return str(llm_settings().get("model") or "").strip()


def grading_model_name() -> str:
    return configured_model() or "ollama:auto"


def extract_pdf_text(path: str) -> tuple[str, int]:
    try:
        import pdfplumber
    except Exception:  # pragma: no cover - optional dependency
        return "PDF text extraction unavailable in this environment.", 0
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages), len(pdf.pages)
    except Exception as exc:  # pragma: no cover - resilient fallback for transient PDF parse problems
        return f"PDF text extraction failed: {exc}", 0


@dataclass(frozen=True)
class ResumeValidationResult:
    passes: dict[str, bool]
    scores: dict[str, float]
    risks: list[str]
    edits: list[str]
    keyword_hits: list[str]


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("\n", " ").split())


def _split_keywords(value: str) -> tuple[str, ...]:
    return tuple(item.strip().lower() for item in value.split(";") if item.strip())


def _normalize_keyword_phrase(phrase: str) -> str:
    return re.sub(r"[^a-z0-9 +/\\-]", " ", phrase.lower()).strip()


def _contains_phrase(source: str, phrase: str) -> bool:
    normalized_phrase = _normalize_keyword_phrase(phrase)
    if not normalized_phrase:
        return False
    return normalized_phrase in source


def _missing_from_keywords(source: str, job: Job) -> tuple[list[str], list[str]]:
    keywords = _split_keywords(job.keywords)
    matches = []
    missing = []
    for keyword in keywords:
        normalized = _normalize_keyword_phrase(keyword)
        if not normalized:
            continue
        if normalized in source:
            matches.append(keyword)
        else:
            missing.append(keyword)
    return matches, missing


def _target_tokens_found(source: str, job: Job) -> list[str]:
    title = _normalize_keyword_phrase(job.title or "")
    if not title:
        return []
    result: list[str] = []
    title_tokens = [token for token in re.split(r"[\s\-_/]+", title) if len(token) > 2]
    for token in title_tokens:
        if token in source:
            result.append(token)
    return result


def _has_bottom_technologies_section(source: str) -> bool:
    tail = source[-950:] if len(source) > 950 else source
    return bool(re.search(r"\btechnolog(?:ies|y)\s*:", tail))


def _section_hit(text: str, needle: str) -> bool:
    return bool(re.search(rf"\b{re.escape(needle.lower())}\b", text.lower()))


def validate_resume_text(job: Job, text: str, page_count: int) -> ResumeValidationResult:
    normalized = _normalize_text(text)
    company_hit = _contains_phrase(normalized, job.company)
    title_hits = _target_tokens_found(normalized, job)
    keyword_hits, missing_keywords = _missing_from_keywords(normalized, job)
    keyword_ratio = len(keyword_hits) / max(1, len(_split_keywords(job.keywords)))
    no_project_dates = not _section_hit(normalized, "project dates")

    no_target_or_objective = not bool(
        re.search(r"\b(target|objective)\s*(section|statement)?\b", normalized)
    )
    bottom_technologies_present = _has_bottom_technologies_section(normalized)
    profile_placeholder_present = bool(
        re.search(
            r"\b(your name|add contact information|add education in settings|configure profile|configured candidate project|add your experience)\b",
            normalized,
        )
    )

    passes = {
        "one_page": page_count <= 1,
        "no_target_or_objective": no_target_or_objective,
        "no_project_dates": no_project_dates,
        "no_bottom_technologies_section": not bottom_technologies_present,
        "clear_bold_hierarchy": True,
        "keywords_match_role": keyword_ratio >= 0.20 or len(keyword_hits) >= 2,
        "company_and_role_reference": company_hit and len(title_hits) >= 1,
        "profile_configured": not profile_placeholder_present,
    }

    scores = {
        "role_fit": min(1.0, 0.4 + (len(title_hits) * 0.12) + (0.22 if company_hit else 0.0)),
        "tailoring": min(1.0, 0.3 + keyword_ratio * 0.9),
        "technical_strength": min(1.0, 0.6 + (len(keyword_hits) * 0.08)),
        "formatting": 1.0 if passes["one_page"] and passes["no_bottom_technologies_section"] else 0.72,
        "ats_readability": 0.92 if passes["keywords_match_role"] else 0.64,
    }

    risks: list[str] = []
    edits: list[str] = []
    if not passes["one_page"]:
        risks.append("Resume appears to exceed one page.")
        edits.append("Condense resume content to one page to improve ATS compatibility and recruiter scan speed.")
    if not passes["no_target_or_objective"]:
        risks.append("Detected possible Target/Objective section text.")
        edits.append("Remove any Target/Objective section to match your requested structure.")
    if not passes["no_project_dates"]:
        risks.append("Detected project-date phrasing.")
        edits.append("Ensure project blocks do not include date ranges.")
    if not passes["no_bottom_technologies_section"]:
        risks.append("Detected a bottom technologies-style heading.")
        edits.append("Remove the standalone bottom technologies section.")
    if not passes["company_and_role_reference"]:
        risks.append("Company/role evidence in the extracted resume text is weak.")
        edits.append("Keep company and role-relevant language explicit in the first sections of the resume.")
    if missing_keywords:
        risks.append(f"Keyword coverage is partial. Missing {len(missing_keywords)} target keyword(s).")
        edits.append("Add stronger evidence around the strongest missing technical keywords in projects or summary bullets.")
    if profile_placeholder_present:
        risks.append("Candidate profile appears incomplete; placeholder resume text is present.")
        edits.append("Complete Settings with a real candidate profile before using this artifact.")

    return ResumeValidationResult(
        passes=passes,
        scores=scores,
        risks=risks,
        edits=edits,
        keyword_hits=keyword_hits,
    )


def _merge_grade_payload(job: Job, parsed: dict[str, Any], validation: ResumeValidationResult) -> dict[str, Any]:
    passes = dict(validation.passes)
    if not isinstance(parsed.get("passes"), dict):
        parsed["passes"] = passes
    else:
        for key, value in passes.items():
            parsed["passes"][key] = bool(parsed["passes"].get(key, value)) and bool(value)
    parsed_scores = dict(parsed.get("scores", {}))
    if not parsed_scores:
        parsed_scores = {
            "role_fit": 0.6,
            "tailoring": 0.6,
            "technical_strength": 0.6,
            "formatting": 0.6,
            "ats_readability": 0.6,
        }
    for key, value in validation.scores.items():
        parsed_scores[key] = min(float(parsed_scores.get(key, value)), value)
    parsed["scores"] = parsed_scores

    model_risks = [str(item) for item in (parsed.get("top_risks") or []) if str(item).strip()]
    risks = list(dict.fromkeys(model_risks + validation.risks))
    parsed["top_risks"] = risks[:5]

    model_edits = [str(item) for item in (parsed.get("recommended_edits") or []) if str(item).strip()]
    edits = list(dict.fromkeys(model_edits + validation.edits))
    parsed["recommended_edits"] = edits[:5]

    parsed_keyword_hits = list(dict.fromkeys([*validation.keyword_hits, *(parsed.get("keyword_hits") or [])]))
    parsed["keyword_hits"] = parsed_keyword_hits

    parsed_ready = bool(parsed.get("ready_to_send"))
    blocking = not all(parsed["passes"].values())
    parsed["ready_to_send"] = parsed_ready and not blocking

    if validation.passes["no_bottom_technologies_section"] is False:
        parsed["overall_grade"] = "C"
    elif not validation.passes["no_target_or_objective"]:
        parsed["overall_grade"] = "C-"
    elif blocking:
        parsed["overall_grade"] = parsed.get("overall_grade") or "C-"

    return parsed


def _build_fallback_grade(job: Job) -> dict[str, object]:
    return {
        "overall_grade": "B",
        "ready_to_send": False,
        "scores": {
            "role_fit": 0.65,
            "tailoring": 0.65,
            "technical_strength": 0.75,
            "formatting": 0.75,
            "ats_readability": 0.8,
        },
        "passes": {
            "one_page": True,
            "no_target_or_objective": True,
            "no_project_dates": True,
            "no_bottom_technologies_section": True,
            "clear_bold_hierarchy": True,
            "keywords_match_role": bool(job.keywords),
        },
        "top_risks": [
            "Automated fallback grade: review for role-specific proof points and exactness of project details.",
        ],
        "recommended_edits": [
            "Confirm quantified impact statements where available.",
            "Verify final PDF renders cleanly in your target application systems.",
            "Manually verify no prohibited sections remain before final submission.",
        ],
    }


def _compact(value: str, limit: int = 6500) -> str:
    value = re.sub(r"\n{3,}", "\n\n", value.strip())
    return value if len(value) <= limit else value[:limit] + "\n...[truncated for grading prompt]"


def grade_resume(job: Job, artifact: Artifact) -> Grade:
    text, page_count = extract_pdf_text(artifact.resume_pdf_path)
    validation = validate_resume_text(job, text, page_count)
    prompt = f"""Grade this tailored resume for a specific job. Be strict but practical.

Job: {job.company} - {job.title}
Requirements: {job.key_requirements}
Keywords: {job.keywords}

Known checks:
- PDF page count: {page_count}
- No Target or Objective section is allowed.
- Project dates should be removed.
- Standalone bottom Technologies section should be removed.
- Project-specific inline Technologies lines are allowed.
- Rendered PDF uses bold job and project headings.

Resume text:
---
{_compact(text)}
---

Return JSON only:
{{
  "overall_grade": "A+|A|A-|B+|B|B-|C+|C|C-|D|F",
  "ready_to_send": true,
  "scores": {{"role_fit": 1, "tailoring": 1, "technical_strength": 1, "formatting": 1, "ats_readability": 1}},
  "passes": {{"one_page": true, "no_target_or_objective": true, "no_project_dates": true, "no_bottom_technologies_section": true, "clear_bold_hierarchy": true, "keywords_match_role": true}},
  "top_risks": ["risk 1", "risk 2", "risk 3"],
  "recommended_edits": ["edit 1", "edit 2", "edit 3"]
}}
"""
    payload = {
        "model": configured_model(),
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": float(llm_settings().get("temperature") or 0.1),
            "num_ctx": int(llm_settings().get("num_ctx") or 8192),
        },
    }
    if not payload["model"]:
        base = _build_fallback_grade(job)
        parsed = _merge_grade_payload(job, base, validation)
        return Grade(
            job_id=job.id,
            artifact_id=artifact.id,
            model=grading_model_name(),
            overall_grade=str(parsed.get("overall_grade", "")),
            ready_to_send=bool(parsed.get("ready_to_send")),
            scores_json=json.dumps(parsed.get("scores", {})),
            passes_json=json.dumps(parsed.get("passes", {})),
            risks_json=json.dumps(parsed.get("top_risks", [])),
            raw_json=json.dumps({**parsed, "notice": "No Ollama model configured; used deterministic fallback grade."}),
        )
    request = urllib.request.Request(
        ollama_generate_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = json.loads(response.read().decode("utf-8")).get("response", "{}")
        parsed = json.loads(raw)
        parsed = _merge_grade_payload(job, parsed, validation)
    except Exception:
        base = _build_fallback_grade(job)
        parsed = _merge_grade_payload(job, base, validation)

    return Grade(
        job_id=job.id,
        artifact_id=artifact.id,
        model=grading_model_name(),
        overall_grade=str(parsed.get("overall_grade", "")),
        ready_to_send=bool(parsed.get("ready_to_send")),
        scores_json=json.dumps(parsed.get("scores", {})),
        passes_json=json.dumps(parsed.get("passes", {})),
        risks_json=json.dumps(parsed.get("top_risks", [])),
        raw_json=json.dumps(parsed),
    )
