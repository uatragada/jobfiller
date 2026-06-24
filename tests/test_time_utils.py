from __future__ import annotations

from datetime import datetime, timezone

from app.backend.services.time_utils import newest_sort_key, parse_posting_age


def test_parse_posting_age_hours_days_weeks() -> None:
    now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)

    assert parse_posting_age("2 hours ago", now).hour == 10
    assert parse_posting_age("1 day ago", now).day == 22
    assert parse_posting_age("3 weeks ago", now).day == 2


def test_parse_posting_age_range() -> None:
    now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)

    assert parse_posting_age("1-2 weeks ago", now).day == 16
    assert parse_posting_age("2-3 days ago", now).day == 21


def test_unknown_dates_sort_below_known_new_postings() -> None:
    now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)
    two_hours = parse_posting_age("2 hours ago", now)
    one_day = parse_posting_age("1 day ago", now)
    unknown = None

    rows = [
        ("unknown", newest_sort_key(unknown, now, 99)),
        ("one_day", newest_sort_key(one_day, now, 90)),
        ("two_hours", newest_sort_key(two_hours, now, 80)),
    ]
    assert [name for name, _ in sorted(rows, key=lambda row: row[1], reverse=True)] == [
        "two_hours",
        "one_day",
        "unknown",
    ]
