from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..settings import OUTPUT_ROOT, candidate_slug
from ..models import Artifact, Job
from .document_builder import build_pdf, build_tex, make_cover_letter, read_cover_letter_docx, write_cover_letter_docx
from .local_llm import generate_cover_letter
from .text_utils import slugify


ARTIFACT_ROOT = OUTPUT_ROOT / "app_artifacts"
RESUME_ROOT = OUTPUT_ROOT / "resumes"
COVER_ROOT = OUTPUT_ROOT / "cover_letters"
TEXT_ARTIFACT_KINDS = {"cover-letter", "latex"}


def try_compile_tex(tex_path: Path, out_dir: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["tectonic", "--outdir", str(out_dir), str(tex_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except FileNotFoundError:
        return False, "tectonic not installed"
    except Exception as exc:
        return False, str(exc)
    output = "\n".join(part for part in [result.stdout, result.stderr] if part).strip()
    return result.returncode == 0, output[-2000:]


def _safe_copy(source: Path, destination: Path) -> None:
    src = source.resolve()
    dst = destination.resolve()
    if src != dst:
        shutil.copyfile(source, destination)


def _revision_dir(job: Job, revision: int) -> Path:
    company_slug = slugify(job.company or "company")
    role_slug = slugify(job.title or "role")
    return ARTIFACT_ROOT / f"job-{job.id:04d}-{company_slug}-{role_slug}" / f"rev-{revision:03d}"


def _job_output_paths(job: Job) -> tuple[Path, Path, Path, Path]:
    company_slug = slugify(job.company or "company")
    role_slug = slugify(job.title or "role")
    person_slug = candidate_slug()
    job_suffix = f"{company_slug}-{role_slug}"
    if job.id:
        job_suffix = f"{job_suffix}-job-{job.id:04d}"
    latex_root = RESUME_ROOT / job_suffix
    pdf_path = RESUME_ROOT / f"{person_slug}-resume-{job_suffix}.pdf"
    cover_path = COVER_ROOT / f"{person_slug}-cover-letter-{job_suffix}.docx"
    tex_path = latex_root / "main.tex"
    return tex_path, pdf_path, cover_path, latex_root


def _write_cover_letter(path: Path, content: str) -> None:
    if path.suffix.lower() == ".docx":
        write_cover_letter_docx(path, content)
    else:
        path.write_text(content, encoding="utf-8")


def _read_cover_letter(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return read_cover_letter_docx(path)
    return path.read_text(encoding="utf-8")


def _ensure_pdf(
    job: Job,
    tex_path: Path,
    pdf_path: Path,
    out_dir: Path,
) -> tuple[str, Path]:
    compiled, compile_log = try_compile_tex(tex_path, out_dir)
    compiled_pdf = out_dir / "main.pdf"
    if compiled and compiled_pdf.exists():
        _safe_copy(compiled_pdf, pdf_path)
        return f"tectonic compile succeeded: {compile_log}", pdf_path
    build_pdf(job, pdf_path)
    return f"tectonic failed; fallback PDF generated: {compile_log}", pdf_path


def generate_artifacts(db: Session, job: Job) -> Artifact:
    latest_revision = db.scalar(select(Artifact.revision).where(Artifact.job_id == job.id).order_by(Artifact.revision.desc()))
    revision = (latest_revision or 0) + 1
    out_dir = _revision_dir(job, revision)
    resume_dir = out_dir / "resume"
    cover_dir = out_dir / "cover_letter"
    resume_dir.mkdir(parents=True, exist_ok=True)
    cover_dir.mkdir(parents=True, exist_ok=True)
    RESUME_ROOT.mkdir(parents=True, exist_ok=True)
    COVER_ROOT.mkdir(parents=True, exist_ok=True)

    tex_path, pdf_path, cover_path, _ = _job_output_paths(job)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    cover_path.parent.mkdir(parents=True, exist_ok=True)

    # Revision storage keeps a full history in app_artifacts and also refreshes latest delivery paths.
    revision_tex_path = resume_dir / "main.tex"
    person_slug = candidate_slug()
    revision_pdf_path = out_dir / f"{person_slug}-resume-{slugify(job.company or 'company')}-rev-{revision:03d}.pdf"
    rendered_tex = build_tex(job)
    tex_path.write_text(rendered_tex, encoding="utf-8")
    revision_tex_path.write_text(rendered_tex, encoding="utf-8")

    compile_status, _ = _ensure_pdf(job, revision_tex_path, revision_pdf_path, resume_dir)
    _safe_copy(revision_pdf_path, pdf_path)

    # Keep a revision-correct cover letter copy for auditability and rollback.
    revision_cover_path = cover_dir / f"{person_slug}-cover-letter-{slugify(job.company or 'company')}-rev-{revision:03d}.docx"
    fallback_cover_letter = make_cover_letter(job)
    _write_cover_letter(revision_cover_path, generate_cover_letter(job, fallback_cover_letter))
    _safe_copy(revision_cover_path, cover_path)

    # Keep an always-accessible latest .tex artifact path for the workflow.
    _safe_copy(revision_tex_path, tex_path)
    artifact = Artifact(
        job_id=job.id,
        revision=revision,
        resume_tex_path=str(tex_path),
        resume_pdf_path=str(pdf_path),
        cover_letter_path=str(cover_path),
        workbook_path="",
        compile_status=compile_status,
    )
    db.add(artifact)
    db.flush()
    return artifact


def artifact_text_path(artifact: Artifact, kind: str) -> Path:
    if kind == "cover-letter":
        return Path(artifact.cover_letter_path)
    if kind == "latex":
        return Path(artifact.resume_tex_path)
    raise ValueError(f"Unsupported editable artifact kind: {kind}")


def read_artifact_text(artifact: Artifact, kind: str) -> tuple[Path, str]:
    file_path = artifact_text_path(artifact, kind)
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    if kind == "cover-letter":
        return file_path, _read_cover_letter(file_path)
    return file_path, file_path.read_text(encoding="utf-8")


def update_artifact_text(db: Session, artifact: Artifact, kind: str, content: str) -> Artifact:
    if kind not in TEXT_ARTIFACT_KINDS:
        raise ValueError(f"Unsupported editable artifact kind: {kind}")

    job = artifact.job
    latest_revision = db.scalar(select(Artifact.revision).where(Artifact.job_id == job.id).order_by(Artifact.revision.desc()))
    revision = (latest_revision or 0) + 1
    out_dir = _revision_dir(job, revision)
    resume_dir = out_dir / "resume"
    cover_dir = out_dir / "cover_letter"
    resume_dir.mkdir(parents=True, exist_ok=True)
    cover_dir.mkdir(parents=True, exist_ok=True)
    RESUME_ROOT.mkdir(parents=True, exist_ok=True)
    COVER_ROOT.mkdir(parents=True, exist_ok=True)
    tex_path, pdf_path, cover_path, _ = _job_output_paths(job)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    cover_path.parent.mkdir(parents=True, exist_ok=True)

    revision_tex_path = resume_dir / "main.tex"
    person_slug = candidate_slug()
    revision_cover_path = cover_dir / f"{person_slug}-cover-letter-{slugify(job.company or 'company')}-rev-{revision:03d}.docx"
    revision_pdf_path = out_dir / f"{person_slug}-resume-{slugify(job.company or 'company')}-rev-{revision:03d}.pdf"

    if kind == "latex":
        revision_tex_path.write_text(content, encoding="utf-8")
        _safe_copy(revision_tex_path, tex_path)
        if artifact.cover_letter_path and Path(artifact.cover_letter_path).exists():
            _write_cover_letter(revision_cover_path, _read_cover_letter(Path(artifact.cover_letter_path)))
        else:
            _write_cover_letter(revision_cover_path, "")
        compile_status, _ = _ensure_pdf(job, revision_tex_path, revision_pdf_path, resume_dir)
        _safe_copy(revision_pdf_path, pdf_path)
        compile_status = f"{compile_status} (manual latex edit)"
    else:
        _write_cover_letter(revision_cover_path, content)
        _safe_copy(revision_cover_path, cover_path)
        if artifact.resume_tex_path and Path(artifact.resume_tex_path).exists():
            _safe_copy(Path(artifact.resume_tex_path), revision_tex_path)
            _safe_copy(Path(artifact.resume_tex_path), tex_path)
        else:
            revision_tex = build_tex(job)
            revision_tex_path.write_text(revision_tex, encoding="utf-8")
            _safe_copy(revision_tex_path, tex_path)

        if artifact.resume_pdf_path and Path(artifact.resume_pdf_path).exists():
            _safe_copy(Path(artifact.resume_pdf_path), revision_pdf_path)
            _safe_copy(Path(artifact.resume_pdf_path), pdf_path)
            compile_status = artifact.compile_status or "copied prior compiled PDF"
        else:
            compile_status, _ = _ensure_pdf(job, revision_tex_path, revision_pdf_path, resume_dir)
            _safe_copy(revision_pdf_path, pdf_path)
            compile_status = f"{compile_status} (manual cover-letter edit)"

    next_artifact = Artifact(
        job_id=job.id,
        revision=revision,
        resume_tex_path=str(tex_path),
        resume_pdf_path=str(pdf_path),
        cover_letter_path=str(cover_path),
        workbook_path=artifact.workbook_path,
        compile_status=compile_status,
    )
    db.add(next_artifact)
    db.flush()
    return next_artifact
