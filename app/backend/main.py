from __future__ import annotations

import json
import os
import secrets
import subprocess
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import __version__
from .database import get_db, init_db
from .models import Artifact, Grade, Job, ProfileFact, Question, Run, utcnow
from .schemas import (
    AnswerQuestionRequest,
    ArtifactContentRequest,
    BulkImportRequest,
    ScanRequest,
    ImportJobRequest,
    JobOut,
    JobPatchRequest,
    ProfileFactOut,
    ProfileFactPatchRequest,
    ProfileFactRequest,
    QuestionOut,
    RunOut,
    ScanOut,
    SettingsRequest,
)
from .settings import OUTPUT_ROOT, load_settings, public_settings, save_settings
from .services.artifacts import read_artifact_text, update_artifact_text
from .services.local_llm import allow_remote_ollama, configured_model, grading_model_name, ollama_tags_url, ollama_url_policy
from .services.ingestion import DEFAULT_SCAN_LIMIT, run_scan, upsert_job
from .services.normalize import unsafe_import_url_reason, unsafe_loopback_http_url_reason
from .services.processor import (
    answer_question,
    apply_fact_to_tagged_open_questions,
    latest_artifact,
    latest_grade,
    grade_artifact,
    mark_artifacts_stale_for_profile_change,
    process_job,
    process_newest_queue,
    upsert_profile_fact,
)
from .services.missing_info import impact_for_tag, impact_score_for_tag
from .services.time_utils import scan_sort_key
from .services.worker import worker
from .services.workbook import CSV_EXPORT_PATH, JSON_EXPORT_PATH, WORKBOOK_PATH, build_tomorrow_checklist, export_current_json_csv, export_current_workbook


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = ROOT / "app" / "frontend" / "dist"
TOKEN_PATH = OUTPUT_ROOT / ".jobfiller-token"
API_CAPABILITIES = {
    "question_answer_autoflush_fix": True,
    "local_mutation_token": True,
    "token_required_for_local_writes": True,
}


@asynccontextmanager
async def lifespan(_app: FastAPI):  # noqa: ANN201
    init_db()
    await worker.start()
    try:
        yield
    finally:
        await worker.stop()


app = FastAPI(title="JobFiller", version=__version__, lifespan=lifespan)
_configured_origins = [origin.strip() for origin in os.environ.get("JOBFILLER_ALLOWED_ORIGINS", "").split(",")]
_default_origins = [
    origin
    for port in range(5173, 5194)
    for origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")
]
_origin_allowlist = list(dict.fromkeys([*_default_origins, *[origin for origin in _configured_origins if origin]]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origin_allowlist,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def local_mutation_token() -> str:
    configured = os.environ.get("JOBFILLER_LOCAL_TOKEN", "").strip()
    if configured:
        return configured
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if TOKEN_PATH.exists():
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    TOKEN_PATH.write_text(token, encoding="utf-8")
    try:
        TOKEN_PATH.chmod(0o600)
    except OSError:
        pass
    return token


def mutation_token_required(request: Request) -> bool:
    method = request.method.upper()
    path = request.url.path
    if method == "OPTIONS":
        return False
    if path in {"/api/health", "/api/session"}:
        return False
    if method in {"GET", "HEAD"} and is_public_download_path(path):
        return False
    return path.startswith("/api")


def is_public_download_path(path: str) -> bool:
    if path in {"/api/workbook/latest", "/api/export/latest.json", "/api/export/latest.csv"}:
        return True
    if path.startswith("/api/export/") and path.endswith("/download"):
        return True
    if not path.startswith("/api/artifacts/"):
        return False
    return (
        path.endswith("/resume")
        or path.endswith("/cover-letter")
        or path.endswith("/latex")
        or path.endswith("/download")
    )


@app.middleware("http")
async def require_local_mutation_token(request: Request, call_next):  # noqa: ANN001
    if request.url.path.startswith("/api") and mutation_token_required(request):
        supplied = request.headers.get("x-jobfiller-token", "")
        if not secrets.compare_digest(supplied, local_mutation_token()):
            return JSONResponse({"detail": "Missing or invalid local JobFiller token."}, status_code=403)
    return await call_next(request)


def job_out(job: Job) -> JobOut:
    artifact = latest_artifact(job)
    grade = latest_grade(job)
    readiness_score = compute_readiness(job)
    return JobOut(
        id=job.id,
        company=job.company,
        title=job.title,
        location=job.location,
        work_model=job.work_model,
        source=job.source,
        source_url=job.source_url,
        apply_url=job.apply_url,
        fit_score=job.fit_score,
        status=job.status,
        role_family=job.role_family,
        key_requirements=job.key_requirements,
        keywords=job.keywords,
        posting_age_text=job.posting_age_text,
        salary=job.salary,
        materials=job.materials,
        manual_questions=job.manual_questions,
        posted_at=job.posted_at,
        first_seen_at=job.first_seen_at,
        last_seen_at=job.last_seen_at,
        updated_at=job.updated_at,
        latest_grade=grade.overall_grade if grade else None,
        ready_to_send=grade.ready_to_send if grade else None,
        latest_resume_pdf_path=artifact.resume_pdf_path if artifact else None,
        latest_cover_letter_path=artifact.cover_letter_path if artifact else None,
        latest_artifact_id=artifact.id if artifact else None,
        artifact_count=len(job.artifacts),
        readiness_score=readiness_score,
        open_questions=sum(1 for question in job.questions if question.status == "OPEN"),
    )


def grade_to_score(grade_text: str | None) -> float:
    if not grade_text:
        return 0.0
    return {
        "A+": 5.0,
        "A": 4.8,
        "A-": 4.6,
        "B+": 4.1,
        "B": 4.0,
        "B-": 3.7,
        "C+": 3.2,
        "C": 3.0,
        "C-": 2.7,
        "D": 2.0,
        "F": 1.0,
    }.get(grade_text, 0.0)


def compute_readiness(job: Job) -> int | None:
    grade = latest_grade(job)
    if not grade:
        return None
    scores = json.loads(grade.scores_json or "{}")
    numeric_scores = [float(value) for value in scores.values() if isinstance(value, (int, float))]
    if numeric_scores:
        average = sum(numeric_scores) / len(numeric_scores)
        return int(round(average * 100 if average <= 1 else average * 20 if average <= 5 else average))
    return 92 if grade.ready_to_send else 55


def artifact_folder_path(artifact: Artifact | None) -> Path | None:
    if not artifact:
        return None
    for field in (artifact.resume_pdf_path, artifact.resume_tex_path, artifact.cover_letter_path):
        if field:
            candidate = Path(field)
            if candidate.exists():
                return candidate.parent
    return None


def artifact_file_for_kind(artifact: Artifact, kind: str) -> tuple[Path, str]:
    paths = {
        "resume": artifact.resume_pdf_path,
        "cover-letter": artifact.cover_letter_path,
        "latex": artifact.resume_tex_path,
    }
    if kind not in paths:
        raise HTTPException(status_code=404, detail="Artifact kind not found")
    if not paths[kind]:
        raise HTTPException(status_code=404, detail=f"Artifact file missing: {kind}")
    file_path = Path(paths[kind])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact file missing: {file_path}")
    media_type = "application/pdf" if kind == "resume" else "text/plain"
    return file_path, media_type


def artifact_payload(artifact: Artifact, latest_id: int | None = None) -> dict[str, object]:
    return {
        "id": artifact.id,
        "job_id": artifact.job_id,
        "revision": artifact.revision,
        "resume_pdf_path": artifact.resume_pdf_path,
        "resume_tex_path": artifact.resume_tex_path,
        "cover_letter_path": artifact.cover_letter_path,
        "workbook_path": artifact.workbook_path,
        "compile_status": artifact.compile_status,
        "created_at": artifact.created_at,
        "resume_pdf_url": f"/api/artifacts/{artifact.id}/resume",
        "cover_letter_url": f"/api/artifacts/{artifact.id}/cover-letter",
        "latex_url": f"/api/artifacts/{artifact.id}/latex",
        "is_latest": latest_id is not None and artifact.id == latest_id,
    }


def require_valid_url(url: str, field_name: str = "Job import URL") -> None:
    parsed = urlparse(url)
    reason = unsafe_import_url_reason(url)
    if reason or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        detail = f"{field_name} requires a valid URL using public http(s). Unsafe URL rejected: {reason or 'invalid URL.'}"
        raise HTTPException(status_code=422, detail=detail)


def validate_import_urls(payload: ImportJobRequest) -> None:
    require_valid_url(payload.url, "Job source URL")
    if payload.apply_url:
        require_valid_url(payload.apply_url, "Job apply URL")


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "version": __version__, "capabilities": API_CAPABILITIES}


@app.get("/api/session")
def session() -> dict[str, object]:
    return {"mutation_token": local_mutation_token()}


@app.get("/api/settings")
def get_settings() -> dict[str, object]:
    return public_settings()


@app.put("/api/settings")
def put_settings(payload: SettingsRequest) -> dict[str, object]:
    llm = payload.settings.get("llm", {}) if isinstance(payload.settings, dict) else {}
    ollama_url = str(llm.get("ollama_url") or "").strip() if isinstance(llm, dict) else ""
    if ollama_url and unsafe_loopback_http_url_reason(ollama_url) and not allow_remote_ollama():
        raise HTTPException(
            status_code=422,
            detail="Ollama URL must point to localhost/127.0.0.1 unless JOBFILLER_ALLOW_REMOTE_OLLAMA=1 is set.",
        )
    save_settings(payload.settings)
    return public_settings()


@app.post("/api/scans", response_model=ScanOut)
def start_scan(payload: ScanRequest, db: Session = Depends(get_db)) -> ScanOut:
    run = Run(kind="manual_scan", status="RUNNING", message="Manual newest-first scan started.")
    db.add(run)
    db.commit()
    try:
        process_limit = payload.limit if payload.limit and payload.limit > 0 else DEFAULT_SCAN_LIMIT
        imported, message = run_scan(
            db,
            run,
            remote_first=payload.remote_first,
            source=payload.source,
            limit=process_limit,
            scanner_keywords=payload.scanner_keywords,
        )
        process_newest_queue(db, limit=process_limit, remote_first=payload.remote_first)
        run.status = "SUCCEEDED"
        run.message = message
        run.finished_at = utcnow()
        db.commit()
    except Exception as exc:
        run.status = "FAILED"
        run.message = f"{run.message} Failed: {exc}"
        run.finished_at = utcnow()
        db.commit()
        return ScanOut(run_id=run.id, imported=0, message=run.message)
    return ScanOut(run_id=run.id, imported=imported, message=message)


@app.post("/api/jobs/import", response_model=JobOut)
def import_job(payload: ImportJobRequest, db: Session = Depends(get_db)) -> JobOut:
    validate_import_urls(payload)
    run = Run(kind="import_job", status="RUNNING", message=f"Importing {payload.url}")
    db.add(run)
    db.flush()
    job: Job | None = None
    try:
        job = upsert_job(db, payload.model_dump(exclude_none=True), source="manual")
        process_job(db, job)
        if job.status == "FAILED":
            run.status = "FAILED"
            run.message = f"Imported {job.company} - {job.title}, but artifact processing failed."
        else:
            run.status = "SUCCEEDED"
            run.message = f"Imported {job.company} - {job.title}"
        run.finished_at = utcnow()
        db.commit()
    except Exception as exc:
        run.status = "FAILED"
        run.message = f"Import failed: {exc}"
        run.finished_at = utcnow()
        if job:
            job.status = "FAILED"
            job.updated_at = utcnow()
            db.commit()
            db.refresh(job)
            return job_out(job)
        db.commit()
        raise
    db.refresh(job)
    return job_out(job)


@app.post("/api/imports/bulk")
def bulk_import(payload: BulkImportRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    imported: list[Job] = []
    errors: list[dict[str, object]] = []
    for index, item in enumerate(payload.jobs):
        try:
            validate_import_urls(item)
            job = upsert_job(db, item.model_dump(exclude_none=True), source=payload.source or "agent")
            if payload.process:
                process_job(db, job)
            imported.append(job)
        except Exception as exc:  # keep agent batches resilient; callers get row-level errors.
            errors.append({"index": index, "url": item.url, "error": str(exc)})
    db.commit()
    return {
        "imported": len(imported),
        "errors": errors,
        "job_ids": [job.id for job in imported],
    }


@app.get("/api/jobs", response_model=list[JobOut])
def list_jobs(sort: str = "newest", remote_first: bool = True, db: Session = Depends(get_db)) -> list[JobOut]:
    jobs = db.scalars(select(Job)).all()

    if not jobs:
        return []

    if sort == "oldest":
        jobs.sort(key=lambda item: (0 if item.posted_at else 1, item.posted_at or item.first_seen_at))
    elif sort == "fit":
        jobs.sort(key=lambda item: item.fit_score, reverse=True)
    elif sort == "fit-low":
        jobs.sort(key=lambda item: item.fit_score)
    elif sort == "grade":
        jobs.sort(
            key=lambda item: (
                grade_to_score(latest_grade(item).overall_grade if latest_grade(item) else None),
                compute_readiness(item) or 0,
                item.fit_score,
            ),
            reverse=True,
        )
    elif sort in {"grade-low", "lowest_grade"}:
        jobs.sort(
            key=lambda item: (
                grade_to_score(latest_grade(item).overall_grade if latest_grade(item) else None),
                compute_readiness(item) or 0,
                item.fit_score,
            )
        )
    elif sort == "ready":
        jobs.sort(key=lambda item: compute_readiness(item) or 0, reverse=True)
    elif sort == "recently-updated":
        jobs.sort(key=lambda item: item.updated_at, reverse=True)
    elif sort == "needs-info":
        jobs.sort(
            key=lambda item: (
                sum(1 for q in item.questions if q.status == "OPEN" and q.blocking),
                item.posted_at or item.first_seen_at,
            ),
            reverse=True,
        )
    elif sort == "company":
        jobs.sort(key=lambda item: item.company.lower())
    elif sort == "status":
        jobs.sort(key=lambda item: item.status)
    else:
        jobs.sort(
            key=lambda item: scan_sort_key(
                item.posted_at,
                item.first_seen_at,
                item.fit_score,
                remote_first=remote_first,
                location=item.location,
                work_model=item.work_model,
            ),
            reverse=True,
        )
    return [job_out(job) for job in jobs]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    artifact = latest_artifact(job)
    grade = latest_grade(job)
    return {
        "job": job_out(job).model_dump(),
        "post": {
            "summary": job.post.summary if job.post else "",
            "raw_text": job.post.raw_text if job.post else "",
            "parsed_requirements": job.post.parsed_requirements if job.post else "",
            "parsed_keywords": job.post.parsed_keywords if job.post else "",
            "compensation": job.post.compensation if job.post else "",
        },
        "materials": job.materials,
        "manual_questions": job.manual_questions,
        "salary": job.salary,
        "questions": [question_out(q).model_dump() for q in job.questions],
        "artifact": {
            "id": artifact.id if artifact else None,
            "revision": artifact.revision if artifact else None,
            "resume_tex_path": artifact.resume_tex_path if artifact else None,
            "resume_pdf_path": artifact.resume_pdf_path if artifact else None,
            "cover_letter_path": artifact.cover_letter_path if artifact else None,
            "resume_pdf_url": f"/api/artifacts/{artifact.id}/resume" if artifact else None,
            "cover_letter_url": f"/api/artifacts/{artifact.id}/cover-letter" if artifact else None,
            "folder_path": str(artifact_folder_path(artifact)) if artifact else None,
            "compile_status": artifact.compile_status if artifact else None,
            "created_at": artifact.created_at if artifact else None,
        },
        "grade": {
            "overall_grade": grade.overall_grade if grade else None,
            "ready_to_send": grade.ready_to_send if grade else None,
            "scores": json.loads(grade.scores_json) if grade else {},
            "passes": json.loads(grade.passes_json) if grade else {},
            "risks": json.loads(grade.risks_json) if grade else [],
        },
    }


@app.get("/api/jobs/{job_id}/artifacts")
def list_job_artifacts(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    artifacts = db.scalars(
        select(Artifact)
        .where(Artifact.job_id == job_id)
        .order_by(Artifact.revision.desc(), Artifact.created_at.desc())
    ).all()
    latest_id = artifacts[0].id if artifacts else None
    return {
        "job_id": job.id,
        "latest_artifact_id": latest_id,
        "artifacts": [artifact_payload(artifact, latest_id=latest_id) for artifact in artifacts],
    }


@app.get("/api/jobs/{job_id}/questions")
def list_job_questions(
    job_id: int,
    db: Session = Depends(get_db),
    status: str = "OPEN",
) -> list[QuestionOut]:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    query = select(Question).where(Question.job_id == job_id)
    if status != "all":
        query = query.where(Question.status == status)
    rows = [question_out(q) for q in db.scalars(query).all()]
    rows.sort(key=lambda row: (row.created_at), reverse=True)
    return rows


@app.patch("/api/jobs/{job_id}", response_model=JobOut)
def patch_job(job_id: int, payload: JobPatchRequest, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is not None and hasattr(job, field):
            setattr(job, field, value)
    job.updated_at = utcnow()
    db.commit()
    db.refresh(job)
    return job_out(job)


@app.post("/api/jobs/{job_id}/reprocess", response_model=JobOut)
def reprocess_job(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    process_job(db, job, force=True)
    db.commit()
    db.refresh(job)
    return job_out(job)


@app.post("/api/jobs/{job_id}/artifacts/generate", response_model=JobOut)
def generate_job_artifacts(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    process_job(db, job, force=True)
    db.commit()
    db.refresh(job)
    return job_out(job)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"status": "deleted"}


def question_out(question: Question) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        job_id=question.job_id,
        company=question.job.company,
        title=question.job.title,
        tag=question.tag,
        impact=impact_for_tag(question.tag),
        impact_score=impact_score_for_tag(question.tag),
        question_text=question.question_text,
        blocking=question.blocking,
        status=question.status,
        answer=question.answer,
        created_at=question.created_at,
    )


@app.get("/api/questions", response_model=list[QuestionOut])
def list_questions(
    status: str = "OPEN",
    sort: str = "impact",
    tag: str = "all",
    db: Session = Depends(get_db),
) -> list[QuestionOut]:
    query = select(Question)
    if status != "all":
        query = query.where(Question.status == status)
    if tag and tag != "all":
        query = query.where(Question.tag == tag)
    rows = [question_out(q) for q in db.scalars(query).all()]
    if sort == "impact":
        rows.sort(key=lambda row: (row.blocking, row.impact_score, row.created_at), reverse=True)
    elif sort == "impact-low":
        rows.sort(key=lambda row: (row.impact_score, row.created_at))
    elif sort == "recent":
        rows.sort(key=lambda row: row.created_at, reverse=True)
    elif sort == "oldest":
        rows.sort(key=lambda row: row.created_at)
    elif sort == "status":
        rows.sort(key=lambda row: (row.status, row.created_at))
    else:
        rows.sort(key=lambda row: (row.blocking, row.impact_score, row.created_at), reverse=True)
    return rows


@app.post("/api/questions/{question_id}/answer")
def answer(question_id: int, payload: AnswerQuestionRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    affected = answer_question(db, question, payload.answer)
    db.commit()
    return {"affected_job_ids": [job.id for job in affected]}


@app.post("/api/questions/{question_id}/skip")
def skip_question(question_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    question.status = "SKIPPED"
    question.answered_at = utcnow()
    db.commit()
    return {"id": question.id, "status": question.status}


@app.get("/api/profile-facts", response_model=list[ProfileFactOut])
def list_profile_facts(db: Session = Depends(get_db)) -> list[ProfileFactOut]:
    facts = db.scalars(select(ProfileFact).order_by(ProfileFact.updated_at.desc())).all()
    return [
        ProfileFactOut(
            id=fact.id,
            tag=fact.tag,
            question_text=fact.question_text,
            answer=fact.answer,
            confidence=fact.confidence,
            updated_at=fact.updated_at,
        )
        for fact in facts
    ]


@app.post("/api/profile-facts", response_model=ProfileFactOut)
def create_profile_fact(payload: ProfileFactRequest, db: Session = Depends(get_db)) -> ProfileFactOut:
    fact = upsert_profile_fact(
        db,
        payload.tag,
        payload.answer,
        payload.question_text,
        confidence=payload.confidence,
    )
    affected = apply_fact_to_tagged_open_questions(db, fact.tag, fact.answer, fact.question_text)
    mark_artifacts_stale_for_profile_change(db, fact.tag, exclude_job_ids={job.id for job in affected})
    db.commit()
    db.refresh(fact)
    return ProfileFactOut(
        id=fact.id,
        tag=fact.tag,
        question_text=fact.question_text,
        answer=fact.answer,
        confidence=fact.confidence,
        updated_at=fact.updated_at,
    )


@app.patch("/api/profile-facts/{fact_id}", response_model=ProfileFactOut)
def patch_profile_fact(fact_id: int, payload: ProfileFactPatchRequest, db: Session = Depends(get_db)) -> ProfileFactOut:
    fact = db.get(ProfileFact, fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is not None and hasattr(fact, field):
            setattr(fact, field, value)
    fact.updated_at = utcnow()
    affected: list[Job] = []
    if payload.answer is not None or payload.question_text is not None:
        affected = apply_fact_to_tagged_open_questions(db, fact.tag, fact.answer, fact.question_text)
        mark_artifacts_stale_for_profile_change(db, fact.tag, exclude_job_ids={job.id for job in affected})
    db.commit()
    db.refresh(fact)
    return ProfileFactOut(
        id=fact.id,
        tag=fact.tag,
        question_text=fact.question_text,
        answer=fact.answer,
        confidence=fact.confidence,
        updated_at=fact.updated_at,
    )


@app.delete("/api/profile-facts/{fact_id}")
def delete_profile_fact(fact_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    fact = db.get(ProfileFact, fact_id)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    db.delete(fact)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/runs", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db)) -> list[RunOut]:
    runs = db.scalars(select(Run).order_by(Run.started_at.desc()).limit(50)).all()
    return [RunOut(id=r.id, kind=r.kind, status=r.status, message=r.message, started_at=r.started_at, finished_at=r.finished_at) for r in runs]


@app.get("/api/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    duration_seconds = None
    if run.finished_at:
        duration_seconds = max(0.0, (run.finished_at - run.started_at).total_seconds())
    return {
        "id": run.id,
        "kind": run.kind,
        "status": run.status,
        "message": run.message,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_seconds": duration_seconds,
    }


@app.get("/api/model-health")
def model_health(db: Session = Depends(get_db)) -> dict[str, object]:
    queue_depth = (
        db.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.status.in_(["DISCOVERED", "PARSED", "GENERATING", "QA"]))
        )
        or 0
    )
    latest_run = db.scalars(select(Run).order_by(Run.started_at.desc())).first()
    total_runs = db.scalar(select(func.count()).select_from(Run)) or 0
    successful_runs = db.scalar(select(func.count()).select_from(Run).where(Run.status == "SUCCEEDED")) or 0
    failed_runs = db.scalar(select(func.count()).select_from(Run).where(Run.status == "FAILED")) or 0
    running_runs = db.scalar(select(func.count()).select_from(Run).where(Run.status == "RUNNING")) or 0
    run_rows = db.scalars(select(Run).order_by(Run.started_at.desc()).limit(50)).all()
    run_durations = []
    for run in run_rows:
        if run.finished_at:
            run_durations.append(max(0.0, (run.finished_at - run.started_at).total_seconds()))
    avg_recent_duration = round(sum(run_durations) / len(run_durations), 2) if run_durations else None
    job_status_rows = db.execute(
        select(Job.status, func.count().label("count")).group_by(Job.status)
    ).all()
    job_status_counts = {status: count for status, count in job_status_rows}
    scanner_running = db.scalar(
        select(func.count())
        .select_from(Run)
        .where(Run.status == "RUNNING", Run.kind.in_(["manual_scan", "scheduled_scan"]))
    ) or 0
    ollama_policy = ollama_url_policy()
    ollama_status = "connected"
    if ollama_policy["blocked"]:
        ollama_status = "blocked remote endpoint"
    else:
        try:
            with urllib.request.urlopen(ollama_tags_url(), timeout=1) as response:
                ollama_status = "connected" if response.status < 500 else "degraded"
        except Exception:
            ollama_status = "not reachable"
    return {
        "model": grading_model_name(),
        "configured_model": configured_model() or "",
        "provider": "Ollama",
        "mode": ollama_policy["mode"],
        "ollama_url_effective": ollama_policy["effective_url"],
        "ollama_url_blocked": ollama_policy["blocked"],
        "status": ollama_status,
        "scanner": "running" if (scanner_running or worker.is_running) else "idle",
        "worker": "running" if worker.is_running else "idle",
        "queue_depth": queue_depth,
        "artifact_exports": {
            "workbook_exists": WORKBOOK_PATH.exists(),
            "json_export_exists": JSON_EXPORT_PATH.exists(),
            "csv_export_exists": CSV_EXPORT_PATH.exists(),
            "workbook_path": str(WORKBOOK_PATH),
            "json_export_path": str(JSON_EXPORT_PATH),
            "csv_export_path": str(CSV_EXPORT_PATH),
        },
        "job_status_counts": job_status_counts,
        "last_run_status": latest_run.status if latest_run else "unknown",
        "last_run_at": latest_run.started_at if latest_run else None,
        "run_metrics": {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "running_runs": running_runs,
            "recent_runs_count": len(run_rows),
            "avg_recent_duration_seconds": avg_recent_duration,
        },
    }


@app.post("/api/workbook/export")
def export_workbook(db: Session = Depends(get_db)) -> dict[str, str]:
    path = export_current_workbook(db)
    return {"status": "exported", "path": str(path), "url": "/api/workbook/latest"}


@app.post("/api/export/workbook")
def export_workbook_alias(db: Session = Depends(get_db)) -> dict[str, object]:
    workbook = export_current_workbook(db)
    extra = export_current_json_csv(db)
    return {
        "status": "exported",
        "formats": {
            "xlsx": str(workbook),
            "json": str(extra["json"]),
            "csv": str(extra["csv"]),
        },
        "urls": {
            "xlsx": "/api/workbook/latest",
            "json": "/api/export/latest.json",
            "csv": "/api/export/latest.csv",
        },
    }


@app.get("/api/export/{export_id}/download")
def download_latest_export(export_id: str, db: Session = Depends(get_db)) -> FileResponse:
    export_key = export_id.strip().lower()
    if export_key in {"workbook", "xlsx", "xls", "jobfiller", "jobfiller-feedback-loop"}:
        export_workbook_path = export_current_workbook(db)
        return FileResponse(
            export_workbook_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=export_workbook_path.name,
        )
    if export_key in {"json", "json_export", "latestjson", "latest_json"}:
        exports = export_current_json_csv(db)
        return FileResponse(
            exports["json"],
            media_type="application/json",
            filename=Path(exports["json"]).name,
        )
    if export_key in {"csv", "csv_export", "latestcsv", "latest_csv"}:
        exports = export_current_json_csv(db)
        return FileResponse(
            exports["csv"],
            media_type="text/csv",
            filename=Path(exports["csv"]).name,
        )
    raise HTTPException(status_code=404, detail=f"Unknown export identifier: {export_id}")


@app.get("/api/workbook/latest")
def download_workbook() -> FileResponse:
    if not WORKBOOK_PATH.exists():
        raise HTTPException(status_code=404, detail="Workbook has not been exported yet")
    return FileResponse(
        WORKBOOK_PATH,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=WORKBOOK_PATH.name,
    )


@app.get("/api/checklist/tomorrow")
def tomorrow_checklist(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return build_tomorrow_checklist(db)


@app.get("/api/checklist/apply-queue")
def apply_queue_checklist(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return build_tomorrow_checklist(db)


@app.get("/api/export/latest.json")
def download_latest_json() -> FileResponse:
    if not JSON_EXPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="JSON export has not been generated yet")
    return FileResponse(JSON_EXPORT_PATH, media_type="application/json", filename=JSON_EXPORT_PATH.name)


@app.get("/api/export/latest.csv")
def download_latest_csv() -> FileResponse:
    if not CSV_EXPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="CSV export has not been generated yet")
    return FileResponse(CSV_EXPORT_PATH, media_type="text/csv", filename=CSV_EXPORT_PATH.name)


@app.get("/api/artifacts/{artifact_id}/content")
def get_artifact_content(artifact_id: int, kind: str = "cover-letter", db: Session = Depends(get_db)) -> dict[str, object]:
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        file_path, content = read_artifact_text(artifact, kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Artifact file missing: {exc}") from exc
    return {
        "artifact_id": artifact.id,
        "job_id": artifact.job_id,
        "revision": artifact.revision,
        "kind": kind,
        "path": str(file_path),
        "content": content,
    }


@app.patch("/api/artifacts/{artifact_id}/content")
def patch_artifact_content(
    artifact_id: int,
    payload: ArtifactContentRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        next_artifact = update_artifact_text(db, artifact, payload.kind, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    next_artifact.job.updated_at = utcnow()
    if payload.kind == "latex":
        grade_artifact(db, next_artifact)
    db.commit()
    db.refresh(next_artifact)
    return {
        "status": "saved",
        "artifact_id": next_artifact.id,
        "job_id": next_artifact.job_id,
        "revision": next_artifact.revision,
        "resume_pdf_path": next_artifact.resume_pdf_path,
        "resume_tex_path": next_artifact.resume_tex_path,
        "cover_letter_path": next_artifact.cover_letter_path,
        "compile_status": next_artifact.compile_status,
    }


@app.post("/api/artifacts/{artifact_id}/grade")
def grade_artifact_now(artifact_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    grade = grade_artifact(db, artifact)
    db.commit()
    latest = latest_grade(artifact.job)
    if not latest:
        return {"status": "not_graded", "artifact_id": artifact.id}
    return {
        "status": "graded",
        "artifact_id": artifact.id,
        "job_id": artifact.job_id,
        "grade_id": latest.id,
        "overall_grade": latest.overall_grade,
        "ready_to_send": latest.ready_to_send,
        "grade_revision": latest.id,
    }


@app.get("/api/artifacts/{artifact_id}/resume")
def download_artifact_resume(artifact_id: int, db: Session = Depends(get_db)) -> FileResponse:
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    file_path, media_type = artifact_file_for_kind(artifact, "resume")
    return FileResponse(file_path, media_type=media_type, filename=file_path.name)


@app.get("/api/artifacts/{artifact_id}/cover-letter")
def download_artifact_cover_letter(artifact_id: int, db: Session = Depends(get_db)) -> FileResponse:
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    file_path, media_type = artifact_file_for_kind(artifact, "cover-letter")
    return FileResponse(file_path, media_type=media_type, filename=file_path.name)


@app.get("/api/artifacts/{artifact_id}/latex")
def download_artifact_latex(artifact_id: int, db: Session = Depends(get_db)) -> FileResponse:
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    file_path, media_type = artifact_file_for_kind(artifact, "latex")
    return FileResponse(file_path, media_type=media_type, filename=file_path.name)


@app.get("/api/artifacts/{artifact_id}/download")
def download_artifact_default(
    artifact_id: int,
    kind: str = "resume",
    db: Session = Depends(get_db),
) -> FileResponse:
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    file_path, media_type = artifact_file_for_kind(artifact, kind)
    return FileResponse(file_path, media_type=media_type, filename=file_path.name)


@app.post("/api/artifacts/{artifact_id}/open-folder")
def open_artifact_folder(artifact_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    folder = artifact_folder_path(artifact)
    if not folder:
        raise HTTPException(status_code=404, detail="No artifact files available to open")
    if os.name == "nt":
        explorer = ["explorer", str(folder)]
        subprocess.Popen(explorer, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        subprocess.Popen(["xdg-open", str(folder)])
    return {
        "status": "opened",
        "folder": str(folder),
        "artifact_id": artifact.id,
        "job_id": artifact.job_id,
    }


@app.get("/api/artifacts/{artifact_id}/open")
def open_artifact_folder_alias(artifact_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return open_artifact_folder(artifact_id, db)


UPLOAD_CONFIRMATION = "review-before-submit"


@app.post("/api/jobs/{job_id}/assist-upload")
def assist_upload(job_id: int, kind: str = "resume", confirm: str = "", db: Session = Depends(get_db)) -> dict[str, str]:
    if confirm != UPLOAD_CONFIRMATION:
        raise HTTPException(
            status_code=409,
            detail="Upload helper requires explicit confirmation that the user will review before final submit.",
        )
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    artifact = latest_artifact(job)
    if not artifact:
        raise HTTPException(status_code=400, detail="No artifact available")
    if kind not in {"resume", "cover-letter"}:
        raise HTTPException(status_code=422, detail="Upload helper supports resume or cover-letter only")
    file_path = artifact.resume_pdf_path if kind == "resume" else artifact.cover_letter_path
    helper = ROOT / "helpers" / "Start-BrowserResumeUpload.ps1"
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=400, detail=f"Artifact does not exist: {file_path}")
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper),
            "-FilePath",
            file_path,
            "-ButtonName",
            "Attach",
        ],
        cwd=str(ROOT),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return {"status": "started", "file_path": file_path}


@app.get("/{full_path:path}", include_in_schema=False)
def serve_dashboard(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard build not found. Run npm run build in app/frontend or start the dev frontend.")
    requested = (FRONTEND_DIST / full_path).resolve()
    try:
        requested.relative_to(FRONTEND_DIST.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Static file not found") from exc
    if full_path and requested.exists() and requested.is_file():
        return FileResponse(requested)
    if full_path.startswith("assets/") or Path(full_path).suffix:
        raise HTTPException(status_code=404, detail="Static file not found")
    return FileResponse(index_path)
