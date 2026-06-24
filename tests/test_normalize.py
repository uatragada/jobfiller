from __future__ import annotations

from app.backend.services.normalize import canonicalize_url


def test_linkedin_job_url_dedupes_tracking_variants() -> None:
    a = "https://www.linkedin.com/jobs/view/software-engineer-at-acme-1234567890/?trackingId=abc"
    b = "https://www.linkedin.com/jobs/view/1234567890"

    assert canonicalize_url(a) == canonicalize_url(b)


def test_linkedin_search_urls_keep_query_identity() -> None:
    a = "https://www.linkedin.com/jobs/search/?keywords=Dario%20Software%20Developer"
    b = "https://www.linkedin.com/jobs/search/?keywords=McKinsey%20FinLab"

    assert canonicalize_url(a) != canonicalize_url(b)
