from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..models import Artifact, Grade, Job, ProfileFact, Question, Run, utcnow
from .artifacts import generate_artifacts
from .local_llm import grade_resume, grading_model_name
from .missing_info import ensure_questions
from .time_utils import scan_sort_key


def latest_artifact(job: Job) -> Artifact | None:
    return sorted(job.artifacts, key=lambda item: item.revision, reverse=True)[0] if job.artifacts else None


def latest_grade(job: Job) -> Grade | None:
    return sorted(job.grades, key=lambda item: item.created_at, reverse=True)[0] if job.grades else None


def artifact_files_available(job: Job) -> bool:
    artifact = latest_artifact(job)
    if not artifact:
        return False
    return all(
        bool(path_value and Path(path_value).exists())
        for path_value in (artifact.resume_tex_path, artifact.resume_pdf_path, artifact.cover_letter_path)
    )


def grade_artifact(db: Session, artifact: Artifact) -> Grade | None:
    if not artifact.resume_pdf_path:
        message = "Local LLM grading skipped because resume PDF is missing."
        grade = Grade(
            job_id=artifact.job_id,
            artifact_id=artifact.id,
            model=grading_model_name(),
            overall_grade="ERROR",
            ready_to_send=False,
            risks_json=json.dumps([message]),
            raw_json=json.dumps({"error": message}),
        )
        db.add(grade)
        return grade
    if not Path(artifact.resume_pdf_path).exists():
        grade = Grade(
            job_id=artifact.job_id,
            artifact_id=artifact.id,
            model=grading_model_name(),
            overall_grade="ERROR",
            ready_to_send=False,
            risks_json=json.dumps(["Local LLM grading skipped because resume PDF is missing."]),
            raw_json=json.dumps({"error": "Missing resume PDF for grading"}),
        )
        db.add(grade)
        return grade

    try:
        grade = grade_resume(artifact.job, artifact)
        db.add(grade)
        return grade
    except Exception as exc:
        grade = Grade(
            job_id=artifact.job_id,
            artifact_id=artifact.id,
            model=grading_model_name(),
            overall_grade="ERROR",
            ready_to_send=False,
            scores_json="{}",
            passes_json="{}",
            risks_json=json.dumps([f"Local LLM grading failed: {exc}"]),
            raw_json=json.dumps({"error": str(exc)}),
        )
        db.add(grade)
        return grade


def process_job(db: Session, job: Job, *, force: bool = False) -> Job:
    if job.status == "READY" and not force and artifact_files_available(job):
        return job
    open_questions = ensure_questions(db, job)
    if open_questions:
        job.status = "NEEDS_INFO"
        job.updated_at = utcnow()
        db.flush()
        return job

    job.status = "GENERATING"
    job.updated_at = utcnow()
    db.flush()
    try:
        artifact = generate_artifacts(db, job)
    except Exception as exc:
        job.status = "FAILED"
        job.updated_at = utcnow()
        db.add(
            Run(
                kind="artifact_generation",
                status="FAILED",
                message=f"Artifact generation failed for {job.company} - {job.title}: {exc}",
                finished_at=utcnow(),
            )
        )
        db.flush()
        return job
    db.flush()
    job.status = "QA"
    grade = grade_artifact(db, artifact)
    if grade and grade.overall_grade != "ERROR":
        job.status = "READY" if grade.ready_to_send else "QA"
    elif grade:
        job.status = "QA"
    job.updated_at = utcnow()
    db.flush()
    return job


def mark_artifacts_stale_for_profile_change(
    db: Session,
    tag: str,
    *,
    exclude_job_ids: set[int] | None = None,
) -> int:
    excluded = exclude_job_ids or set()
    marked = 0
    jobs = db.scalars(select(Job)).all()
    for job in jobs:
        if job.id in excluded:
            continue
        artifact = latest_artifact(job)
        if not artifact:
            continue
        existing_status = artifact.compile_status or "previous compile status unavailable"
        if "stale" in existing_status.lower() and tag in existing_status:
            continue
        artifact.compile_status = (
            f"stale: profile fact '{tag}' changed after this revision; previous status: {existing_status}"
        )
        if job.status in {"READY", "QA"}:
            job.status = "QA"
        job.updated_at = utcnow()
        marked += 1

    if marked:
        db.add(
            Run(
                kind="profile_fact_update",
                status="SUCCEEDED",
                message=f"Marked {marked} artifact set(s) stale after profile fact '{tag}' changed.",
                finished_at=utcnow(),
            )
        )
    db.flush()
    return marked


def upsert_profile_fact(
    db: Session,
    tag: str,
    answer: str,
    question_text: str | None = None,
    *,
    confidence: float | None = None,
) -> ProfileFact:
    now = utcnow()
    values: dict[str, object] = {
        "tag": tag,
        "answer": answer,
        "question_text": question_text or "",
        "created_at": now,
        "updated_at": now,
    }
    update_values: dict[str, object] = {
        "answer": answer,
        "updated_at": now,
    }
    if question_text is not None:
        update_values["question_text"] = question_text
    if confidence is not None:
        values["confidence"] = confidence
        update_values["confidence"] = confidence

    db.execute(
        sqlite_insert(ProfileFact)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[ProfileFact.tag],
            set_=update_values,
        )
    )
    db.flush()
    return db.scalars(select(ProfileFact).where(ProfileFact.tag == tag)).one()


def apply_fact_to_tagged_open_questions(
    db: Session,
    tag: str,
    answer: str,
    question_text: str | None = None,
    *,
    process_jobs: bool = True,
) -> list[Job]:
    upsert_profile_fact(db, tag, answer, question_text)
    # Production sessions run with autoflush disabled, so make the upserted fact
    # visible before looking up linked open questions.
    db.flush()

    linked_questions = db.scalars(
        select(Question).where(Question.tag == tag, Question.status == "OPEN")
    ).all()
    if not linked_questions:
        db.flush()
        return []

    affected: dict[int, Job] = {}
    for linked_question in linked_questions:
        linked_question.answer = answer
        if question_text:
            linked_question.question_text = question_text
        linked_question.status = "ANSWERED"
        linked_question.answered_at = utcnow()
        affected[linked_question.job_id] = linked_question.job

    if process_jobs:
        for job in affected.values():
            if not any(q.status == "OPEN" and q.blocking for q in job.questions):
                process_job(db, job, force=True)
    db.flush()
    return list(affected.values())


def process_newest_queue(db: Session, limit: int = 20, *, remote_first: bool = True) -> int:
    jobs = db.scalars(
        select(Job).where(Job.status.in_(["PARSED", "DISCOVERED", "READY"]))
    ).all()
    jobs = [job for job in jobs if job.status != "READY" or not artifact_files_available(job)]
    jobs = sorted(
        jobs,
        key=lambda job: scan_sort_key(
            job.posted_at,
            job.first_seen_at,
            job.fit_score,
            remote_first=remote_first,
            location=job.location,
            work_model=job.work_model,
        ),
        reverse=True,
    )[:limit]
    for job in jobs:
        process_job(db, job)
    return len(jobs)


def answer_question(db: Session, question: Question, answer: str) -> list[Job]:
    question.answer = answer
    question.status = "ANSWERED"
    question.answered_at = utcnow()
    upsert_profile_fact(db, question.tag, answer, question.question_text, confidence=1.0)
    affected: dict[int, Job] = {question.job.id: question.job}
    for linked in apply_fact_to_tagged_open_questions(
        db,
        question.tag,
        answer,
        question.question_text,
        process_jobs=False,
    ):
        affected[linked.id] = linked
    db.flush()
    for job in affected.values():
        if not any(q.status == "OPEN" and q.blocking for q in job.questions):
            process_job(db, job, force=True)
    mark_artifacts_stale_for_profile_change(db, question.tag, exclude_job_ids=set(affected))
    db.flush()
    return list(affected.values())
