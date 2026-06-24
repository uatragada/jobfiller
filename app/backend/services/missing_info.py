from __future__ import annotations

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
        "project_metrics",
        ("metrics", "measurable impact", "high-scale", "throughput", "latency"),
        "Do you have concrete metrics for your projects, such as users, documents processed, latency, cost savings, or accuracy improvements?",
        impact="High",
        impact_score=84,
    ),
)


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
                Question.status == "OPEN",
            )
        ).first()
        if existing:
            created_or_open.append(existing)
            continue
        question = Question(job_id=job.id, tag=rule.tag, question_text=rule.question, blocking=True)
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
