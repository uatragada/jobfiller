from __future__ import annotations

from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.backend.database import Base, get_db
from app.backend.main import app
from app.backend import __version__


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db():
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
    token = client.get("/api/session").json()["mutation_token"]
    client.headers.update({"X-JobFiller-Token": token})
    yield
    client.headers.pop("X-JobFiller-Token", None)
    app.dependency_overrides.clear()


def test_import_rejects_malformed_url() -> None:
    response = client.post("/api/jobs/import", json={"url": "not a url"})

    assert response.status_code == 422
    assert "valid URL" in response.text


def test_health_advertises_required_answer_fix_capability() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == __version__
    assert payload["capabilities"]["question_answer_autoflush_fix"] is True


def test_import_rejects_unsafe_local_or_credentialed_urls() -> None:
    unsafe_urls = [
        "http://127.0.0.1:8000/internal-job",
        "http://localhost/jobs/1",
        "http://169.254.169.254/latest/meta-data",
        "https://user:password@example.com/jobs/secret",
        "file:///C:/Users/Candidate/private-job.html",
    ]

    for unsafe_url in unsafe_urls:
        response = client.post("/api/jobs/import", json={"url": unsafe_url})
        assert response.status_code == 422, unsafe_url
        assert "unsafe" in response.text.lower() or "valid URL" in response.text


def test_import_rejects_unsafe_apply_url() -> None:
    response = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/safe-source",
            "apply_url": "javascript:alert(1)",
            "company": "ApplySafe",
            "title": "Backend Engineer",
        },
    )

    assert response.status_code == 422
    assert "apply" in response.text.lower()


def test_local_mutations_require_local_token() -> None:
    anonymous_client = TestClient(app)
    blocked = anonymous_client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/token-required",
            "company": "TokenCo",
            "title": "Backend Engineer",
        },
    )
    assert blocked.status_code == 403

    token = anonymous_client.get("/api/session").json()["mutation_token"]
    allowed = client.post(
        "/api/jobs/import",
        headers={"Origin": "http://127.0.0.1:5173", "X-JobFiller-Token": token},
        json={
            "url": "https://example.com/jobs/token-required",
            "company": "TokenCo",
            "title": "Backend Engineer",
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["company"] == "TokenCo"


def test_local_cors_allows_launcher_frontend_port_range() -> None:
    response = client.options(
        "/api/questions/1/answer",
        headers={
            "Origin": "http://127.0.0.1:5193",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-jobfiller-token",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5193"


def test_missing_static_asset_returns_404_not_dashboard_html() -> None:
    response = client.get("/assets/definitely-missing-jobfiller-test.js")

    assert response.status_code == 404
    assert "text/html" not in response.headers.get("content-type", "").lower()


def test_settings_reject_remote_ollama_url_without_opt_in() -> None:
    response = client.put(
        "/api/settings",
        json={
            "settings": {
                "candidate": {"name": "Test Candidate", "email": "candidate@example.com"},
                "llm": {"provider": "ollama", "ollama_url": "https://models.example.com", "model": "model"},
            }
        },
    )

    assert response.status_code == 422
    assert "localhost" in response.text.lower() or "127.0.0.1" in response.text


def test_scan_failure_returns_failed_run_without_unhandled_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable_scanner(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("scanner unavailable")

    monkeypatch.setattr("app.backend.main.run_scan", unavailable_scanner)

    response = client.post("/api/scans", json={"limit": 5, "source": "all", "remote_first": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["imported"] == 0
    assert "scanner unavailable" in payload["message"]

    runs = client.get("/api/runs").json()
    assert runs[0]["status"] == "FAILED"
    assert "scanner unavailable" in runs[0]["message"]


def test_scan_can_create_codex_job_site_handoff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    request_path = tmp_path / "codex_scan_request.json"
    prompt_path = tmp_path / "codex_scan_prompt.txt"
    monkeypatch.setattr("app.backend.services.codex_scan.REQUEST_JSON_PATH", request_path)
    monkeypatch.setattr("app.backend.services.codex_scan.REQUEST_PROMPT_PATH", prompt_path)

    response = client.post(
        "/api/scans",
        json={
            "limit": 3,
            "source": "seed",
            "remote_first": True,
            "scanner_keywords": "backend, fastapi",
            "codex_agent": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["codex_request_path"] == str(request_path)
    assert payload["codex_prompt_path"] == str(prompt_path)
    assert payload["codex_launched"] is False
    assert "Codex job-site scan request" in payload["message"]
    assert request_path.exists()
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "Use the local JobFiller MCP server." in prompt
    assert "export_jobs_to_jobfiller" in prompt
    assert "LinkedIn" in prompt
    assert "Indeed" in prompt


def test_import_processing_failure_creates_failed_job_and_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable_job_page(db, job, *, force: bool = False):  # noqa: ANN001
        raise RuntimeError("job page unavailable")

    monkeypatch.setattr("app.backend.main.process_job", unavailable_job_page)

    response = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/unavailable-posting",
            "company": "UnavailableCo",
            "title": "Backend Engineer",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "FAILED"
    assert payload["company"] == "UnavailableCo"

    runs = client.get("/api/runs").json()
    assert runs[0]["status"] == "FAILED"
    assert "job page unavailable" in runs[0]["message"]

    detail = client.get(f"/api/jobs/{payload['id']}").json()
    assert detail["job"]["status"] == "FAILED"


def test_artifact_generation_failure_preserves_existing_artifact_and_logs_run(monkeypatch: pytest.MonkeyPatch) -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/artifact-failure-preserve",
            "company": "ArtifactSafe",
            "title": "Backend Engineer",
            "key_requirements": "Python; APIs; testing",
            "keywords": "Python; FastAPI; backend",
        },
    )
    assert imported.status_code == 200
    job_id = imported.json()["id"]
    first_artifact_id = imported.json()["latest_artifact_id"]
    assert first_artifact_id

    def broken_generation(db, job):  # noqa: ANN001
        raise RuntimeError("tectonic failure")

    monkeypatch.setattr("app.backend.services.processor.generate_artifacts", broken_generation)

    regenerated = client.post(f"/api/jobs/{job_id}/artifacts/generate")

    assert regenerated.status_code == 200
    payload = regenerated.json()
    assert payload["status"] == "FAILED"
    assert payload["latest_artifact_id"] == first_artifact_id

    runs = client.get("/api/runs").json()
    assert any(run["status"] == "FAILED" and "tectonic failure" in run["message"] for run in runs)


def test_profile_fact_update_marks_existing_artifacts_stale() -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/stale-artifact-contract",
            "company": "StaleCo",
            "title": "Backend Engineer",
            "key_requirements": "Python; APIs; testing",
            "keywords": "Python; FastAPI; backend",
        },
    )
    assert imported.status_code == 200
    job_id = imported.json()["id"]
    artifact_id = imported.json()["latest_artifact_id"]
    assert artifact_id

    fact = client.post(
        "/api/profile-facts",
        json={
            "tag": "backend_depth",
            "question_text": "Backend depth",
            "answer": "Built FastAPI services and document pipelines.",
            "confidence": 0.9,
        },
    )
    assert fact.status_code == 200

    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["artifact"]["id"] == artifact_id
    assert "stale" in detail["artifact"]["compile_status"].lower()
    assert detail["job"]["status"] == "QA"


def test_question_skip_endpoint_marks_question_skipped() -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://www.linkedin.com/jobs/view/987654321",
            "company": "FinanceCo",
            "title": "Backend Engineer",
            "key_requirements": "finance; payments; APIs",
            "keywords": "finance; backend",
        },
    )
    assert imported.status_code == 200
    questions = client.get("/api/questions").json()
    question = next(item for item in questions if item["company"] == "FinanceCo")

    skipped = client.post(f"/api/questions/{question['id']}/skip")

    assert skipped.status_code == 200
    assert skipped.json()["status"] == "SKIPPED"
    all_questions = client.get("/api/questions?status=all").json()
    updated = next(item for item in all_questions if item["id"] == question["id"])
    assert updated["status"] == "SKIPPED"


def test_profile_fact_create_update_delete_contract() -> None:
    created = client.post(
        "/api/profile-facts",
        json={
            "tag": "remote_preference",
            "question_text": "Remote preference",
            "answer": "Prioritize remote backend and platform roles.",
            "confidence": 1.0,
        },
    )
    assert created.status_code == 200
    fact_id = created.json()["id"]

    updated = client.patch(
        f"/api/profile-facts/{fact_id}",
        json={"answer": "Remote-first; hybrid roles near my preferred location are acceptable.", "confidence": 0.9},
    )

    assert updated.status_code == 200
    assert "Remote-first" in updated.json()["answer"]
    deleted = client.delete(f"/api/profile-facts/{fact_id}")
    assert deleted.status_code == 200


def test_profile_fact_reuses_questions_and_unblocks_jobs() -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://www.linkedin.com/jobs/view/9900112233",
            "company": "FinanceCo",
            "title": "Backend Finance Engineer",
            "key_requirements": "finance; fixed income; trading systems",
            "keywords": "finance; backend",
        },
    )
    assert imported.status_code == 200
    job_id = imported.json()["id"]
    detail_before = client.get(f"/api/jobs/{job_id}")
    assert detail_before.status_code == 200
    assert detail_before.json()["job"]["status"] in {"NEEDS_INFO", "QA", "DISCOVERED", "PARSED"}

    open_questions = [item for item in client.get("/api/questions?status=OPEN").json() if item["job_id"] == job_id]
    assert any(item["tag"] == "finance_motivation" for item in open_questions)

    created = client.post(
        "/api/profile-facts",
        json={
            "tag": "finance_motivation",
            "question_text": "Finance motivation",
            "answer": "I am focused on finance product engineering because it combines systems thinking, reliability, and measurable impact. I am motivated to build secure, scalable tools that improve decision workflows.",
            "confidence": 0.98,
        },
    )
    assert created.status_code == 200

    remaining_open = [item for item in client.get("/api/questions?status=OPEN").json() if item["job_id"] == job_id]
    assert all(item["tag"] != "finance_motivation" for item in remaining_open)

    detail_after = client.get(f"/api/jobs/{job_id}").json()
    assert detail_after["job"]["status"] in {"NEEDS_INFO", "PARSED", "GENERATING", "QA", "READY"}


def test_job_patch_delete_and_run_detail_contract() -> None:
    imported = client.post(
        "/api/jobs/import",
        json={"url": "https://example.com/jobs/backend-test-contract", "company": "PatchCo", "title": "Backend Engineer"},
    )
    assert imported.status_code == 200
    job_id = imported.json()["id"]

    patched = client.patch(f"/api/jobs/{job_id}", json={"notes": "Follow up tomorrow.", "status": "QA"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "QA"

    runs = client.get("/api/runs").json()
    assert runs
    detail = client.get(f"/api/runs/{runs[0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == runs[0]["id"]

    deleted = client.delete(f"/api/jobs/{job_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/jobs/{job_id}").status_code == 404


def test_model_health_and_export_aliases_contract() -> None:
    health = client.get("/api/model-health")
    assert health.status_code == 200
    assert health.json()["provider"] == "Ollama"
    assert "model" in health.json()

    export = client.post("/api/export/workbook")
    assert export.status_code == 200
    assert export.json()["formats"]["xlsx"].endswith(".xlsx")
    workbook_path = export.json()["formats"]["xlsx"]
    assert zipfile.is_zipfile(workbook_path)
    with zipfile.ZipFile(workbook_path) as archive:
        names = set(archive.namelist())
        assert {"xl/workbook.xml", "xl/worksheets/sheet1.xml", "xl/styles.xml"} <= names
        for name in names:
            if name.endswith(".xml"):
                ET.fromstring(archive.read(name))

    json_export = client.get("/api/export/latest.json")
    csv_export = client.get("/api/export/latest.csv")
    assert json_export.status_code == 200
    assert csv_export.status_code == 200


def test_bulk_import_accepts_agent_job_records() -> None:
    response = client.post(
        "/api/imports/bulk",
        json={
            "source": "agent-fixture",
            "process": False,
            "jobs": [
                {
                    "url": "https://example.com/jobs/agent-imported-backend",
                    "company": "AgentCo",
                    "title": "Backend Engineer",
                    "location": "Remote",
                    "work_model": "Remote",
                    "key_requirements": "Python; APIs",
                    "keywords": "Python; FastAPI",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["imported"] == 1
    assert payload["errors"] == []
    jobs = client.get("/api/jobs").json()
    job = next(job for job in jobs if job["company"] == "AgentCo" and job["source"] == "agent-fixture")
    assert job["latest_artifact_id"] is not None


def test_bulk_import_blocks_auto_generation_when_questions_are_open() -> None:
    response = client.post(
        "/api/imports/bulk",
        json={
            "source": "agent-fixture",
            "jobs": [
                {
                    "url": "https://example.com/jobs/agent-imported-questions",
                    "company": "QuestionCo",
                    "title": "Backend Finance Engineer",
                    "location": "Remote",
                    "work_model": "Remote",
                    "key_requirements": "finance; fixed income; backend APIs",
                    "keywords": "finance; backend",
                    "manual_questions": "Can you relocate to Boston?\nAre you comfortable with a hybrid schedule?",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1

    jobs = client.get("/api/jobs").json()
    job = next(item for item in jobs if item["company"] == "QuestionCo")
    assert job["status"] == "NEEDS_INFO"
    assert job["open_questions"] >= 3
    assert job["latest_artifact_id"] is None

    questions = [item for item in client.get("/api/questions?status=OPEN").json() if item["job_id"] == job["id"]]
    assert any(item["tag"] == "finance_motivation" for item in questions)
    assert any(item["question_text"] == "Can you relocate to Boston?" for item in questions)
    assert any(item["question_text"] == "Are you comfortable with a hybrid schedule?" for item in questions)


def test_global_question_queue_deduplicates_reusable_questions() -> None:
    response = client.post(
        "/api/imports/bulk",
        json={
            "source": "agent-fixture",
            "jobs": [
                {
                    "url": "https://example.com/jobs/dedupe-question-a",
                    "company": "FirstQuestionCo",
                    "title": "Backend Engineer",
                    "manual_questions": "Confirm commute or relocation fit for the on-site requirement.",
                },
                {
                    "url": "https://example.com/jobs/dedupe-question-b",
                    "company": "SecondQuestionCo",
                    "title": "Backend Engineer",
                    "manual_questions": "Confirm commute or relocation fit for the on-site requirement.",
                },
            ],
        },
    )

    assert response.status_code == 200
    job_ids = response.json()["job_ids"]

    questions = client.get("/api/questions?status=OPEN").json()
    matching = [
        question
        for question in questions
        if question["question_text"] == "Confirm commute or relocation fit for the on-site requirement."
    ]
    assert len(matching) == 1
    assert matching[0]["duplicate_count"] == 2
    assert matching[0]["duplicate_job_ids"] == sorted(job_ids)

    for job_id in job_ids:
        job_questions = client.get(f"/api/jobs/{job_id}/questions?status=OPEN").json()
        assert len(
            [
                question
                for question in job_questions
                if question["question_text"] == "Confirm commute or relocation fit for the on-site requirement."
            ]
        ) == 1

    skipped = client.post(f"/api/questions/{matching[0]['id']}/skip")
    assert skipped.status_code == 200
    assert skipped.json()["skipped"] == 2
    all_questions = client.get("/api/questions?status=all").json()
    updated = [
        question
        for question in all_questions
        if question["question_text"] == "Confirm commute or relocation fit for the on-site requirement."
    ]
    assert len(updated) == 1
    assert updated[0]["duplicate_count"] == 2
    assert updated[0]["duplicate_job_ids"] == sorted(job_ids)
    assert {question["status"] for question in updated} == {"SKIPPED"}


def test_email_status_sync_updates_pipeline_followups_and_exports() -> None:
    response = client.post(
        "/api/email-sync/applications",
        json={
            "source": "gmail",
            "messages": [
                {
                    "id": "example-media-rejection",
                    "thread_id": "example-media-rejection",
                    "from": "Example Media Workday <no-reply@example-media.test>",
                    "subject": "An update about your application for Data Platform Engineer - R000105204",
                    "body": (
                        "Thank you for your time in applying for the Data Platform Engineer "
                        "- R000105204 position at Example Media. We have decided to pursue other candidates at this time."
                    ),
                    "email_ts": "2026-06-18T07:07:39+00:00",
                    "display_url": "https://mail.example.test/messages/example-media-rejection",
                },
                {
                    "id": "example-devices-identity",
                    "thread_id": "example-devices-identity",
                    "from": "Example Devices Recruiting <no-reply@example-devices.test>",
                    "subject": "Confirm your identity for job Factory Automation Engineer - 25010802",
                    "body": (
                        "We need you to confirm your identity so that your job application is considered for the job "
                        "Factory Automation Engineer - 25010802. "
                        "Confirm your identity using this code: 123456. https://careers.example-devices.test/s/example"
                    ),
                    "email_ts": "2026-06-01T21:54:39+00:00",
                    "display_url": "https://mail.example.test/messages/example-devices-identity",
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["states"] == {"REJECTED": 1, "ACTION_NEEDED": 1}

    events = client.get("/api/application-events?limit=10").json()
    rejected_event = next(event for event in events if event["company"] == "Example Media")
    action_event = next(event for event in events if event["company"] == "Example Devices")
    assert rejected_event["state"] == "REJECTED"
    assert "closed" in rejected_event["follow_up_action"].lower()
    assert action_event["state"] == "ACTION_NEEDED"
    assert "fresh code" in action_event["follow_up_action"].lower()

    jobs = client.get("/api/jobs?sort=recently-updated").json()
    assert not any(job["company"] == "Real Candidate Company" for job in jobs)

    checklist = client.get("/api/checklist/apply-queue").json()
    assert any(row["company"] == "Example Devices" and row["follow_up_action"] for row in checklist)

    export = client.post("/api/export/workbook")
    assert export.status_code == 200
    with zipfile.ZipFile(export.json()["formats"]["xlsx"]) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
        assert "Follow Ups" in workbook_xml

    json_rows = client.get("/api/export/latest.json").json()
    assert any(row["company"] == "Example Media" and row["application_state"] == "REJECTED" for row in json_rows)


def test_bulk_import_rejects_oversized_batches() -> None:
    response = client.post(
        "/api/imports/bulk",
        json={
            "source": "agent-fixture",
            "jobs": [{"url": f"https://example.com/jobs/oversized-{index}"} for index in range(101)],
        },
    )

    assert response.status_code == 422


def test_model_health_includes_queue_and_run_metrics() -> None:
    # Seed some activity so counters are populated.
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/health-metrics",
            "company": "HealthCo",
            "title": "Backend Engineer",
            "key_requirements": "Python; APIs; testing",
            "keywords": "Python; backend",
        },
    )
    assert imported.status_code == 200

    health = client.get("/api/model-health").json()
    assert isinstance(health["queue_depth"], int)
    assert "artifact_exports" in health
    assert "run_metrics" in health
    assert {"total_runs", "successful_runs", "failed_runs", "running_runs", "recent_runs_count"} <= set(health["run_metrics"])
    assert "job_status_counts" in health


def test_artifact_content_edit_creates_latest_revision() -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/artifact-editor-contract",
            "company": "ArtifactCo",
            "title": "Backend API Engineer",
            "key_requirements": "Python; APIs; testing",
            "keywords": "Python; FastAPI; backend",
        },
    )
    assert imported.status_code == 200
    job_id = imported.json()["id"]
    artifact_id = imported.json()["latest_artifact_id"]
    assert artifact_id

    content = client.get(f"/api/artifacts/{artifact_id}/content?kind=cover-letter")
    assert content.status_code == 200
    edited_text = content.json()["content"] + "\n\nManual review note: emphasize FastAPI service ownership."

    patched = client.patch(
        f"/api/artifacts/{artifact_id}/content",
        json={"kind": "cover-letter", "content": edited_text},
    )

    assert patched.status_code == 200
    assert patched.json()["revision"] > content.json()["revision"]

    detail = client.get(f"/api/jobs/{job_id}").json()
    latest_artifact_id = detail["artifact"]["id"]
    assert latest_artifact_id == patched.json()["artifact_id"]

    latest_content = client.get(f"/api/artifacts/{latest_artifact_id}/content?kind=cover-letter")
    assert latest_content.status_code == 200
    assert "emphasize FastAPI service ownership" in latest_content.json()["content"]


def test_artifact_download_and_generation_alias_endpoints() -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/artifact-alias-contract",
            "company": "AliasAI",
            "title": "Backend API Engineer",
            "key_requirements": "Python; APIs; tests",
            "keywords": "backend; python; fastapi",
        },
    )
    assert imported.status_code == 200
    job_id = imported.json()["id"]
    artifact_id = imported.json()["latest_artifact_id"]
    assert artifact_id

    generate = client.post(f"/api/jobs/{job_id}/artifacts/generate")
    assert generate.status_code == 200
    assert generate.json()["id"] == job_id

    latest_artifact_id = client.get(f"/api/jobs/{job_id}").json()["artifact"]["id"]
    download = client.get(f"/api/artifacts/{latest_artifact_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/pdf")

    cover_download = client.get(f"/api/artifacts/{latest_artifact_id}/download?kind=cover-letter")
    assert cover_download.status_code == 200
    assert cover_download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    latex_download = client.get(f"/api/artifacts/{latest_artifact_id}/download?kind=latex")
    assert latex_download.status_code == 200
    assert latex_download.headers["content-type"].startswith("text/plain")


def test_artifact_grade_endpoint_returns_current_grade() -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/artifact-grade-contract",
            "company": "QualityAI",
            "title": "Backend AI Engineer",
            "key_requirements": "Python; FastAPI; ML tooling",
            "keywords": "Python; APIs; backend",
        },
    )
    assert imported.status_code == 200
    artifact_id = imported.json()["latest_artifact_id"]
    assert artifact_id

    graded = client.post(f"/api/artifacts/{artifact_id}/grade")
    assert graded.status_code == 200
    payload = graded.json()
    assert payload["status"] == "graded"
    assert payload["overall_grade"] != ""
    assert payload["breakdown"]["score_items"]
    assert payload["breakdown"]["checks"]
    assert "keyword_coverage" in payload["breakdown"]
    assert "recommended_edits" in payload["breakdown"]

    detail = client.get(f"/api/jobs/{payload['job_id']}").json()
    assert detail["job"]["latest_grade_breakdown"]["score_items"]
    assert detail["grade"]["breakdown"]["score_items"]


def test_jobs_sort_newest_first() -> None:
    now_job = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/newest-first-1",
            "company": "FreshCo",
            "title": "Fresh Backend Role",
            "posting_age_text": "1 hour ago",
        },
    )
    old_job = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/newest-first-2",
            "company": "OlderCo",
            "title": "Older Backend Role",
            "posting_age_text": "3 days ago",
        },
    )
    unknown_job = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/newest-first-3",
            "company": "UnknownCo",
            "title": "Unknown Date Role",
        },
    )
    assert all(item.status_code == 200 for item in (now_job, old_job, unknown_job))

    jobs = client.get("/api/jobs?sort=newest&remote_first=true").json()

    assert [job["company"] for job in jobs][:3] == ["FreshCo", "OlderCo", "UnknownCo"]


def test_jobs_sort_grade_low_and_recently_updated() -> None:
    ready_job = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/grade-low-ready",
            "company": "ReadyCo",
            "title": "Ready Backend Role",
        },
    )
    needs_info_job = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/grade-low-needs",
            "company": "NeedsCo",
            "title": "Needs Info Backend Role",
        },
    )
    assert ready_job.status_code == 200
    assert needs_info_job.status_code == 200

    ready_id = ready_job.json()["id"]
    needs_id = needs_info_job.json()["id"]
    client.patch(f"/api/jobs/{ready_id}", json={"status": "READY"})
    client.patch(f"/api/jobs/{needs_id}", json={"status": "NEEDS_INFO"})

    grade_low = client.get("/api/jobs?sort=grade-low").json()
    grade_value = {"A+": 5.3, "A": 5, "A-": 4.7, "B+": 4.3, "B": 4, "B-": 3.7, "C": 3, "D": 2, "F": 1, "-": 0}
    tracked_ids = {ready_id: "ReadyCo", needs_id: "NeedsCo"}
    grade_low_jobs = [job for job in grade_low if job["id"] in tracked_ids]
    assert len(grade_low_jobs) >= 2
    sort_keys = []
    for job in grade_low_jobs:
        rank = grade_value.get(job["latest_grade"] or "-", 0)
        sort_keys.append((rank, job["readiness_score"] or 0, job["fit_score"]))
    assert sort_keys[0] <= sort_keys[1]

    # Touch one record to force a deterministic recently-updated ordering.
    client.patch(f"/api/jobs/{needs_id}", json={"notes": "updated for sorting check"})
    recent = client.get("/api/jobs?sort=recently-updated").json()
    assert recent[0]["id"] == needs_id


def test_questions_endpoint_supports_tag_filter() -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/tag-filter-1",
            "company": "TagCo",
            "title": "Software Engineer C++",
            "key_requirements": "C++; low latency",
            "keywords": "c++ c++",
        },
    )
    assert imported.status_code == 200
    open_questions = client.get("/api/questions?status=all").json()
    tags = {item["tag"] for item in open_questions}
    assert "cpp" in tags

    cpp_questions = client.get("/api/questions?status=all&tag=cpp").json()
    assert cpp_questions
    assert all(item["tag"] == "cpp" for item in cpp_questions)
    assert len(cpp_questions) == 1


def test_job_artifacts_endpoint_returns_version_history() -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/artifacts-endpoint-contract",
            "company": "ArtifactHistory",
            "title": "Backend API Engineer",
            "key_requirements": "Python; APIs; testing",
            "keywords": "backend; python; fastapi",
        },
    )
    assert imported.status_code == 200
    job_id = imported.json()["id"]

    response = client.get(f"/api/jobs/{job_id}/artifacts")
    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["latest_artifact_id"] == imported.json()["latest_artifact_id"]
    assert len(payload["artifacts"]) >= 1
    assert payload["artifacts"][0]["is_latest"] is True


def test_job_questions_endpoint_defaults_to_open_and_allows_status_filter() -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/job-questions-contract",
            "company": "QuestionHistory",
            "title": "Backend Product Engineer",
            "key_requirements": "C++; fintech; trading systems",
            "keywords": "backend; c++; finance",
        },
    )
    assert imported.status_code == 200
    job_id = imported.json()["id"]

    open_questions = client.get(f"/api/jobs/{job_id}/questions").json()
    all_questions = client.get(f"/api/jobs/{job_id}/questions?status=all").json()
    assert open_questions
    assert all(item["status"] == "OPEN" for item in open_questions)
    assert any(item["job_id"] == job_id for item in all_questions)


def test_assist_upload_requires_explicit_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    imported = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/assist-upload-contract",
            "company": "AssistContract",
            "title": "Associate Developer",
            "key_requirements": "Python; APIs; testing",
            "keywords": "python; api; testing",
        },
    )
    assert imported.status_code == 200
    job_id = imported.json()["id"]
    resume_path = imported.json()["latest_resume_pdf_path"]
    assert resume_path
    assert Path(resume_path).exists()

    launches: list[tuple[list[str], dict]] = []

    def fake_popen(args, **kwargs):  # noqa: ANN001, ANN003
        launches.append((args, kwargs))
        return object()

    monkeypatch.setattr("app.backend.main.subprocess.Popen", fake_popen)

    blocked = client.post(f"/api/jobs/{job_id}/assist-upload?kind=resume")
    assert blocked.status_code == 409
    assert launches == []

    allowed = client.post(f"/api/jobs/{job_id}/assist-upload?kind=resume&confirm=review-before-submit")
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "started"
    assert launches


def test_export_download_aliases_return_files() -> None:
    # Export endpoints are only valid after at least one workbook/export cycle, so create one.
    export = client.post("/api/export/workbook")
    assert export.status_code == 200

    workbook_download = client.get("/api/export/workbook/download")
    json_download = client.get("/api/export/json_export/download")
    csv_download = client.get("/api/export/csv_export/download")
    assert workbook_download.status_code == 200
    assert json_download.status_code == 200
    assert csv_download.status_code == 200


def test_tomorrow_checklist_contract_and_sorting() -> None:
    fresh = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/checklist-fresh",
            "company": "FreshCo",
            "title": "Backend Engineer",
            "posting_age_text": "2 hours ago",
            "key_requirements": "backend; APIs",
            "keywords": "python; fastapi",
            "materials": "Resume and cover letter.",
        },
    )
    older = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/checklist-older",
            "company": "OlderCo",
            "title": "Software Engineer I",
            "posting_age_text": "3 days ago",
            "key_requirements": "backend; platform",
            "keywords": "java; sql",
            "materials": "Portfolio link",
            "manual_questions": "Confirm relocation flexibility.",
        },
    )
    unknown = client.post(
        "/api/jobs/import",
        json={
            "url": "https://example.com/jobs/checklist-unknown",
            "company": "UnknownCo",
            "title": "Associate Developer",
            "key_requirements": "backend; apis",
            "keywords": "python; api",
        },
    )
    assert all(item.status_code == 200 for item in (fresh, older, unknown))

    checklist = client.get("/api/checklist/apply-queue").json()

    assert isinstance(checklist, list)
    assert len(checklist) >= 3
    ordered_companies = [row["company"] for row in checklist[:3]]
    assert ordered_companies == ["FreshCo", "OlderCo", "UnknownCo"]

    row = next(item for item in checklist if item["company"] == "FreshCo")
    for key in [
        "apply_order",
        "company",
        "title",
        "status",
        "apply_url",
        "location",
        "work_model",
        "fit_score",
        "grade",
        "ready_to_send",
        "materials",
        "manual_questions",
        "resume_pdf_path",
        "cover_letter_path",
        "resume_tex_path",
        "posting_age_text",
        "posted_at",
        "first_seen_at",
    ]:
        assert key in row
    assert row["apply_url"]
    assert "-resume-" in row["resume_pdf_path"]
    assert row["resume_pdf_path"].endswith(".pdf")
    assert row["resume_tex_path"].endswith("main.tex")
    assert row["cover_letter_path"].endswith(".docx")
    assert row["materials"] == "Resume and cover letter."
    assert row["manual_questions"] == ""
