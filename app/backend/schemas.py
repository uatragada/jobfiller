from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ImportJobRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    company: Optional[str] = Field(default=None, max_length=200)
    title: Optional[str] = Field(default=None, max_length=240)
    location: Optional[str] = Field(default=None, max_length=200)
    work_model: Optional[str] = Field(default=None, max_length=80)
    apply_url: Optional[str] = Field(default=None, max_length=2048)
    role_family: Optional[str] = Field(default=None, max_length=120)
    key_requirements: Optional[str] = Field(default=None, max_length=5000)
    keywords: Optional[str] = Field(default=None, max_length=2000)
    fit_score: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=5000)
    posting_age_text: Optional[str] = Field(default=None, max_length=100)
    raw_text: Optional[str] = Field(default=None, max_length=25000)
    materials: Optional[str] = Field(default=None, max_length=2000)
    manual_questions: Optional[str] = Field(default=None, max_length=2000)
    salary: Optional[str] = Field(default=None, max_length=200)


class BulkImportRequest(BaseModel):
    jobs: list[ImportJobRequest] = Field(default_factory=list, min_length=1, max_length=100)
    source: str = Field(default="agent", max_length=80)
    process: bool = False


class ScanRequest(BaseModel):
    remote_first: bool = True
    limit: Optional[int] = None
    source: Optional[str] = None
    scanner_keywords: Optional[str] = None


class AnswerQuestionRequest(BaseModel):
    answer: str = Field(min_length=1)


class ProfileFactRequest(BaseModel):
    tag: str = Field(min_length=1)
    question_text: str = ""
    answer: str = Field(min_length=1)
    confidence: float = 1.0


class ProfileFactPatchRequest(BaseModel):
    tag: Optional[str] = None
    question_text: Optional[str] = None
    answer: Optional[str] = None
    confidence: Optional[float] = None


class JobPatchRequest(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    work_model: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    key_requirements: Optional[str] = None
    keywords: Optional[str] = None


class ArtifactContentRequest(BaseModel):
    kind: str = "cover-letter"
    content: str = Field(min_length=1)


class JobOut(BaseModel):
    id: int
    company: str
    title: str
    location: str
    work_model: str
    source: str
    source_url: str
    apply_url: str
    fit_score: int
    status: str
    role_family: str
    key_requirements: str
    keywords: str
    posting_age_text: str
    salary: str
    materials: str
    manual_questions: str
    posted_at: Optional[datetime]
    first_seen_at: datetime
    last_seen_at: datetime
    updated_at: datetime
    latest_grade: Optional[str] = None
    ready_to_send: Optional[bool] = None
    latest_resume_pdf_path: Optional[str] = None
    latest_cover_letter_path: Optional[str] = None
    latest_artifact_id: Optional[int] = None
    artifact_count: int = 0
    readiness_score: Optional[int] = None
    open_questions: int = 0


class QuestionOut(BaseModel):
    id: int
    job_id: int
    company: str
    title: str
    tag: str
    impact: str = "Unknown"
    impact_score: int = 0
    question_text: str
    blocking: bool
    status: str
    answer: str
    created_at: datetime


class ProfileFactOut(BaseModel):
    id: int
    tag: str
    question_text: str
    answer: str
    confidence: float
    updated_at: datetime


class RunOut(BaseModel):
    id: int
    kind: str
    status: str
    message: str
    started_at: datetime
    finished_at: Optional[datetime]


class ScanOut(BaseModel):
    run_id: int
    imported: int
    message: str


class SettingsRequest(BaseModel):
    settings: dict
