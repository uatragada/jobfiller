from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from app.backend.database import Base, get_db
from app.backend.main import app
from app.backend.services.gmail_importer import parse_gmail_alert_email, score_job_against_profile


PROFILE = {
    "summary": "Computer Science graduate with an Economics minor focused on backend services, APIs, AI products, and data validation.",
    "skills": ["Python", "FastAPI", "REST APIs", "Backend Services", "Data Pipelines", "React", "TypeScript", "Java", "SQL"],
    "education": [{"degree": "BSc Computer Science, Minor in Economics"}],
    "experience": [{"company": "WEX", "title": "Enterprise Engineering Co-Op Intern"}],
    "projects": [{"name": "Varelio", "description": "FastAPI document extraction pipeline"}],
}

SCAN = {
    "default_location": "Raleigh, NC",
    "preferred_locations": "Raleigh, NC; Durham, NC; Cary, NC; Remote tied to Research Triangle",
}


@pytest.fixture()
def client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, future=True)

    def override_get_db():
        with TestingSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    token = test_client.get("/api/session").json()["mutation_token"]
    test_client.headers.update({"X-JobFiller-Token": token})
    yield test_client
    app.dependency_overrides.clear()


def test_linkedin_digest_importer_extracts_jobs() -> None:
    message = {
        "id": "gmail-1",
        "from_": "LinkedIn Job Alerts jobalerts-noreply@linkedin.com",
        "subject": "Applied AI Software Engineer at Blossom",
        "email_ts": "2026-06-24T13:15:17",
        "body": """
        [Blossom](https://www.linkedin.com/comm/jobs/view/4432033376/?trackingId=abc)
        [Applied AI Software Engineer (All Levels)
        Blossom · Raleigh, NC (On-site)
        $150K-$220K / year](https://www.linkedin.com/comm/jobs/view/4432033376/?trackingId=abc)

        [Wealthfront](https://www.linkedin.com/comm/jobs/view/4296094481/?trackingId=def)
        [Backend Engineer
        Wealthfront · Raleigh, NC (Hybrid)
        Actively recruiting Easy Apply](https://www.linkedin.com/comm/jobs/view/4296094481/?trackingId=def)
        """,
    }

    jobs = parse_gmail_alert_email(message)

    assert [(job.company, job.title) for job in jobs] == [
        ("Blossom", "Applied AI Software Engineer (All Levels)"),
        ("Wealthfront", "Backend Engineer"),
    ]
    assert jobs[0].location == "Raleigh, NC"
    assert jobs[0].work_model == "On-site"
    assert jobs[0].salary == "$150K-$220K / year"
    assert "finance" not in jobs[0].manual_questions.lower()


def test_indeed_importer_scores_and_questions_examplegov() -> None:
    message = {
        "id": "gmail-examplegov",
        "from_": "Indeed donotreply@match.indeed.com",
        "subject": "Entry Level Software Engineer @ ExampleGov",
        "body": """
        [View job](https://cts.indeed.com/v3/examplegov)
        ExampleGov
        Remote
        Salary
        $102,000 - $197,000 a year
        Job description
        Familiarity with at least one programming language (Java strongly preferred). U.S. citizenship required due to client eligibility requirements, including the ability to obtain and maintain a public trust clearance. Exposure to modern web technologies such as Java, Spring Boot, JavaScript, React, or similar frameworks. Basic understanding of full stack development concepts.
        """,
    }

    jobs = parse_gmail_alert_email(message)

    assert len(jobs) == 1
    assert jobs[0].company == "ExampleGov"
    assert jobs[0].work_model == "Remote"
    assert jobs[0].fit_score >= 80
    assert "citizenship" in jobs[0].manual_questions.lower()
    assert "Public Trust" in jobs[0].key_requirements


def test_ladders_and_glassdoor_formats_parse() -> None:
    ladders = parse_gmail_alert_email(
        {
            "from_": "Ladders jobs@my.theladders.com",
            "subject": "GC AI Offering Over $100K for Software Engineer, Product job",
            "body": """
            [Remote
            Software Engineer, Product
            $90K - $130K*
            GC AI | Virtual / Travel](https://t.ladders.co/f/a/one)
            """,
        }
    )
    glassdoor = parse_gmail_alert_email(
        {
            "from_": "Glassdoor Jobs noreply@glassdoor.com",
            "subject": "Staff Software Engineer - AI Trainer role at DataAnnotation",
            "body": """
            [DataAnnotation
            Staff Software Engineer - AI Trainer
            Yonkers, NY
            $50 - $100
            Easy Apply](https://www.glassdoor.com/partner/jobListing.htm?jobListingId=1010165571802)
            """,
        }
    )

    assert ladders[0].company == "GC AI"
    assert ladders[0].work_model == "Remote"
    assert glassdoor[0].company == "DataAnnotation"
    assert glassdoor[0].title == "Staff Software Engineer - AI Trainer"
    assert "seniority" in glassdoor[0].manual_questions.lower()


def test_profile_scoring_prefers_backend_over_unrelated_roles() -> None:
    backend_score = score_job_against_profile(
        {
            "title": "Backend Engineer",
            "location": "Raleigh, NC",
            "work_model": "Hybrid",
            "key_requirements": "Python; FastAPI; APIs; SQL",
            "keywords": "backend; platform; data pipelines",
        },
        PROFILE,
        SCAN,
    )
    civil_score = score_job_against_profile(
        {
            "title": "Civil Engineering Project Manager",
            "location": "Saco, ME",
            "work_model": "On-site",
            "key_requirements": "civil engineering; construction management",
            "keywords": "civil engineering",
        },
        PROFILE,
        SCAN,
    )

    assert backend_score > civil_score + 25


def test_gmail_alert_endpoint_imports_and_creates_questions(client: TestClient) -> None:
    response = client.post(
        "/api/imports/gmail-alerts",
        json={
            "source": "gmail-alert-test",
            "process": True,
            "emails": [
                {
                    "id": "gmail-examplegov",
                    "from_": "Indeed donotreply@match.indeed.com",
                    "subject": "Entry Level Software Engineer @ ExampleGov",
                    "body": """
                    [View job](https://cts.indeed.com/v3/examplegov-endpoint)
                    ExampleGov
                    Remote
                    Salary
                    $102,000 - $197,000 a year
                    Job description
                    U.S. citizenship required due to client eligibility requirements, including public trust clearance. Java, Python, JavaScript, React, and full stack development.
                    """,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"] == 1
    assert payload["imported"] == 1
    assert payload["jobs"][0]["company"] == "ExampleGov"
    assert payload["jobs"][0]["open_questions"] >= 1

    questions = client.get("/api/questions?status=OPEN").json()
    assert any(question["tag"] == "work_authorization_clearance" for question in questions)
