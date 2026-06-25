from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ApplicationEvent, Job, utcnow
from .ingestion import upsert_job
from .normalize import canonicalize_url, slugify, unsafe_import_url_reason


APPLICATION_STATES = {"DISCOVERED", "APPLIED", "ACTION_NEEDED", "INTERVIEW", "REJECTED"}
EMAIL_TRACKING_STATUS = "EMAIL_TRACKING"


@dataclass(frozen=True)
class ClassifiedEmail:
    state: str
    company: str
    title: str
    requisition_id: str
    follow_up_action: str
    action_url: str
    evidence: str


def sync_application_emails(
    db: Session,
    messages: list[dict[str, object]],
    *,
    source: str = "gmail",
) -> dict[str, object]:
    synced: list[ApplicationEvent] = []
    for message in sorted(messages, key=_message_received_at):
        classified = classify_application_email(message)
        job = _find_or_create_job(db, classified, message, source=source)
        event = _upsert_application_event(db, job, message, classified, source=source)
        _apply_event_to_job(job, event)
        synced.append(event)

    db.flush()
    states: dict[str, int] = {}
    for event in synced:
        states[event.state] = states.get(event.state, 0) + 1
    return {
        "synced": len(synced),
        "job_ids": sorted({event.job_id for event in synced}),
        "event_ids": [event.id for event in synced],
        "states": states,
    }


def classify_application_email(message: dict[str, object]) -> ClassifiedEmail:
    subject = _text(message.get("subject"))
    body = _text(message.get("body"))
    snippet = _text(message.get("snippet"))
    sender = _text(message.get("sender") or message.get("from_") or message.get("from"))
    normalized = _normalize_space(" ".join([subject, snippet, body]))
    lowered = normalized.lower()
    company, title, requisition_id = _extract_company_title_requisition(sender, normalized)
    action_url = _first_action_url(body) or _first_action_url(snippet)

    if _has_rejection_signal(lowered):
        state = "REJECTED"
        follow_up_action = "Mark this application closed; no reply is needed unless you want to revisit adjacent roles."
    elif _has_identity_or_task_signal(lowered):
        state = "ACTION_NEEDED"
        follow_up_action = "Open the candidate portal and complete the requested identity or account check with a fresh code."
    elif _has_interview_signal(lowered):
        state = "INTERVIEW"
        follow_up_action = "Review the recruiter request and schedule or confirm the interview promptly."
    elif _has_application_received_signal(lowered):
        state = "APPLIED"
        follow_up_action = "Application received; monitor the candidate portal and wait for the next update."
    else:
        state = "APPLIED"
        follow_up_action = "Review the status email and decide whether a manual follow-up is needed."

    evidence = _redact_sensitive_codes(normalized)[:1800]
    return ClassifiedEmail(
        state=state,
        company=company,
        title=title,
        requisition_id=requisition_id,
        follow_up_action=follow_up_action,
        action_url=action_url,
        evidence=evidence,
    )


def _upsert_application_event(
    db: Session,
    job: Job,
    message: dict[str, object],
    classified: ClassifiedEmail,
    *,
    source: str,
) -> ApplicationEvent:
    now = utcnow()
    external_id = _text(message.get("id"))
    event = db.scalars(
        select(ApplicationEvent).where(
            ApplicationEvent.source == source,
            ApplicationEvent.external_id == external_id,
        )
    ).first()
    if not event:
        event = ApplicationEvent(source=source, external_id=external_id, created_at=now)
        db.add(event)
    action_url, action_url_note = _safe_clickable_email_url(classified.action_url, "action_url")
    evidence_url, evidence_url_note = _safe_clickable_email_url(_text(message.get("display_url")), "evidence_url")
    event.job = job
    event.thread_id = _text(message.get("thread_id"))
    event.sender = _text(message.get("sender") or message.get("from_") or message.get("from"))
    event.subject = _text(message.get("subject"))
    event.snippet = _redact_sensitive_codes(_text(message.get("snippet")))[:4000]
    event.body_excerpt = _append_url_safety_notes(classified.evidence, action_url_note, evidence_url_note)
    event.state = classified.state
    event.follow_up_action = classified.follow_up_action
    event.action_url = action_url
    event.evidence_url = evidence_url
    event.received_at = _message_received_at(message)
    event.updated_at = now
    db.flush()
    return event


def _apply_event_to_job(job: Job, event: ApplicationEvent) -> None:
    current_at = job.last_status_email_at
    event_at = event.received_at or event.updated_at
    comparable_current = _comparable_datetime(current_at)
    comparable_event = _comparable_datetime(event_at) or utcnow()
    if comparable_current is not None and comparable_event < comparable_current:
        return
    if event.action_url and not unsafe_import_url_reason(event.action_url):
        job.apply_url = event.action_url
    job.application_state = event.state if event.state in APPLICATION_STATES else "APPLIED"
    job.follow_up_action = event.follow_up_action
    job.follow_up_due_at = None
    job.last_status_email_at = comparable_event
    job.last_status_email_subject = event.subject
    job.last_status_email_url = event.evidence_url
    job.updated_at = utcnow()


def _find_or_create_job(
    db: Session,
    classified: ClassifiedEmail,
    message: dict[str, object],
    *,
    source: str,
) -> Job:
    source_url = _synthetic_application_url(classified)
    canonical = canonicalize_url(source_url)
    jobs = db.scalars(select(Job)).all()
    for job in jobs:
        if canonicalize_url(job.source_url) == canonical:
            return job
    for job in jobs:
        if _same_label(job.company, classified.company) and _same_title_or_requisition(job, classified):
            return job

    apply_url = classified.action_url if classified.action_url and not unsafe_import_url_reason(classified.action_url) else source_url
    job = upsert_job(
        db,
        {
            "url": source_url,
            "company": classified.company,
            "title": classified.title,
            "apply_url": apply_url,
            "location": "Not listed",
            "work_model": "Not listed",
            "role_family": "Application Tracking",
            "key_requirements": classified.title,
            "keywords": "application status; gmail sync",
            "fit_score": 70,
            "notes": f"Seeded from {source} status email: {_text(message.get('subject'))}",
            "raw_text": _replace_unsafe_urls_with_notes(classified.evidence),
        },
        source=f"{source}-status",
    )
    job.status = EMAIL_TRACKING_STATUS
    return job


def _extract_company_title_requisition(sender: str, text: str) -> tuple[str, str, str]:
    lowered = text.lower()
    company = _company_from_sender(sender)
    title = "Application Status Update"
    requisition_id = ""

    application_match = re.search(r"application for\s+(.+?)\s+position at\s+(.+?)(?:[.;]|$)", text, re.I)
    if application_match:
        title, requisition_id = _split_requisition(_normalize_space(application_match.group(1)))
        company = _normalize_space(application_match.group(2)) or company

    job_match = re.search(
        r"(?:job application for|considered for the job|for job)\s+(.+?)\s+[—-]\s+([A-Z]?\d{6,10})\b",
        text,
        re.I,
    )
    if job_match:
        title = _normalize_space(job_match.group(1))
        requisition_id = job_match.group(2).strip()
    elif "confirm your identity" in lowered and title == "Application Status Update":
        title = "Application Identity Check"

    if title == "Application Status Update":
        title, fallback_req = _split_requisition(_title_from_subject(text))
        requisition_id = requisition_id or fallback_req
    return company, title, requisition_id


def _company_from_sender(sender: str) -> str:
    display = sender.split("<", 1)[0].strip().strip('"')
    display = re.sub(r"\b(no[-_ ]?reply|recruiting|careers|workday|team)\b", "", display, flags=re.I)
    return _normalize_space(display) or "Unknown Company"


def _same_title_or_requisition(job: Job, classified: ClassifiedEmail) -> bool:
    haystack = " ".join([job.title, job.source_url, job.apply_url, job.notes]).lower()
    if classified.requisition_id and classified.requisition_id.lower() in haystack:
        return True
    if classified.title == "Application Identity Check":
        return True
    return _same_label(job.title, classified.title)


def _same_label(a: str | None, b: str | None) -> bool:
    return _normalize_space(a or "").lower() == _normalize_space(b or "").lower()


def _synthetic_application_url(classified: ClassifiedEmail) -> str:
    parts = [classified.company, classified.title, classified.requisition_id]
    slug = slugify("-".join(part for part in parts if part))
    return f"https://jobfiller-status-sync.example/applications/{slug}"


def _safe_clickable_email_url(url: str, field_name: str) -> tuple[str, str]:
    cleaned = _text(url)
    if not cleaned:
        return "", ""
    reason = unsafe_import_url_reason(cleaned)
    if reason:
        return "", f"{field_name} ignored: {reason}"
    return cleaned, ""


def _append_url_safety_notes(evidence: str, *notes: str) -> str:
    sanitized = _replace_unsafe_urls_with_notes(evidence)
    usable_notes = [note for note in notes if note]
    if not usable_notes:
        return sanitized
    suffix = " ".join(f"[{note}]" for note in usable_notes)
    return f"{sanitized} {suffix}".strip()[:4000]


def _replace_unsafe_urls_with_notes(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        url = raw.rstrip(".,")
        trailing = raw[len(url) :]
        reason = unsafe_import_url_reason(url)
        if not reason:
            return raw
        return f"[unsafe URL removed: {reason}]{trailing}"

    return re.sub(r"https?://[^\s)\]>]+", replace, value or "")


def _message_received_at(message: dict[str, object]) -> datetime:
    value = message.get("received_at") or message.get("email_ts")
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _text(value)
        if not text:
            return utcnow()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return utcnow()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _comparable_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _has_rejection_signal(text: str) -> bool:
    return any(
        token in text
        for token in (
            "pursue other candidates",
            "not moving forward",
            "will not be moving forward",
            "not selected",
            "no longer under consideration",
            "unfortunately",
            "decided to pursue",
        )
    )


def _has_identity_or_task_signal(text: str) -> bool:
    return any(
        token in text
        for token in (
            "confirm your identity",
            "verify your identity",
            "one-time pass code",
            "one time pass code",
            "must confirm",
            "action required",
            "complete setup",
            "assessment",
        )
    )


def _has_interview_signal(text: str) -> bool:
    return any(
        token in text
        for token in (
            "schedule an interview",
            "interview availability",
            "invited to interview",
            "next interview",
            "recruiter screen",
            "phone screen",
        )
    )


def _has_application_received_signal(text: str) -> bool:
    return any(
        token in text
        for token in (
            "thank you for applying",
            "thanks for your interest",
            "received your application",
            "we received your job application",
            "application has been received",
        )
    )


def _split_requisition(value: str) -> tuple[str, str]:
    match = re.search(r"(.+?)\s+[—-]\s+([A-Z]?\d{6,10})\b", value)
    if not match:
        return _normalize_space(value), ""
    return _normalize_space(match.group(1)), match.group(2).strip()


def _title_from_subject(text: str) -> str:
    first_sentence = text.split(".", 1)[0]
    for prefix in (
        "An update about your application for",
        "Your recent job application for",
        "Confirm your identity for job",
    ):
        if first_sentence.lower().startswith(prefix.lower()):
            return _normalize_space(first_sentence[len(prefix) :])
    return "Application Status Update"


def _first_action_url(value: str) -> str:
    for candidate in re.findall(r"https?://[^\s)\]>]+", value or ""):
        url = candidate.rstrip(".,")
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.netloc.lower().startswith("mail.google.com"):
            return url
    return ""


def _redact_sensitive_codes(value: str) -> str:
    redacted = re.sub(
        r"(?i)((?:one[- ]?time\s+)?(?:pass\s*)?code\s*:?\s*)\d{4,8}",
        r"\1[redacted code]",
        value or "",
    )
    redacted = re.sub(r"(?i)(using the one-time pass code\s*:?\s*)\d{4,8}", r"\1[redacted code]", redacted)
    return redacted


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _text(value: object) -> str:
    return str(value or "").strip()
