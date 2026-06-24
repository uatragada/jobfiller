from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.backend.database import Base
from app.backend.models import Job, ProfileFact, Question
from app.backend.services.ingestion import upsert_job
from app.backend.services.ingestion import import_chrome_job_tabs, run_scan
from app.backend.services.missing_info import ensure_questions
from app.backend.services.processor import answer_question, apply_fact_to_tagged_open_questions, process_job, grade_artifact
from app.backend.services.artifacts import generate_artifacts, update_artifact_text
from app.backend.models import Run
from pathlib import Path
from app.backend.services.local_llm import extract_pdf_text


def make_db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def make_non_autoflush_db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, future=True)()


def test_missing_info_blocks_without_inventing_claims() -> None:
    db = make_db()
    job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/111",
            "company": "Capgemini",
            "title": "Software Engineer C++ Python",
            "key_requirements": "C++; Python; enterprise delivery",
            "keywords": "C++; Python",
        },
    )
    questions = ensure_questions(db, job)

    assert questions
    assert questions[0].tag == "cpp"


def test_answer_question_creates_reusable_profile_fact() -> None:
    db = make_db()
    job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/222",
            "company": "Dario",
            "title": "Associate Software Developer",
            "key_requirements": "healthcare; software development",
            "keywords": "health tech; Python",
        },
    )
    question = ensure_questions(db, job)[0]
    answer_question(db, question, "No direct HIPAA experience, but I can reference data validation and privacy-conscious workflows.")

    fact = db.scalars(select(ProfileFact).where(ProfileFact.tag == question.tag)).first()
    updated_question = db.get(Question, question.id)
    assert fact is not None
    assert "privacy" in fact.answer
    assert updated_question.status == "ANSWERED"


def test_answer_question_with_non_autoflush_session_does_not_duplicate_profile_fact() -> None:
    db = make_non_autoflush_db()
    job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/non-autoflush-answer",
            "company": "SyntheticCo",
            "title": "Backend Engineer",
            "key_requirements": "Python; APIs; testing",
            "keywords": "backend; api",
        },
    )
    question = Question(
        job_id=job.id,
        tag="synthetic_non_autoflush",
        question_text="Synthetic non-autoflush question.",
        blocking=True,
        status="OPEN",
    )
    db.add(question)
    db.flush()

    answer_question(db, question, "Synthetic answer.")
    db.commit()

    facts = list(db.scalars(select(ProfileFact).where(ProfileFact.tag == "synthetic_non_autoflush")).all())
    assert len(facts) == 1
    assert question.status == "ANSWERED"


def test_answer_question_reprocesses_each_affected_job_once(monkeypatch) -> None:
    db = make_db()
    first_job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/reprocess-once-a",
            "company": "FirstCo",
            "title": "Backend Engineer",
            "key_requirements": "finance; backend",
            "keywords": "finance; backend",
        },
    )
    second_job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/reprocess-once-b",
            "company": "SecondCo",
            "title": "Backend Engineer",
            "key_requirements": "finance; backend",
            "keywords": "finance; backend",
        },
    )
    first_question = Question(
        job_id=first_job.id,
        tag="synthetic_reprocess_once",
        question_text="Synthetic shared fact question.",
        blocking=True,
        status="OPEN",
    )
    second_question = Question(
        job_id=second_job.id,
        tag="synthetic_reprocess_once",
        question_text="Synthetic shared fact question.",
        blocking=True,
        status="OPEN",
    )
    db.add_all([first_question, second_question])
    db.flush()

    calls: list[int] = []

    def spy_process_job(db_session, job, *, force: bool = False):  # noqa: ANN001
        calls.append(job.id)
        job.status = "READY"
        return job

    monkeypatch.setattr("app.backend.services.processor.process_job", spy_process_job)

    affected = answer_question(db, first_question, "Synthetic answer.")

    assert sorted(job.id for job in affected) == sorted([first_job.id, second_job.id])
    assert sorted(calls) == sorted([first_job.id, second_job.id])
    assert len(calls) == 2
    assert second_question.status == "ANSWERED"


def test_applying_profile_fact_reprocesses_blocked_jobs() -> None:
    db = make_db()
    job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/777",
            "company": "Jefferies",
            "title": "Associate Software Developer",
            "key_requirements": "finance; fixed income; platform ownership",
            "keywords": "finance; backend",
        },
    )
    process_job(db, job)
    assert job.status == "NEEDS_INFO"
    assert any(question.tag == "finance_motivation" for question in job.questions)

    answered_jobs = apply_fact_to_tagged_open_questions(
        db,
        "finance_motivation",
        "I am motivated by systems reliability in finance because I can combine software engineering with data integrity and measurable impact.",
        "Finance motivation",
    )
    db.flush()

    assert answered_jobs
    finance_questions = list(db.scalars(select(Question).where(Question.job_id == job.id, Question.tag == "finance_motivation")).all())
    assert finance_questions and all(question.status != "OPEN" for question in finance_questions)
    assert job.status in {"NEEDS_INFO", "QA", "READY"}


def test_generic_real_users_phrase_does_not_create_metrics_blocker() -> None:
    db = make_db()
    job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/333",
            "company": "SkillStorm",
            "title": "Entry Level Software Developer",
            "key_requirements": "entry level; software developer; application development",
            "keywords": "Python; Java; JavaScript; testing",
            "raw_text": "Build software for real users and client delivery.",
        },
    )

    assert ensure_questions(db, job) == []


def test_generic_repository_phrase_does_not_create_finance_blocker() -> None:
    db = make_db()
    job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/334",
            "company": "ExampleCo",
            "title": "Software Engineer",
            "key_requirements": "Maintain application repositories and API integrations",
            "keywords": "GitHub; backend; APIs",
            "raw_text": "Own code repositories, pull requests, and release automation.",
        },
    )

    assert all(question.tag != "finance_motivation" for question in ensure_questions(db, job))


def test_run_scan_updates_run_metadata() -> None:
    db = make_db()
    run = Run(kind="manual_scan", status="RUNNING", message="manual scan start")
    db.add(run)
    db.flush()

    imported, message = run_scan(db, run, remote_first=True, source="seed", limit=3)

    assert imported > 0
    assert imported <= 3
    assert run.status == "SUCCEEDED"
    assert run.finished_at is not None
    assert "remote-first" in message


def test_scan_request_can_use_keywords_filtering() -> None:
    db = make_db()
    run = Run(kind="manual_scan", status="RUNNING", message="manual scan start")
    db.add(run)
    db.flush()

    imported, message = run_scan(
        db,
        run,
        remote_first=True,
        source="seed",
        scanner_keywords="backend, fastapi",
        limit=2,
    )

    assert imported <= 2
    assert "newest-first" in message


def test_run_scan_filters_by_scanner_keywords() -> None:
    db = make_db()
    run = Run(kind="manual_scan", status="RUNNING", message="manual scan start")
    db.add(run)
    db.flush()

    imported, message = run_scan(
        db,
        run,
        remote_first=True,
        source="seed",
        limit=25,
        scanner_keywords="trading, finance",
    )

    assert imported > 0
    assert "seeded/current" in message


def test_chrome_scan_imports_common_ats_job_tabs(monkeypatch) -> None:
    db = make_db()
    monkeypatch.setattr(
        "app.backend.services.ingestion.chrome_debug_tabs",
        lambda: [
            {
                "url": "https://boards.greenhouse.io/example/jobs/1234567",
                "title": "Backend Engineer - Example Systems - Remote",
            },
            {
                "url": "https://jobs.lever.co/acme/abc123",
                "title": "Data Analyst | Acme Analytics | Hybrid",
            },
            {
                "url": "https://example.com/blog/not-a-job",
                "title": "Company Blog",
            },
        ],
    )

    jobs = import_chrome_job_tabs(db, remote_first=True)

    assert len(jobs) == 2
    assert {job.source for job in jobs} == {"chrome"}
    assert {job.company for job in jobs} == {"Example Systems", "Acme Analytics"}
    assert any(job.work_model == "Remote" for job in jobs)


def test_artifact_paths_follow_output_contract(monkeypatch) -> None:
    monkeypatch.setattr("app.backend.services.artifacts.candidate_slug", lambda: "candidate")
    db = make_db()
    job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/555",
            "company": "SeatGeek",
            "title": "Software Engineer I",
            "key_requirements": "backend; APIs; testing",
            "keywords": "Python; FastAPI",
        },
    )
    artifact = generate_artifacts(db, job)

    assert artifact.resume_tex_path == str((Path("outputs") / "resumes" / f"seatgeek-software-engineer-i-job-{job.id:04d}" / "main.tex").resolve())
    assert artifact.resume_pdf_path == str((Path("outputs") / "resumes" / f"candidate-resume-seatgeek-software-engineer-i-job-{job.id:04d}.pdf").resolve())
    assert artifact.cover_letter_path == str(
        (Path("outputs") / "cover_letters" / f"candidate-cover-letter-seatgeek-software-engineer-i-job-{job.id:04d}.md").resolve()
    )
    assert Path(artifact.resume_tex_path).exists()
    assert Path(artifact.resume_pdf_path).exists()
    assert Path(artifact.cover_letter_path).exists()


def test_same_company_jobs_do_not_share_latest_artifact_paths(monkeypatch) -> None:
    monkeypatch.setattr("app.backend.services.artifacts.candidate_slug", lambda: "candidate")
    db = make_db()
    first_job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/same-company-a",
            "company": "ExampleCo",
            "title": "Backend Engineer",
            "key_requirements": "Python; APIs",
            "keywords": "Python; backend",
        },
    )
    second_job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/same-company-b",
            "company": "ExampleCo",
            "title": "Platform Engineer",
            "key_requirements": "Infrastructure; APIs",
            "keywords": "platform; backend",
        },
    )

    first_artifact = generate_artifacts(db, first_job)
    second_artifact = generate_artifacts(db, second_job)

    assert first_artifact.resume_pdf_path != second_artifact.resume_pdf_path
    assert first_artifact.cover_letter_path != second_artifact.cover_letter_path
    assert f"job-{first_job.id:04d}" in first_artifact.resume_pdf_path
    assert f"job-{second_job.id:04d}" in second_artifact.resume_pdf_path


def test_artifact_revisions_preserve_working_paths() -> None:
    db = make_db()
    job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/556",
            "company": "SeatGeek",
            "title": "Software Engineer I",
            "key_requirements": "backend; APIs; testing",
            "keywords": "Python; FastAPI",
        },
    )
    first = generate_artifacts(db, job)
    second = update_artifact_text(db, first, "cover-letter", "Manual cover letter adjustment.")

    assert second.revision == first.revision + 1
    assert second.resume_tex_path == first.resume_tex_path
    assert second.cover_letter_path == first.cover_letter_path
    assert Path(second.cover_letter_path).exists()


def test_grade_artifact_handles_missing_pdf() -> None:
    db = make_db()
    job = upsert_job(
        db,
        {
            "url": "https://www.linkedin.com/jobs/view/777",
            "company": "SeatGeek",
            "title": "Software Engineer I",
            "key_requirements": "backend; APIs; testing",
            "keywords": "Python; FastAPI",
        },
    )
    artifact = generate_artifacts(db, job)
    artifact.resume_pdf_path = ""

    grade = grade_artifact(db, artifact)

    assert grade is not None
    assert grade.overall_grade == "ERROR"
    assert "resume PDF is missing" in grade.raw_json


def test_extract_pdf_text_fails_open_gracefully() -> None:
    text, pages = extract_pdf_text("definitely-does-not-exist.pdf")
    assert pages == 0
    assert text
    assert "failed" in text.lower() or "unavailable" in text.lower()
