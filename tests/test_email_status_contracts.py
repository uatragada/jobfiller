from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.backend.database import Base
from app.backend.models import ApplicationEvent, Job
from app.backend.services.email_status_sync import classify_application_email, sync_application_emails
from app.backend.services.gmail_importer import parse_gmail_alerts


def make_db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_application_status_sync_does_not_downgrade_newer_rejection_with_older_status() -> None:
    db = make_db()
    rejected = {
        "id": "example-media-newer-rejection",
        "thread_id": "example-media-thread",
        "from": "Example Media Workday <no-reply@example-media.test>",
        "subject": "An update about your application for Data Platform Engineer - R000105204",
        "body": (
            "Thank you for your time in applying for the Data Platform Engineer - R000105204 "
            "position at Example Media. We have decided to pursue other candidates at this time."
        ),
        "email_ts": "2026-06-20T12:00:00+00:00",
    }
    older_received = {
        "id": "example-media-older-received",
        "thread_id": "example-media-thread",
        "from": "Example Media Workday <no-reply@example-media.test>",
        "subject": "An update about your application for Data Platform Engineer - R000105204",
        "body": "Thank you for applying. We received your application.",
        "email_ts": "2026-06-19T12:00:00+00:00",
    }

    sync_application_emails(db, [rejected])
    db.commit()
    sync_application_emails(db, [older_received])
    db.commit()

    job = db.scalars(select(Job).where(Job.company == "Example Media")).one()
    events = db.scalars(select(ApplicationEvent).where(ApplicationEvent.job_id == job.id)).all()
    assert job.application_state == "REJECTED"
    assert "closed" in job.follow_up_action.lower()
    assert {event.state for event in events} == {"REJECTED", "APPLIED"}


def test_application_status_sync_ignores_private_action_urls() -> None:
    db = make_db()
    result = sync_application_emails(
        db,
        [
            {
                "id": "private-action-url",
                "thread_id": "private-action-thread",
                "from": "Example Careers careers@example.com",
                "subject": "Action required for Backend Engineer",
                "body": (
                    "Action required: complete setup for Backend Engineer. "
                    "Use http://127.0.0.1:8000/private-candidate-portal to continue."
                ),
                "email_ts": "2026-06-21T12:00:00+00:00",
                "display_url": "http://169.254.169.254/latest/meta-data",
            }
        ],
    )
    db.commit()

    assert result["states"] == {"ACTION_NEEDED": 1}
    event = db.scalars(select(ApplicationEvent)).one()
    job = db.get(Job, event.job_id)
    assert event.action_url == ""
    assert event.evidence_url == ""
    assert "action_url ignored" in event.body_excerpt
    assert "evidence_url ignored" in event.body_excerpt
    assert "unsafe URL removed" in event.body_excerpt
    assert "127.0.0.1" not in event.body_excerpt
    assert "169.254.169.254" not in event.body_excerpt
    assert "127.0.0.1" not in job.apply_url
    assert job.application_state == "ACTION_NEEDED"
    assert job.last_status_email_url == ""


@pytest.mark.parametrize(
    ("newer_subject", "newer_body", "expected_state"),
    [
        (
            "Backend Engineer interview availability",
            "You are invited to interview. Please share interview availability for a recruiter screen.",
            "INTERVIEW",
        ),
        (
            "Action required for Backend Engineer",
            "Action required: complete setup for Backend Engineer before the next hiring step.",
            "ACTION_NEEDED",
        ),
    ],
)
def test_application_status_sync_keeps_older_rejection_as_history_after_newer_active_state(
    newer_subject: str,
    newer_body: str,
    expected_state: str,
) -> None:
    db = make_db()
    newer_active = {
        "id": f"example-newer-{expected_state.lower()}",
        "thread_id": "example-thread",
        "from": "ExampleCo Careers <careers@example.com>",
        "subject": newer_subject,
        "body": newer_body,
        "email_ts": "2026-06-22T12:00:00+00:00",
        "display_url": "https://mail.example.test/messages/newer-active",
    }
    older_rejection = {
        "id": f"example-older-rejected-{expected_state.lower()}",
        "thread_id": "example-thread",
        "from": "ExampleCo Careers <careers@example.com>",
        "subject": "An update about your Backend Engineer application",
        "body": "Unfortunately, we are not moving forward with your Backend Engineer application.",
        "email_ts": "2026-06-21T12:00:00+00:00",
        "display_url": "https://mail.example.test/messages/older-rejected",
    }

    sync_application_emails(db, [newer_active])
    db.commit()
    sync_application_emails(db, [older_rejection])
    db.commit()

    job = db.scalars(select(Job).where(Job.company == "ExampleCo")).one()
    events = db.scalars(select(ApplicationEvent).where(ApplicationEvent.job_id == job.id)).all()

    assert job.application_state == expected_state
    assert job.last_status_email_subject == newer_subject
    assert job.last_status_email_url == "https://mail.example.test/messages/newer-active"
    assert {event.state for event in events} == {expected_state, "REJECTED"}


def test_classify_application_email_detects_interview_and_application_received_states() -> None:
    interview = classify_application_email(
        {
            "from": "Recruiting Team careers@example.com",
            "subject": "Backend Engineer interview availability",
            "body": "You are invited to interview. Please share interview availability for a recruiter screen.",
        }
    )
    received = classify_application_email(
        {
            "from": "Recruiting Team careers@example.com",
            "subject": "Thanks for applying to Backend Engineer",
            "body": "We received your application and will review it soon.",
        }
    )

    assert interview.state == "INTERVIEW"
    assert "schedule" in interview.follow_up_action.lower() or "confirm" in interview.follow_up_action.lower()
    assert received.state == "APPLIED"
    assert "monitor" in received.follow_up_action.lower()


def test_parse_gmail_alerts_deduplicates_tracking_variants_of_same_linkedin_job() -> None:
    records = parse_gmail_alerts(
        [
            {
                "id": "linkedin-dedupe",
                "from_": "LinkedIn Job Alerts jobalerts-noreply@linkedin.com",
                "subject": "Backend jobs near you",
                "body": """
                [ExampleCo](https://www.linkedin.com/comm/jobs/view/4432033376/?trackingId=abc)
                [Backend Engineer
                ExampleCo · Raleigh, NC (Hybrid)](https://www.linkedin.com/comm/jobs/view/4432033376/?trackingId=abc)

                [ExampleCo](https://www.linkedin.com/jobs/view/4432033376/?trackingId=def)
                [Backend Engineer
                ExampleCo · Raleigh, NC (Hybrid)](https://www.linkedin.com/jobs/view/4432033376/?trackingId=def)
                """,
            }
        ]
    )

    assert len(records) == 1
    assert records[0]["company"] == "ExampleCo"
    assert records[0]["title"] == "Backend Engineer"
    assert records[0]["work_model"] == "Hybrid"
