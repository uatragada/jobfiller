from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.database import Base, get_db
from app.backend.main import app
from app.backend.models import ApplicationEvent, Artifact, Grade, Job, Question


@pytest.fixture()
def isolated_client():
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
    client = TestClient(app)
    token = client.get("/api/session").json()["mutation_token"]
    client.headers.update({"X-JobFiller-Token": token})
    yield client, TestingSessionLocal
    app.dependency_overrides.clear()


def test_api_read_routes_require_token_while_public_routes_remain_open(isolated_client) -> None:
    anonymous = TestClient(app)

    assert anonymous.get("/api/health").status_code == 200
    assert anonymous.get("/api/session").status_code == 200
    assert anonymous.get("/api/jobs").status_code == 403
    assert anonymous.get("/api/model-health").status_code == 403
    assert anonymous.get("/api/export/latest.json").status_code != 403


def test_bulk_import_keeps_valid_rows_and_reports_unsafe_row_errors(isolated_client) -> None:
    client, _session_factory = isolated_client

    response = client.post(
        "/api/imports/bulk",
        json={
            "source": "agent-regression",
            "jobs": [
                {
                    "url": "https://example.com/jobs/bulk-valid-backend",
                    "company": "ValidBulkCo",
                    "title": "Backend Engineer",
                    "key_requirements": "Python; APIs; testing",
                    "keywords": "backend; api",
                },
                {
                    "url": "http://127.0.0.1:8000/private-job",
                    "company": "UnsafeBulkCo",
                    "title": "Private Job",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["imported"] == 1
    assert payload["errors"][0]["index"] == 1
    assert "unsafe" in payload["errors"][0]["error"].lower()
    jobs = client.get("/api/jobs").json()
    assert any(job["company"] == "ValidBulkCo" for job in jobs)
    assert not any(job["company"] == "UnsafeBulkCo" for job in jobs)


def test_delete_job_cascades_questions_artifacts_grades_and_application_events(isolated_client, tmp_path: Path) -> None:
    client, SessionLocal = isolated_client
    resume = tmp_path / "resume.pdf"
    resume.write_text("%PDF-1.4 test", encoding="utf-8")
    cover = tmp_path / "cover.docx"
    cover.write_text("cover", encoding="utf-8")
    tex = tmp_path / "main.tex"
    tex.write_text("resume tex", encoding="utf-8")

    with SessionLocal() as db:
        job = Job(
            source_url="https://example.com/jobs/delete-cascade",
            canonical_url="https://example.com/jobs/delete-cascade",
            apply_url="https://example.com/apply/delete-cascade",
            company="CascadeCo",
            title="Backend Engineer",
            status="QA",
        )
        db.add(job)
        db.flush()
        db.add_all(
            [
                Question(job_id=job.id, tag="cascade", question_text="Cascade question?", blocking=True),
                Artifact(
                    job_id=job.id,
                    revision=1,
                    resume_pdf_path=str(resume),
                    resume_tex_path=str(tex),
                    cover_letter_path=str(cover),
                    compile_status="compiled",
                ),
                Grade(job_id=job.id, artifact_id=None, model="test", overall_grade="A", ready_to_send=True),
                ApplicationEvent(
                    job_id=job.id,
                    source="gmail",
                    external_id="cascade-message",
                    subject="Application status",
                    state="APPLIED",
                ),
            ]
        )
        db.commit()
        job_id = job.id

    deleted = client.delete(f"/api/jobs/{job_id}")
    assert deleted.status_code == 200

    with SessionLocal() as db:
        assert db.get(Job, job_id) is None
        assert db.scalars(select(Question).where(Question.job_id == job_id)).all() == []
        assert db.scalars(select(Artifact).where(Artifact.job_id == job_id)).all() == []
        assert db.scalars(select(Grade).where(Grade.job_id == job_id)).all() == []
        assert db.scalars(select(ApplicationEvent).where(ApplicationEvent.job_id == job_id)).all() == []


def test_application_events_blank_unsafe_stored_urls(isolated_client) -> None:
    client, SessionLocal = isolated_client
    with SessionLocal() as db:
        job = Job(
            source_url="https://example.com/jobs/stored-event-url",
            canonical_url="https://example.com/jobs/stored-event-url",
            company="StoredUrlCo",
            title="Backend Engineer",
        )
        db.add(job)
        db.flush()
        db.add(
            ApplicationEvent(
                job_id=job.id,
                source="email",
                external_id="stored-unsafe-url",
                subject="Action required",
                state="ACTION_NEEDED",
                action_url="http://127.0.0.1:8000/private-candidate-portal",
                evidence_url="http://localhost:5173/mail/private-message",
            )
        )
        db.commit()

    response = client.get("/api/application-events?limit=10")

    assert response.status_code == 200
    event = next(item for item in response.json() if item["external_id"] == "stored-unsafe-url")
    assert event["action_url"] == ""
    assert event["evidence_url"] == ""


def test_artifact_routes_return_clear_errors_for_missing_or_unsupported_files(isolated_client, tmp_path: Path) -> None:
    client, SessionLocal = isolated_client
    resume = tmp_path / "resume.pdf"
    resume.write_text("%PDF-1.4 test", encoding="utf-8")
    tex = tmp_path / "main.tex"
    tex.write_text("resume tex", encoding="utf-8")

    with SessionLocal() as db:
        job = Job(
            source_url="https://example.com/jobs/artifact-errors",
            canonical_url="https://example.com/jobs/artifact-errors",
            company="ArtifactErrorCo",
            title="Backend Engineer",
        )
        db.add(job)
        db.flush()
        artifact = Artifact(
            job_id=job.id,
            revision=1,
            resume_pdf_path=str(resume),
            resume_tex_path=str(tex),
            cover_letter_path=str(tmp_path / "missing-cover.docx"),
            compile_status="compiled",
        )
        db.add(artifact)
        db.commit()
        artifact_id = artifact.id

    unsupported = client.get(f"/api/artifacts/{artifact_id}/download?kind=portfolio")
    missing_cover = client.get(f"/api/artifacts/{artifact_id}/cover-letter")

    assert unsupported.status_code == 404
    assert "kind" in unsupported.text.lower()
    assert missing_cover.status_code == 404
    assert "missing" in missing_cover.text.lower()


def test_assist_upload_rejects_unsupported_kind_before_launching_helper(isolated_client, tmp_path: Path) -> None:
    client, SessionLocal = isolated_client
    resume = tmp_path / "resume.pdf"
    resume.write_text("%PDF-1.4 test", encoding="utf-8")
    cover = tmp_path / "cover.docx"
    cover.write_text("cover", encoding="utf-8")

    with SessionLocal() as db:
        job = Job(
            source_url="https://example.com/jobs/assist-kind",
            canonical_url="https://example.com/jobs/assist-kind",
            company="AssistKindCo",
            title="Backend Engineer",
        )
        db.add(job)
        db.flush()
        db.add(
            Artifact(
                job_id=job.id,
                revision=1,
                resume_pdf_path=str(resume),
                resume_tex_path="",
                cover_letter_path=str(cover),
                compile_status="compiled",
            )
        )
        db.commit()
        job_id = job.id

    response = client.post(f"/api/jobs/{job_id}/assist-upload?kind=portfolio&confirm=review-before-submit")

    assert response.status_code == 422
    assert "resume or cover-letter" in response.text
