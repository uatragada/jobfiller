from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("canonical_url", name="uq_jobs_canonical_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    apply_url: Mapped[str] = mapped_column(Text, default="")
    company: Mapped[str] = mapped_column(String(240), default="")
    title: Mapped[str] = mapped_column(String(320), default="")
    location: Mapped[str] = mapped_column(String(240), default="")
    work_model: Mapped[str] = mapped_column(String(80), default="")
    source: Mapped[str] = mapped_column(String(80), default="manual")
    fit_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="DISCOVERED")
    role_family: Mapped[str] = mapped_column(String(240), default="")
    key_requirements: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[str] = mapped_column(Text, default="")
    materials: Mapped[str] = mapped_column(Text, default="")
    manual_questions: Mapped[str] = mapped_column(Text, default="")
    salary: Mapped[str] = mapped_column(String(200), default="")
    posting_age_text: Mapped[str] = mapped_column(String(80), default="")
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    post: Mapped[Optional["JobPost"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    questions: Mapped[list["Question"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    grades: Mapped[list["Grade"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobPost(Base):
    __tablename__ = "job_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    raw_html: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    parsed_requirements: Mapped[str] = mapped_column(Text, default="")
    parsed_keywords: Mapped[str] = mapped_column(Text, default="")
    compensation: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="post")


class ProfileFact(Base):
    __tablename__ = "profile_facts"
    __table_args__ = (UniqueConstraint("tag", name="uq_profile_facts_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tag: Mapped[str] = mapped_column(String(120))
    question_text: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    tag: Mapped[str] = mapped_column(String(120))
    question_text: Mapped[str] = mapped_column(Text)
    blocking: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(40), default="OPEN")
    answer: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job] = relationship(back_populates="questions")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    revision: Mapped[int] = mapped_column(Integer)
    resume_tex_path: Mapped[str] = mapped_column(Text, default="")
    resume_pdf_path: Mapped[str] = mapped_column(Text, default="")
    cover_letter_path: Mapped[str] = mapped_column(Text, default="")
    workbook_path: Mapped[str] = mapped_column(Text, default="")
    compile_status: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="artifacts")


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    artifact_id: Mapped[Optional[int]] = mapped_column(ForeignKey("artifacts.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(120), default="ollama:auto")
    overall_grade: Mapped[str] = mapped_column(String(20), default="")
    ready_to_send: Mapped[bool] = mapped_column(Boolean, default=False)
    scores_json: Mapped[str] = mapped_column(Text, default="{}")
    passes_json: Mapped[str] = mapped_column(Text, default="{}")
    risks_json: Mapped[str] = mapped_column(Text, default="[]")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="grades")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="RUNNING")
    message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
