from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Job, ProfileFact, Question


@dataclass(frozen=True)
class MissingInfoRule:
    tag: str
    triggers: tuple[str, ...]
    question: str
    impact: str = "High"
    impact_score: int = 80


RULES = (
    MissingInfoRule(
        "cpp",
        ("c++", "cpp"),
        "Do you have real C++ experience beyond coursework? If yes, describe the project, libraries, and what you built.",
        impact="High",
        impact_score=95,
    ),
    MissingInfoRule(
        "healthcare",
        ("healthcare", "health tech", "patient", "clinical", "medical"),
        "Do you have healthcare, patient-data, HIPAA, or health-tech exposure that can be honestly referenced?",
        impact="High",
        impact_score=90,
    ),
    MissingInfoRule(
        "finance_motivation",
        (
            "finance",
            "fintech",
            "payments",
            "banking",
            "capital markets",
            "fixed income",
            "investment banking",
            "asset management",
            "trading",
            "risk analytics",
            "financial services",
        ),
        "What is your honest motivation for finance/fintech roles, and can we reference any finance-related background, coursework, or project work?",
        impact="High",
        impact_score=92,
    ),
    MissingInfoRule(
        "low_latency",
        ("low latency", "market data", "hft", "trading systems", "quant"),
        "Do you have any low-latency, concurrency, systems, or performance-sensitive programming experience we can truthfully include?",
        impact="Medium",
        impact_score=76,
    ),
    MissingInfoRule(
        "work_authorization_clearance",
        ("u.s. citizenship", "us citizenship", "public trust", "security clearance", "clearance eligibility"),
        "Can we truthfully state U.S. citizenship and public-trust or clearance eligibility for this application?",
        impact="High",
        impact_score=94,
    ),
    MissingInfoRule(
        "seniority_scope",
        ("senior", "staff", "principal", "lead engineer"),
        "Is this seniority level realistic for your background, and which concrete project or work evidence should support it?",
        impact="Medium",
        impact_score=74,
    ),
    MissingInfoRule(
        "project_metrics",
        ("metrics", "measurable impact", "high-scale", "throughput", "latency"),
        "Do you have concrete metrics for your projects, such as users, documents processed, latency, cost savings, or accuracy improvements?",
        impact="High",
        impact_score=84,
    ),
)

MANUAL_QUESTION_SPLIT_RE = re.compile(r"(?:\r?\n|;)+")
MANUAL_QUESTION_PREFIX_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s*")
MANUAL_QUESTION_PLACEHOLDERS = (
    "none found",
    "no action",
    "no immediate action",
    "no action unless",
    "candidate already",
    "application url should be opened",
    "verify application form",
    "find original application/job title",
)


def _normalize_manual_question(text: str) -> str:
    text = MANUAL_QUESTION_PREFIX_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _manual_question_tag(question_text: str) -> str:
    digest = hashlib.sha1(question_text.lower().encode("utf-8")).hexdigest()[:16]
    return f"manual_application_{digest}"


def _is_placeholder_manual_question(question_text: str) -> bool:
    lowered = question_text.lower().strip(". ")
    return any(lowered.startswith(placeholder) for placeholder in MANUAL_QUESTION_PLACEHOLDERS)


def manual_question_texts(job: Job) -> tuple[str, ...]:
    raw = (job.manual_questions or "").strip()
    if not raw:
        return ()
    pieces = [_normalize_manual_question(piece) for piece in MANUAL_QUESTION_SPLIT_RE.split(raw)]
    questions = []
    seen = set()
    for piece in pieces:
        if not piece:
            continue
        if _is_placeholder_manual_question(piece):
            continue
        key = piece.lower()
        if key in seen:
            continue
        seen.add(key)
        questions.append(piece)
    return tuple(questions)


def known_tags(db: Session) -> set[str]:
    return set(db.scalars(select(ProfileFact.tag)).all())


def detect_missing_info(db: Session, job: Job) -> list[MissingInfoRule]:
    text = " ".join(
        [
            job.company,
            job.title,
            job.role_family,
            job.key_requirements,
            job.keywords,
            job.notes,
            job.post.raw_text if job.post else "",
        ]
    ).lower()
    facts = known_tags(db)
    missing: list[MissingInfoRule] = []
    for rule in RULES:
        if rule.tag in facts:
            continue
        if any(trigger in text for trigger in rule.triggers):
            missing.append(rule)
    return missing


def ensure_questions(db: Session, job: Job) -> list[Question]:
    created_or_open: list[Question] = []
    for rule in detect_missing_info(db, job):
        existing = db.scalars(
            select(Question).where(
                Question.job_id == job.id,
                Question.tag == rule.tag,
            )
        ).first()
        if existing:
            if existing.status == "OPEN":
                created_or_open.append(existing)
            continue
        question = Question(job_id=job.id, tag=rule.tag, question_text=rule.question, blocking=True)
        db.add(question)
        created_or_open.append(question)
    for question_text in manual_question_texts(job):
        tag = _manual_question_tag(question_text)
        existing = db.scalars(
            select(Question).where(
                Question.job_id == job.id,
                Question.tag == tag,
            )
        ).first()
        if existing:
            if existing.status == "OPEN":
                created_or_open.append(existing)
            continue
        question = Question(job_id=job.id, tag=tag, question_text=question_text, blocking=True)
        db.add(question)
        created_or_open.append(question)
    return created_or_open


def impact_for_tag(tag: str) -> str:
    rule = next((item for item in RULES if item.tag == tag), None)
    return rule.impact if rule else "Medium"


def impact_score_for_tag(tag: str) -> int:
    rule = next((item for item in RULES if item.tag == tag), None)
    return rule.impact_score if rule else 60


def known_rules() -> tuple[MissingInfoRule, ...]:
    return RULES
