from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..settings import scan_settings
from ..models import Job, JobPost, Run, utcnow
from .normalize import canonicalize_url, infer_from_url, unsafe_import_url_reason
from .time_utils import parse_posting_age, scan_sort_key


DEFAULT_SCAN_LIMIT = 20
AGE_FROM_TITLE_RE = re.compile(
    r"\b(?:just posted|today|yesterday|\d+(?:-\d+)?\s*(?:minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago)\b",
    re.I,
)
WORK_MODEL_PATTERNS = (
    ("remote", "Remote"),
    ("work from home", "Remote"),
    ("remote est", "Remote"),
    ("wfh", "Remote"),
    ("hybrid", "Hybrid"),
)
GENERIC_LOCATION_SKIP_WORDS = {"remote", "hybrid", "onsite", "candidate-selected regions", "near me", "open"}


def _split_semicolon(value: str | list[str] | tuple[str, ...] | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return "; ".join(str(item) for item in value)


def _as_text(value: object) -> str:
    return str(value or "").strip()


def _title_tokens(value: str | None) -> tuple[str, ...]:
    title = (value or "").replace("|", " - ")
    return tuple(part.strip() for part in title.split(" - ") if part.strip())


def _seed_data_path() -> Path:
    return Path(scan_settings().get("seed_data_path") or Path(__file__).resolve().parents[3] / "examples" / "jobs.sample.json")


def _default_location() -> str:
    return str(scan_settings().get("default_location") or "Remote")


def _default_work_model() -> str:
    return str(scan_settings().get("default_work_model") or "Remote")


def _default_keywords() -> str:
    return str(scan_settings().get("default_keywords") or "software; resume; cover letter")


def _configured_locations() -> tuple[str, ...]:
    settings = scan_settings()
    raw_locations = [
        str(settings.get("default_location") or ""),
        *re.split(r"[,;]", str(settings.get("preferred_locations") or "")),
    ]
    locations = []
    for value in raw_locations:
        location = re.sub(r"\s+", " ", value.strip())
        if not location:
            continue
        if location.lower() in GENERIC_LOCATION_SKIP_WORDS:
            continue
        if location.lower() not in {item.lower() for item in locations}:
            locations.append(location)
    return tuple(locations)


def _infer_location(title: str) -> str:
    lowered = title.lower()
    for location in _configured_locations():
        if location.lower() in lowered:
            return location
    return _default_location()


def _infer_work_model(title: str, location: str, fallback: str | None = None) -> str:
    source_text = f"{title} {location}".lower()
    for token, model in WORK_MODEL_PATTERNS:
        if token in source_text:
            return model
    return fallback or _default_work_model()


def _extract_posting_age_text(title: str | None) -> str:
    match = AGE_FROM_TITLE_RE.search(title or "")
    if not match:
        return ""
    return " ".join(match.group(0).split())


def _keyword_tokens(raw: str | list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, (list, tuple)):
        raw_values = raw
    else:
        raw_values = re.split(r"[;,]", str(raw))
    return tuple(_normalize_keyword(value) for value in raw_values if _normalize_keyword(value))


def _normalize_keyword(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _matches_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    haystack = text.lower()
    return any(keyword in haystack for keyword in keywords)


def estimate_fit(title: str, requirements: str, keywords: str) -> int:
    text = " ".join([title, requirements, keywords]).lower()
    score = 70
    configured_terms = _keyword_tokens(_default_keywords())
    for term in configured_terms or ("entry level", "associate", "junior", "new grad"):
        if term in text:
            score += 4
    for term in ("senior", "staff", "principal", "10+"):
        if term in text:
            score -= 15
    return max(0, min(99, score))


def upsert_job(db: Session, data: dict[str, object], source: str = "manual") -> Job:
    url = str(data.get("source_url") or data.get("url") or data.get("apply_url") or "").strip()
    if not url:
        raise ValueError("Job URL is required")
    canonical = canonicalize_url(url)
    job = db.scalars(select(Job).where(Job.canonical_url == canonical)).first()
    now = utcnow()
    company, title = infer_from_url(url)
    company = str(data.get("company") or company)
    title = str(data.get("title") or title)
    materials = _as_text(data.get("materials"))
    manual_questions = _as_text(data.get("manual_questions"))
    posting_age_text = str(data.get("posting_age") or data.get("posting_age_text") or "")
    posted_at = parse_posting_age(posting_age_text, now)
    if not job:
        job = Job(
            source_url=url,
            canonical_url=canonical,
            first_seen_at=now,
            source=source,
        )
        db.add(job)
    job.last_seen_at = now
    job.updated_at = now
    apply_url = str(data.get("apply_url") or url).strip()
    job.apply_url = url if unsafe_import_url_reason(apply_url) else apply_url
    job.company = company
    job.title = title
    job.location = str(data.get("location") or _default_location())
    job.work_model = str(data.get("work_model") or _default_work_model())
    job.role_family = str(data.get("role_family") or "General")
    job.key_requirements = _split_semicolon(data.get("key_requirements") or data.get("requirements") or title)
    job.keywords = _split_semicolon(data.get("keywords") or _default_keywords())
    if materials:
        job.materials = materials
    if manual_questions:
        job.manual_questions = manual_questions
    resume_focus = _as_text(data.get("resume_focus"))
    if not job.manual_questions and resume_focus:
        job.manual_questions = resume_focus
    job.salary = _as_text(data.get("salary"))
    job.posting_age_text = posting_age_text
    job.posted_at = posted_at
    job.fit_score = int(data.get("fit_score") or estimate_fit(job.title, job.key_requirements, job.keywords))
    job.notes = str(data.get("notes") or "")
    if job.status == "DISCOVERED":
        job.status = "PARSED"
    raw_text = str(data.get("raw_text") or data.get("cover_letter") or "")
    if job.post:
        job.post.raw_text = raw_text or job.post.raw_text
        job.post.parsed_requirements = job.key_requirements
        job.post.parsed_keywords = job.keywords
    else:
        job.post = JobPost(
            raw_text=raw_text,
            summary=str(data.get("resume_focus") or ""),
            parsed_requirements=job.key_requirements,
            parsed_keywords=job.keywords,
            compensation=str(data.get("salary") or ""),
        )
    db.flush()
    return job


def import_seed_jobs(
    db: Session,
    limit: int | None = None,
    *,
    remote_first: bool = True,
    scanner_keywords: str | None = None,
) -> list[Job]:
    seed_data = _seed_data_path()
    if not seed_data.exists():
        return []
    rows = json.loads(seed_data.read_text(encoding="utf-8"))
    keyword_tokens = _keyword_tokens(scanner_keywords)
    if keyword_tokens:
        rows = [
            row
            for row in rows
            if any(
                token in " ".join(
                    [
                        str(row.get("title", "")),
                        str(row.get("company", "")),
                        str(row.get("location", "")),
                        str(row.get("work_model", "")),
                        str(row.get("key_requirements", "")),
                        str(row.get("keywords", "")),
                    ]
                ).lower()
                for token in keyword_tokens
            )
        ]
    jobs = [upsert_job(db, row, source="seed") for row in rows]
    jobs.sort(
        key=lambda job: scan_sort_key(
            job.posted_at,
            job.first_seen_at,
            job.fit_score,
            remote_first=remote_first,
            location=job.location,
            work_model=job.work_model,
        ),
        reverse=True,
    )
    return jobs[: limit or len(jobs)]


def chrome_debug_tabs() -> list[dict[str, object]]:
    endpoint = os.environ.get("CHROME_CDP_URL", "http://127.0.0.1:9222/json")
    try:
        with urllib.request.urlopen(endpoint, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return []


def import_chrome_linkedin_jobs(
    db: Session,
    *,
    remote_first: bool = True,
    scanner_keywords: str | None = None,
) -> list[Job]:
    jobs: list[Job] = []
    for tab in chrome_debug_tabs():
        url = str(tab.get("url") or "")
        if "linkedin.com/jobs/" not in url or ("jobs/search" not in url and "jobs/view" not in url):
            continue
        title_text = str(tab.get("title") or "")
        if scanner_keywords and not _matches_any_keyword(f"{url} {title_text}", _keyword_tokens(scanner_keywords)):
            continue
        title_parts = _title_tokens(title_text)
        title = title_parts[0] if title_parts else "Imported Job"
        location = _infer_location(" ".join(title_parts))
        work_model = _infer_work_model(title, location)
        posting_age_text = _extract_posting_age_text(title_text)
        if "jobs/search" in url and "remote" in title_text.lower():
            work_model = "Remote"
        jobs.append(
            upsert_job(
                db,
                {
                    "url": url,
                    "title": title,
                    "location": location,
                    "work_model": work_model,
                    "posting_age": posting_age_text,
                    "raw_text": title_text,
                },
                source="chrome",
            )
        )
    jobs.sort(
        key=lambda job: scan_sort_key(
            job.posted_at,
            job.first_seen_at,
            job.fit_score,
            remote_first=remote_first,
            location=job.location,
            work_model=job.work_model,
        ),
        reverse=True,
    )
    return jobs


def run_scan(
    db: Session,
    run: Run,
    *,
    remote_first: bool = True,
    source: str | None = None,
    limit: int | None = None,
    scanner_keywords: str | None = None,
) -> tuple[int, str]:
    chrome_jobs = import_chrome_linkedin_jobs(
        db,
        remote_first=remote_first,
        scanner_keywords=scanner_keywords,
    )
    seed_jobs = import_seed_jobs(
        db,
        limit=limit,
        remote_first=remote_first,
        scanner_keywords=scanner_keywords,
    )
    if source and source != "all":
        target = source.lower()
        chrome_jobs = [job for job in chrome_jobs if target in job.source.lower() or target in job.source_url.lower()]
        seed_jobs = [job for job in seed_jobs if target in job.source.lower() or target in job.source_url.lower()]
    imported = len({job.id for job in chrome_jobs + seed_jobs})
    ordering = "remote-first" if remote_first else "standard"
    message = (
        f"Imported/updated {imported} jobs newest-first ({ordering}). "
        f"Chrome tabs: {len(chrome_jobs)}; seeded/current data: {len(seed_jobs)}."
    )
    run.status = "SUCCEEDED"
    run.message = message
    run.finished_at = utcnow()
    db.flush()
    return imported, message
