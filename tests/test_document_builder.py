from __future__ import annotations

import pytest

from app.backend.models import Job
from app.backend.services.document_builder import (
    build_cover_letter_prompt,
    build_tex,
    make_cover_letter,
    read_cover_letter_docx,
    write_cover_letter_docx,
)
from app.backend.services.local_llm import validate_resume_text


@pytest.fixture
def document_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.backend.services.document_builder.candidate_profile",
        lambda: {
            "name": "Candidate Example",
            "email": "candidate@example.com",
            "phone": "555-0100",
            "location": "Raleigh, NC",
            "linkedin": "linkedin.com/in/candidate-example",
            "website": "www.candidate-example.dev/",
            "summary": "I build backend systems with Python, FastAPI, and data workflows.",
            "education": [{"school": "Example University", "degree": "BS Computer Science", "dates": "2020"}],
            "experience": [
                {
                    "title": "Backend Engineer",
                    "company": "WorkCo",
                    "location": "Remote",
                    "dates": "JOB-DATES-SHOULD-RENDER",
                    "bullets": [
                        "Built Python APIs with test coverage.",
                        "Maintained frontend dashboards for internal users.",
                    ],
                }
            ],
            "projects": [
                {
                    "name": "DocBridge",
                    "dates": "PROJECT-DATES-SHOULD-NOT-RENDER",
                    "description": "Document extraction system using FastAPI.",
                    "skills": ["Python", "FastAPI"],
                    "bullets": [
                        "Implemented document parsing and review workflows.",
                        "Built a FastAPI service for API-based validation.",
                    ],
                }
            ],
            "skills": ["Python", "FastAPI", "SQL"],
            "cover_letter": "I am drawn to engineering teams where careful backend work, clear communication, and reliable delivery matter.",
        },
    )


@pytest.fixture
def backend_job() -> Job:
    return Job(
        company="Acme",
        title="Backend Engineer",
        key_requirements="Python; APIs; testing",
        keywords="Python; FastAPI; SQL",
        role_family="backend",
    )


def test_resume_preserves_saved_overleaf_template_settings_and_header_macros(
    document_profile: None,
    backend_job: Job,
) -> None:
    tex = build_tex(backend_job)

    assert r"\documentclass[10pt, letterpaper]{article}" in tex
    assert "top=2 cm" in tex
    assert "bottom=2 cm" in tex
    assert "left=2 cm" in tex
    assert "right=2 cm" in tex
    assert "footskip=1.0 cm" in tex
    assert r"\usepackage{fontawesome5}" in tex
    assert r"\usepackage{charter}" in tex
    assert r"\newenvironment{header}" in tex
    assert r"\let\hrefWithoutArrow\href" in tex
    assert r"\begin{header}" in tex
    assert r"\fontsize{25 pt}{25 pt}\selectfont Candidate Example" in tex


def test_resume_does_not_emit_bottom_skills_or_technologies_section(
    document_profile: None,
    backend_job: Job,
) -> None:
    tex = build_tex(backend_job)

    assert r"\section{Skills}" not in tex
    assert r"\section{Technologies}" not in tex
    assert r"\textbf{Technologies:} Python, FastAPI" in tex


def test_resume_keeps_job_dates_but_omits_project_dates(document_profile: None, backend_job: Job) -> None:
    tex = build_tex(backend_job)

    assert "JOB-DATES-SHOULD-RENDER" in tex
    assert "PROJECT-DATES-SHOULD-NOT-RENDER" not in tex


def test_cover_letter_uses_role_specific_voice_without_jobfiller_scaffold(
    document_profile: None,
    backend_job: Job,
) -> None:
    cover_letter = make_cover_letter(backend_job)

    forbidden_phrases = [
        "using JobFiller",
        "I am configuring JobFiller",
        "configured profile facts",
        "source materials",
        "tailored application packet",
        "reviewed and adjusted before submission",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in cover_letter
    assert "Acme" in cover_letter
    assert "Backend Engineer" in cover_letter
    assert "DocBridge" in cover_letter
    assert "WorkCo" in cover_letter
    assert 180 <= len(cover_letter.split()) <= 290


def test_cover_letter_prompt_preserves_source_letter_and_limits_edits(
    document_profile: None,
    backend_job: Job,
) -> None:
    prompt = build_cover_letter_prompt(backend_job, make_cover_letter(backend_job))

    assert "expert cover letter writer" in prompt
    assert "Make only the edits necessary" in prompt
    assert "user's own cover letter" in prompt
    assert "careful backend work, clear communication, and reliable delivery matter" in prompt
    assert "Acme" in prompt
    assert "Backend Engineer" in prompt


def test_cover_letter_docx_round_trips_plain_text(tmp_path) -> None:
    path = tmp_path / "cover-letter.docx"
    text = "Candidate Example\ncandidate@example.com\n\nDear Hiring Team,\n\nThis is the edited cover letter."

    write_cover_letter_docx(path, text)

    assert path.exists()
    assert read_cover_letter_docx(path) == text + "\n"


def test_resume_validator_allows_project_inline_technologies(backend_job: Job) -> None:
    text = """
    Candidate Example
    Experience
    Backend Engineer, WorkCo
    Projects
    DocBridge
    Built Python APIs and FastAPI validation workflows.
    Technologies: Python, FastAPI
    """

    result = validate_resume_text(backend_job, text, page_count=1)

    assert result.passes["no_bottom_technologies_section"] is True


def test_resume_validator_blocks_standalone_bottom_technologies_section(backend_job: Job) -> None:
    text = """
    Candidate Example
    Experience
    Backend Engineer, WorkCo
    Projects
    DocBridge
    Built Python APIs and FastAPI validation workflows.

    Technologies
    Languages: Python, JavaScript
    Frameworks: FastAPI, React
    """

    result = validate_resume_text(backend_job, text, page_count=1)

    assert result.passes["no_bottom_technologies_section"] is False
