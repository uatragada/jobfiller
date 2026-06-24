from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone


AGE_RE = re.compile(
    r"(?P<low>\d+)\s*(?:[-–]\s*(?P<high>\d+))?\s*(?P<unit>minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)",
    re.I,
)

REMOTE_PATTERNS = ("remote", "remote est", "remote -", "remote/global", "work from home", "wfh")
HYBRID_PATTERNS = ("hybrid",)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_posting_age(age_text: str | None, now: datetime | None = None) -> datetime | None:
    if not age_text:
        return None
    text = age_text.strip().lower()
    now = now or utcnow()
    if text in {"today", "just posted", "new", "active linkedin page"}:
        return now
    if "yesterday" in text:
        return now - timedelta(days=1)
    match = AGE_RE.search(text)
    if not match:
        return None
    amount = int(match.group("low"))
    unit = match.group("unit")
    if unit.startswith("minute"):
        return now - timedelta(minutes=amount)
    if unit.startswith("hour"):
        return now - timedelta(hours=amount)
    if unit.startswith("day"):
        return now - timedelta(days=amount)
    if unit.startswith("week"):
        return now - timedelta(weeks=amount)
    if unit.startswith("month"):
        return now - timedelta(days=amount * 30)
    if unit.startswith("year"):
        return now - timedelta(days=amount * 365)
    return None


def newest_sort_key(posted_at: datetime | None, first_seen_at: datetime, fit_score: int) -> tuple[int, datetime, datetime, int]:
    has_posted = 1 if posted_at else 0
    return (has_posted, posted_at or datetime.min.replace(tzinfo=timezone.utc), first_seen_at, fit_score)


def remote_rank(text: str | None) -> int:
    if not text:
        return 0
    normalized = text.lower()
    if any(token in normalized for token in REMOTE_PATTERNS):
        return 2
    if any(token in normalized for token in HYBRID_PATTERNS):
        return 1
    return 0


def scan_sort_key(
    posted_at: datetime | None,
    first_seen_at: datetime,
    fit_score: int,
    *,
    remote_first: bool = True,
    location: str = "",
    work_model: str = "",
) -> tuple[int, int, datetime, datetime, int]:
    has_posted = 1 if posted_at else 0
    remote_score = remote_rank(f"{location} {work_model}") if remote_first else 0
    return (
        has_posted,
        remote_score,
        posted_at or datetime.min.replace(tzinfo=timezone.utc),
        first_seen_at,
        fit_score,
    )
