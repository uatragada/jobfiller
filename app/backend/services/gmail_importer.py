from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

from ..settings import candidate_profile, scan_settings


MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)", re.S)
SALARY_RE = re.compile(r"\$\s?\d[\d,]*(?:K)?(?:\s*[-–]\s*\$\s?\d[\d,]*(?:K)?)?(?:\s*/\s*(?:year|yr|hour))?", re.I)
SENIORITY_RE = re.compile(r"\b(?:senior|staff|principal|lead|manager|director)\b", re.I)
EARLY_CAREER_RE = re.compile(r"\b(?:entry[ -]?level|new grad|associate|junior|graduate|internship|intern)\b", re.I)
FINANCE_RE = re.compile(
    r"\b(?:finance|financial|fintech|banking|investment|portfolio|capital markets|fp&a|payments|risk|trading)\b",
    re.I,
)
SOFTWARE_RE = re.compile(r"\b(?:software|backend|full stack|full-stack|api|platform|developer|engineer|ai|data)\b", re.I)


@dataclass(frozen=True)
class ParsedEmailJob:
    url: str
    company: str
    title: str
    location: str = ""
    work_model: str = ""
    role_family: str = ""
    key_requirements: str = ""
    keywords: str = ""
    fit_score: int = 0
    notes: str = ""
    posting_age_text: str = "today"
    raw_text: str = ""
    materials: str = "Resume; cover letter if requested"
    manual_questions: str = ""
    salary: str = ""
    apply_url: str = ""

    def as_import_record(self) -> dict[str, object]:
        return {
            "url": self.url,
            "apply_url": self.apply_url or self.url,
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "work_model": self.work_model,
            "role_family": self.role_family,
            "key_requirements": self.key_requirements,
            "keywords": self.keywords,
            "fit_score": self.fit_score,
            "notes": self.notes,
            "posting_age_text": self.posting_age_text,
            "raw_text": self.raw_text,
            "materials": self.materials,
            "manual_questions": self.manual_questions,
            "salary": self.salary,
        }


def parse_gmail_alert_email(message: Mapping[str, object]) -> list[ParsedEmailJob]:
    body = _clean_text(str(message.get("body") or ""))
    subject = _clean_text(str(message.get("subject") or ""))
    sender = _clean_text(str(message.get("from_") or message.get("from") or ""))
    message_id = _clean_text(str(message.get("id") or ""))
    email_ts = _clean_text(str(message.get("email_ts") or ""))

    if not body and not subject:
        return []

    parsers = (
        _parse_indeed_alert,
        _parse_linkedin_alert,
        _parse_ladders_alert,
        _parse_glassdoor_alert,
        _parse_generic_subject_alert,
    )
    parsed: list[ParsedEmailJob] = []
    seen: set[tuple[str, str, str]] = set()
    for parser in parsers:
        for job in parser(subject, sender, body, message_id, email_ts):
            key = (_canonical_job_url(job.url), job.company.lower(), job.title.lower())
            if key in seen:
                continue
            seen.add(key)
            parsed.append(job)
    return parsed


def parse_gmail_alerts(messages: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    for message in messages:
        for job in parse_gmail_alert_email(message):
            canonical = _canonical_job_url(job.url)
            if canonical in seen_urls:
                continue
            seen_urls.add(canonical)
            records.append(job.as_import_record())
    return records


def _parse_linkedin_alert(
    subject: str,
    sender: str,
    body: str,
    message_id: str,
    email_ts: str,
) -> list[ParsedEmailJob]:
    if "linkedin" not in sender.lower() and "linkedin" not in body.lower():
        return []
    jobs: list[ParsedEmailJob] = []
    for label, url in _markdown_links(body):
        if "/jobs/view/" not in url:
            continue
        lines = _meaningful_lines(label)
        if len(lines) < 2:
            continue
        title = lines[0]
        company, location, work_model = _split_company_location(lines[1])
        if not company or not title or company.lower() in {"linkedin", "premium icon"}:
            continue
        salary = _extract_salary("\n".join(lines[1:]))
        if salary:
            location = _strip_salary(location)
        jobs.append(
            _finalize_job(
                url=url,
                company=company,
                title=title,
                location=location,
                work_model=work_model,
                salary=salary,
                source_name="LinkedIn Job Alert",
                subject=subject,
                sender=sender,
                message_id=message_id,
                email_ts=email_ts,
                raw_text="\n".join(lines[:5]),
            )
        )
    return jobs


def _parse_indeed_alert(
    subject: str,
    sender: str,
    body: str,
    message_id: str,
    email_ts: str,
) -> list[ParsedEmailJob]:
    if "indeed" not in sender.lower() and "indeed" not in body.lower():
        return []
    title = ""
    company = ""
    match = re.search(r"(.+?)\s+@\s+(.+)$", subject)
    if match:
        title = _clean_text(match.group(1))
        company = _clean_text(match.group(2))

    links = [(label, url) for label, url in _markdown_links(body) if "bad match" not in label.lower()]
    url = next((url for label, url in links if "view job" in label.lower()), "")
    if not url and links:
        url = links[0][1]
    if not url:
        return []

    if not title:
        title = _clean_text(next((label for label, _url in links if label.lower() not in {"view job", "learn more"}), "Imported Job"))
    if not company:
        company = _line_after(body, title) or "Unknown Company"
    location = _line_after(body, company)
    salary = _extract_salary(body)
    work_model = _infer_work_model(f"{title} {location} {body}")
    requirements = _job_description_excerpt(body) or f"{title}; {company}; {location}"
    return [
        _finalize_job(
            url=url,
            company=company,
            title=title,
            location=location,
            work_model=work_model,
            salary=salary,
            source_name="Indeed Job Match",
            subject=subject,
            sender=sender,
            message_id=message_id,
            email_ts=email_ts,
            raw_text=requirements,
        )
    ]


def _parse_ladders_alert(
    subject: str,
    sender: str,
    body: str,
    message_id: str,
    email_ts: str,
) -> list[ParsedEmailJob]:
    if "ladders" not in sender.lower() and "ladders" not in body.lower():
        return []
    jobs: list[ParsedEmailJob] = []
    for label, url in _markdown_links(body):
        if "ladders.co" not in urlparse(url).netloc.lower():
            continue
        lines = _meaningful_lines(label)
        if len(lines) < 3:
            continue
        company_line = next((line for line in reversed(lines) if "|" in line), "")
        if not company_line:
            continue
        company, location = [_clean_text(part) for part in company_line.split("|", 1)]
        salary = _extract_salary("\n".join(lines))
        title = next((line for line in lines if line.lower() != "remote" and not SALARY_RE.search(line) and "|" not in line), "")
        if not title or not company:
            continue
        work_model = _infer_work_model(f"{' '.join(lines)} {location}")
        jobs.append(
            _finalize_job(
                url=url,
                company=company,
                title=title,
                location=location,
                work_model=work_model,
                salary=salary,
                source_name="Ladders Job Alert",
                subject=subject,
                sender=sender,
                message_id=message_id,
                email_ts=email_ts,
                raw_text="\n".join(lines),
            )
        )
    return jobs


def _parse_glassdoor_alert(
    subject: str,
    sender: str,
    body: str,
    message_id: str,
    email_ts: str,
) -> list[ParsedEmailJob]:
    if "glassdoor" not in sender.lower() and "glassdoor" not in body.lower():
        return []
    jobs: list[ParsedEmailJob] = []
    for label, url in _markdown_links(body):
        if "glassdoor.com" not in urlparse(url).netloc.lower() or "job" not in url.lower():
            continue
        lines = _meaningful_lines(label)
        if len(lines) < 3:
            continue
        company, title, location = lines[0], lines[1], lines[2]
        salary = _extract_salary("\n".join(lines[3:]))
        jobs.append(
            _finalize_job(
                url=url,
                company=company,
                title=title,
                location=location,
                work_model=_infer_work_model(f"{title} {location} {' '.join(lines)}"),
                salary=salary,
                source_name="Glassdoor Job Alert",
                subject=subject,
                sender=sender,
                message_id=message_id,
                email_ts=email_ts,
                raw_text="\n".join(lines),
            )
        )
    return jobs


def _parse_generic_subject_alert(
    subject: str,
    sender: str,
    body: str,
    message_id: str,
    email_ts: str,
) -> list[ParsedEmailJob]:
    match = re.search(r"(.+?)\s+(?:at|@)\s+(.+)$", subject, re.I)
    if not match:
        return []
    title = _clean_text(match.group(1))
    company = _clean_text(match.group(2))
    if not SOFTWARE_RE.search(title) and not FINANCE_RE.search(title):
        return []
    url = next((url for _label, url in _markdown_links(body) if _looks_like_job_url(url)), "")
    if not url:
        return []
    return [
        _finalize_job(
            url=url,
            company=company,
            title=title,
            location="",
            work_model=_infer_work_model(f"{title} {body}"),
            salary=_extract_salary(body),
            source_name="Gmail Job Alert",
            subject=subject,
            sender=sender,
            message_id=message_id,
            email_ts=email_ts,
            raw_text=body[:2000],
        )
    ]


def _finalize_job(
    *,
    url: str,
    company: str,
    title: str,
    location: str,
    work_model: str,
    salary: str,
    source_name: str,
    subject: str,
    sender: str,
    message_id: str,
    email_ts: str,
    raw_text: str,
) -> ParsedEmailJob:
    company = _clean_text(company)
    title = _clean_text(title)
    location = _clean_location(location)
    work_model = work_model or _infer_work_model(f"{title} {location} {raw_text}")
    role_family = _infer_role_family(title, raw_text)
    key_requirements = _key_requirements(title, company, location, raw_text)
    keywords = _keywords(title, company, location, raw_text, role_family)
    manual_questions = "\n".join(_manual_questions(title, company, location, raw_text))
    notes = "; ".join(
        part
        for part in [
            f"Imported from {source_name}",
            f"Gmail message {message_id}" if message_id else "",
            f"received {email_ts}" if email_ts else "",
            f"subject: {subject}" if subject else "",
            f"sender: {sender}" if sender else "",
        ]
        if part
    )
    record = {
        "title": title,
        "company": company,
        "location": location,
        "work_model": work_model,
        "role_family": role_family,
        "key_requirements": key_requirements,
        "keywords": keywords,
        "salary": salary,
        "raw_text": raw_text,
    }
    return ParsedEmailJob(
        url=url,
        apply_url=url,
        company=company,
        title=title,
        location=location,
        work_model=work_model,
        role_family=role_family,
        key_requirements=key_requirements,
        keywords=keywords,
        fit_score=score_job_against_profile(record),
        notes=notes,
        raw_text=raw_text[:25000],
        manual_questions=manual_questions,
        salary=salary,
    )


def score_job_against_profile(
    job: Mapping[str, object],
    profile: Mapping[str, object] | None = None,
    scan: Mapping[str, object] | None = None,
) -> int:
    profile = profile if profile is not None else candidate_profile()
    scan = scan if scan is not None else scan_settings()
    text = _clean_text(
        " ".join(
            str(job.get(key) or "")
            for key in (
                "title",
                "company",
                "location",
                "work_model",
                "role_family",
                "key_requirements",
                "keywords",
                "salary",
                "raw_text",
            )
        )
    ).lower()
    title = str(job.get("title") or "").lower()
    location = str(job.get("location") or "").lower()
    work_model = str(job.get("work_model") or "").lower()
    profile_text = _profile_text(profile)
    profile_skills = [str(skill).strip().lower() for skill in profile.get("skills", []) if str(skill).strip()]

    score = 54
    matched_skills = [skill for skill in profile_skills if _skill_matches(skill, text)]
    score += min(28, len(matched_skills) * 4)

    if SOFTWARE_RE.search(text):
        score += 10
    if any(term in title for term in ("backend", "api", "platform", "data", "ai")):
        score += 8
    if FINANCE_RE.search(text):
        score += 8 if any(term in profile_text for term in ("economics", "finance", "wex", "payments")) else 3
    if EARLY_CAREER_RE.search(text):
        score += 7
    if SENIORITY_RE.search(text):
        score -= 13
    if "internship" in text or re.search(r"\bintern\b", text):
        score -= 8

    preferred_location_terms = _configured_location_terms(scan)
    if "remote" in work_model or "remote" in location:
        score += 9
    if location and any(term in location for term in preferred_location_terms):
        score += 6
    elif "on-site" in work_model or "onsite" in work_model:
        score -= 4

    if any(term in text for term in ("python", "fastapi", "api", "sql", "java", "react", "typescript", "data pipeline")):
        score += 5
    if any(term in text for term in ("civil engineering", "retail", "teacher")):
        score -= 20

    return max(0, min(99, score))


def _markdown_links(text: str) -> list[tuple[str, str]]:
    return [(_clean_text(label), url.strip()) for label, url in MARKDOWN_LINK_RE.findall(text or "")]


def _meaningful_lines(text: str) -> list[str]:
    return [
        _clean_text(line)
        for line in re.split(r"[\r\n]+", text)
        if _clean_text(line) and not _clean_text(line).lower().endswith("icon")
    ]


def _split_company_location(line: str) -> tuple[str, str, str]:
    if " · " not in line:
        return _clean_text(line), "", ""
    company, rest = [_clean_text(part) for part in line.split(" · ", 1)]
    work_model = ""
    model_match = re.search(r"\((Remote|Hybrid|On-site|Onsite)\)", rest, re.I)
    if model_match:
        work_model = _normalize_work_model(model_match.group(1))
    rest = re.sub(r"\((Remote|Hybrid|On-site|Onsite)\)", "", rest, flags=re.I)
    rest = re.sub(r"\b(?:Actively recruiting|Easy Apply|University of Pittsburgh|DataAnnotation|company alum(?:ni)?|school alum(?:ni)?).*$", "", rest, flags=re.I)
    return company, _clean_location(rest), work_model


def _line_after(body: str, needle: str) -> str:
    lines = _meaningful_lines(body)
    for index, line in enumerate(lines[:-1]):
        if line.lower() == needle.lower():
            return lines[index + 1]
    return ""


def _job_description_excerpt(body: str) -> str:
    marker = re.search(r"Job description\s+(.+?)(?:\n\n\[|Do you want to|get more jobs|Indeed Resume|©)", body, re.I | re.S)
    if marker:
        return _clean_text(marker.group(1))[:4000]
    return _clean_text(body)[:2000]


def _extract_salary(text: str) -> str:
    match = SALARY_RE.search(text or "")
    return _clean_text(match.group(0).replace("*", "")) if match else ""


def _strip_salary(value: str) -> str:
    return _clean_text(SALARY_RE.sub("", value))


def _clean_text(value: str) -> str:
    return re.sub(r"[ \t]+", " ", str(value or "").replace("\u200c", "").replace("\u200f", "")).strip()


def _clean_location(value: str) -> str:
    value = _strip_salary(value)
    value = re.sub(r"\b(?:John Mancuso|Elgin Meadors)\b.*$", "", value).strip()
    value = re.sub(r"\b\d+\s+(?:connection|connections|company alumni|school alumni).*$", "", value, flags=re.I).strip()
    return _clean_text(value.strip(" -|,"))


def _infer_work_model(text: str) -> str:
    lowered = text.lower()
    if "remote" in lowered or "virtual / travel" in lowered:
        return "Remote"
    if "hybrid" in lowered:
        return "Hybrid"
    if "on-site" in lowered or "onsite" in lowered:
        return "On-site"
    return ""


def _normalize_work_model(value: str) -> str:
    lowered = value.lower()
    if lowered == "onsite":
        return "On-site"
    return "On-site" if lowered == "on-site" else value.title()


def _infer_role_family(title: str, raw_text: str) -> str:
    text = f"{title} {raw_text}"
    if FINANCE_RE.search(text):
        return "Finance"
    if SOFTWARE_RE.search(text):
        return "Software Engineering"
    return "General"


def _key_requirements(title: str, company: str, location: str, raw_text: str) -> str:
    tokens = _ordered_unique(
        [
            title,
            company,
            location,
            *_keyword_hits(raw_text, include_soft=True),
        ]
    )
    return "; ".join(tokens[:12])


def _keywords(title: str, company: str, location: str, raw_text: str, role_family: str) -> str:
    tokens = _ordered_unique([role_family, *_keyword_hits(f"{title} {company} {location} {raw_text}")])
    return "; ".join(tokens[:14])


def _keyword_hits(text: str, *, include_soft: bool = False) -> list[str]:
    candidates = [
        ("backend", "Backend"),
        ("software", "Software Engineering"),
        ("api", "APIs"),
        ("python", "Python"),
        ("fastapi", "FastAPI"),
        ("java", "Java"),
        ("spring boot", "Spring Boot"),
        ("javascript", "JavaScript"),
        ("react", "React"),
        ("typescript", "TypeScript"),
        ("sql", "SQL"),
        ("data", "Data"),
        ("ai", "AI"),
        ("llm", "LLM"),
        ("finance", "Finance"),
        ("financial", "Finance"),
        ("banking", "Banking"),
        ("capital markets", "Capital Markets"),
        ("payments", "Payments"),
        ("testing", "Testing"),
        ("public trust", "Public Trust"),
        ("u.s. citizenship", "U.S. citizenship"),
        ("clearance", "Clearance"),
    ]
    lowered = text.lower()
    hits = [label for token, label in candidates if token in lowered]
    if include_soft and not hits:
        hits.append("Review job posting details")
    return hits


def _manual_questions(title: str, company: str, location: str, raw_text: str) -> list[str]:
    text = f"{title} {company} {location} {raw_text}".lower()
    questions: list[str] = []
    if any(term in text for term in ("u.s. citizenship", "us citizenship", "public trust", "clearance")):
        questions.append("Confirm U.S. citizenship and public-trust/clearance eligibility before applying.")
    if FINANCE_RE.search(text):
        questions.append("Confirm finance motivation and any finance, economics, payments, or analytics evidence to reference.")
    if SENIORITY_RE.search(text):
        questions.append("Confirm whether the seniority level is realistic and which experience should support it.")
    if "on-site" in text or "onsite" in text:
        questions.append("Confirm commute or relocation fit for the on-site requirement.")
    return questions


def _ordered_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _canonical_job_url(url: str) -> str:
    parsed = urlparse(url)
    if "linkedin.com" in parsed.netloc.lower() and "/jobs/view/" in parsed.path:
        match = re.search(r"(\d+)", parsed.path)
        if match:
            return f"https://www.linkedin.com/jobs/view/{match.group(1)}"
    return url


def _looks_like_job_url(url: str) -> bool:
    parsed = urlparse(url)
    host_path = f"{parsed.netloc.lower()}{parsed.path.lower()}"
    return any(token in host_path for token in ("linkedin.com/jobs", "indeed.com", "glassdoor.com", "ladders.co", "greenhouse.io", "lever.co", "workdayjobs.com"))


def _profile_text(profile: Mapping[str, object]) -> str:
    chunks = [str(profile.get("summary") or ""), " ".join(str(skill) for skill in profile.get("skills", []) or [])]
    for collection_name in ("education", "experience", "projects"):
        for item in profile.get(collection_name, []) or []:
            if isinstance(item, Mapping):
                chunks.extend(str(value) for value in item.values())
    return " ".join(chunks).lower()


def _configured_location_terms(scan: Mapping[str, object]) -> list[str]:
    values = [
        str(scan.get("default_location") or ""),
        str(scan.get("preferred_locations") or ""),
    ]
    return [
        part
        for value in values
        for part in (_clean_text(token).lower() for token in re.split(r"[;,]", value))
        if part
    ]


def _skill_matches(skill: str, text: str) -> bool:
    normalized = skill.lower().strip()
    if not normalized:
        return False
    aliases = {
        "backend services": ("backend", "api", "service"),
        "rest apis": ("api", "rest"),
        "data pipelines": ("data pipeline", "data", "etl"),
        "openai api": ("openai", "llm", "ai"),
    }
    return normalized in text or any(alias in text for alias in aliases.get(normalized, ()))
