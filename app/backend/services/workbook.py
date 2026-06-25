from __future__ import annotations

import json
import csv
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Job
from ..settings import OUTPUT_ROOT
from .document_builder import read_cover_letter_docx
from .processor import latest_artifact, latest_grade
from .time_utils import scan_sort_key


WORKBOOK_PATH = OUTPUT_ROOT / "jobfiller-feedback-loop.xlsx"
JSON_EXPORT_PATH = OUTPUT_ROOT / "jobfiller-feedback-loop.json"
CSV_EXPORT_PATH = OUTPUT_ROOT / "jobfiller-feedback-loop.csv"


WIDTHS = {
    "Company": 18,
    "Title": 36,
    "Location": 18,
    "Key Requirements": 42,
    "Keywords": 36,
    "Salary": 18,
    "Materials Needed": 40,
    "Source URL": 52,
    "Apply URL": 52,
    "Pipeline State": 18,
    "Follow-Up Action": 70,
    "Last Status Email": 56,
    "Last Status Email At": 24,
    "Last Status Email URL": 52,
    "Resume PDF Path": 58,
    "Resume LaTeX Path": 58,
    "Cover Letter Path": 58,
    "Manual Writing Questions": 42,
    "Local LLM Risks": 70,
    "Cover Letter Text": 90,
    "Action": 56,
    "Files": 60,
}


def _read_cover_letter_export_text(path: str) -> str:
    if not path:
        return ""
    cover_path = Path(path)
    if not cover_path.exists():
        return ""
    if cover_path.suffix.lower() == ".docx":
        return read_cover_letter_docx(cover_path)
    return cover_path.read_text(encoding="utf-8")


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _xml_text(value: object) -> str:
    return escape(str(value), {'"': "&quot;"})


def _cell_xml(row_index: int, column_index: int, value: object, *, header: bool = False) -> str:
    reference = f"{_column_name(column_index)}{row_index}"
    style = ' s="1"' if header else ' s="0"'
    if value is None or value == "":
        return f'<c r="{reference}"{style}/>'
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"{style}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{reference}"{style}><v>{value}</v></c>'
    return f'<c r="{reference}" t="inlineStr"{style}><is><t xml:space="preserve">{_xml_text(value)}</t></is></c>'


def _sheet_xml(headers: list[str], rows: list[list[object]]) -> str:
    column_xml = []
    for index, header in enumerate(headers, start=1):
        width = WIDTHS.get(header, 18)
        column_xml.append(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')

    row_xml = [
        '<row r="1">' + "".join(_cell_xml(1, index, header, header=True) for index, header in enumerate(headers, start=1)) + "</row>"
    ]
    for row_index, row in enumerate(rows, start=2):
        cells = [_cell_xml(row_index, index, value) for index, value in enumerate(row, start=1)]
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    last_column = _column_name(max(1, len(headers)))
    last_row = max(1, len(rows) + 1)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="A1:{last_column}{last_row}"/>'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '</sheetView></sheetViews>'
        f'<cols>{"".join(column_xml)}</cols>'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        '</worksheet>'
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font>'
        '</fonts>'
        '<fills count="3">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill>'
        '</fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
        '</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        '</styleSheet>'
    )


def _write_xlsx(path: Path, sheets: list[tuple[str, list[str], list[list[object]]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index, _sheet in enumerate(sheets, start=1)
    )
    sheet_entries = "".join(
        f'<sheet name="{_xml_text(title[:31])}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (title, _headers, _rows) in enumerate(sheets, start=1)
    )
    workbook_rels = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index, _sheet in enumerate(sheets, start=1)
    )
    styles_rel_id = len(sheets) + 1

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            f"{sheet_overrides}</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{sheet_entries}</sheets></workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{workbook_rels}"
            f'<Relationship Id="rId{styles_rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>",
        )
        archive.writestr("xl/styles.xml", _styles_xml())
        archive.writestr(
            "docProps/core.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>JobFiller Export</dc:title></cp:coreProperties>',
        )
        archive.writestr(
            "docProps/app.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            '<Application>JobFiller</Application></Properties>',
        )
        for index, (_title, headers, rows) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(headers, rows))


def export_current_workbook(db: Session, path: Path = WORKBOOK_PATH) -> Path:
    jobs = ordered_jobs(db)

    job_rows = []
    tailoring_rows = []
    cover_rows = []
    checklist_rows = []
    follow_up_rows = []

    for index, job in enumerate(jobs, start=1):
        artifact = latest_artifact(job)
        grade = latest_grade(job)
        open_questions = [q.question_text for q in job.questions if q.status == "OPEN"]
        manual_questions = list(dict.fromkeys([q.question_text for q in job.questions if q.status == "OPEN"]))
        if job.manual_questions:
            manual_questions.insert(0, job.manual_questions)
        risks = []
        if grade and grade.risks_json:
            risks = json.loads(grade.risks_json)
        resume_pdf = artifact.resume_pdf_path if artifact else ""
        resume_tex = artifact.resume_tex_path if artifact else ""
        cover_path = artifact.cover_letter_path if artifact else ""
        cover_text = _read_cover_letter_export_text(cover_path)
        compile_status = artifact.compile_status if artifact else ""

        job_rows.append(
            [
                index,
                job.company,
                job.title,
                job.location,
                job.work_model,
                job.source_url,
                job.apply_url,
                job.status,
                job.application_state,
                job.follow_up_action,
                job.last_status_email_subject,
                job.last_status_email_at.isoformat() if job.last_status_email_at else "",
                job.last_status_email_url,
                job.fit_score,
                grade.overall_grade if grade else "",
                "yes" if grade and grade.ready_to_send else "no",
                job.key_requirements,
                job.keywords,
                job.salary,
                job.materials,
                resume_pdf,
                resume_tex,
                cover_path,
                "\n".join(manual_questions) or "Resume, cover letter, portfolio, or other materials if requested",
                "\n".join(open_questions),
                job.posting_age_text,
                job.posted_at.isoformat() if job.posted_at else "",
                compile_status,
                "\n".join(risks),
            ]
        )
        tailoring_rows.append(
            [
                index,
                job.company,
                job.title,
                job.role_family,
                job.key_requirements,
                job.keywords,
                compile_status,
                resume_pdf,
            ]
        )
        cover_rows.append([index, job.company, job.title, cover_text, cover_path])
        checklist_rows.append(
            [
                index,
                job.company,
                job.title,
                job.follow_up_action
                or "Open apply URL, confirm the role is still accepting applications, upload the tailored resume, and paste or attach the cover letter if requested.",
                f"{resume_pdf}\n{cover_path}",
                "\n".join(
                    item
                    for item in [
                        "\n".join(open_questions),
                        f"Latest status email: {job.last_status_email_subject}" if job.last_status_email_subject else "",
                    ]
                    if item
                )
                or "Review all required form fields manually, including work authorization and sponsorship.",
            ]
        )
        if job.follow_up_action or job.application_state in {"ACTION_NEEDED", "INTERVIEW", "REJECTED"}:
            follow_up_rows.append(
                [
                    index,
                    job.company,
                    job.title,
                    job.application_state,
                    job.follow_up_action,
                    job.last_status_email_subject,
                    job.last_status_email_at.isoformat() if job.last_status_email_at else "",
                    job.last_status_email_url,
                    job.apply_url,
                ]
            )

    sheets = [
        (
            "Jobs",
            [
            "Apply Order",
            "Company",
            "Title",
            "Location",
            "Work Model",
            "Source URL",
            "Apply URL",
            "Status",
            "Pipeline State",
            "Follow-Up Action",
            "Last Status Email",
            "Last Status Email At",
            "Last Status Email URL",
            "Fit Score",
            "Local LLM Grade",
            "Ready To Send",
            "Key Requirements",
            "Keywords",
            "Salary",
            "Materials Needed",
            "Resume PDF Path",
            "Resume LaTeX Path",
            "Cover Letter Path",
            "Manual Writing Questions",
            "Open Questions",
            "Posting Age",
            "Posted At",
            "Compile Status",
            "Local LLM Risks",
            ],
            job_rows,
        ),
        (
            "Resume Tailoring",
            ["Apply Order", "Company", "Title", "Role Family", "Target Requirements", "Target Keywords", "Compile Status", "Resume PDF Path"],
            tailoring_rows,
        ),
        ("Cover Letters", ["Apply Order", "Company", "Title", "Cover Letter Text", "Cover Letter Path"], cover_rows),
        ("Apply Queue", ["Apply Order", "Company", "Title", "Action", "Files", "Manual Checks"], checklist_rows),
        (
            "Follow Ups",
            [
                "Apply Order",
                "Company",
                "Title",
                "Pipeline State",
                "Follow-Up Action",
                "Last Status Email",
                "Last Status Email At",
                "Last Status Email URL",
                "Apply URL",
            ],
            follow_up_rows,
        ),
    ]

    _write_xlsx(path, sheets)
    return path


def current_export_rows(db: Session) -> list[dict[str, object]]:
    jobs = ordered_jobs(db)
    rows: list[dict[str, object]] = []
    for job in jobs:
        artifact = latest_artifact(job)
        grade = latest_grade(job)
        rows.append(
            {
                "id": job.id,
                "company": job.company,
                "title": job.title,
                "location": job.location,
                "work_model": job.work_model,
                "source": job.source,
                "source_url": job.source_url,
                "apply_url": job.apply_url,
                "status": job.status,
                "application_state": job.application_state,
                "follow_up_action": job.follow_up_action,
                "follow_up_due_at": job.follow_up_due_at.isoformat() if job.follow_up_due_at else "",
                "last_status_email_at": job.last_status_email_at.isoformat() if job.last_status_email_at else "",
                "last_status_email_subject": job.last_status_email_subject,
                "last_status_email_url": job.last_status_email_url,
                "fit_score": job.fit_score,
                "grade": grade.overall_grade if grade else "",
                "ready_to_send": grade.ready_to_send if grade else False,
                "key_requirements": job.key_requirements,
                "keywords": job.keywords,
                "salary": job.salary,
                "materials": job.materials,
                "manual_questions": job.manual_questions,
                "posting_age_text": job.posting_age_text,
                "posted_at": job.posted_at.isoformat() if job.posted_at else "",
                "last_seen_at": job.last_seen_at.isoformat() if job.last_seen_at else "",
                "resume_pdf_path": artifact.resume_pdf_path if artifact else "",
                "resume_tex_path": artifact.resume_tex_path if artifact else "",
                "cover_letter_path": artifact.cover_letter_path if artifact else "",
                "open_questions": sum(1 for question in job.questions if question.status == "OPEN"),
                "notes": job.notes,
            }
        )
    return rows


def ordered_jobs(db: Session) -> list[Job]:
    jobs = db.scalars(select(Job)).all()
    return sorted(
        jobs,
        key=lambda job: scan_sort_key(
            job.posted_at,
            job.first_seen_at,
            job.fit_score,
            remote_first=True,
            location=job.location,
            work_model=job.work_model,
        ),
        reverse=True,
    )


def build_tomorrow_checklist(db: Session) -> list[dict[str, object]]:
    checklist: list[dict[str, object]] = []
    for index, job in enumerate(ordered_jobs(db), start=1):
        artifact = latest_artifact(job)
        grade = latest_grade(job)
        open_questions = [q.question_text for q in job.questions if q.status == "OPEN"]
        manual_questions = list(dict.fromkeys(job.manual_questions.splitlines() if job.manual_questions else []))
        if not artifact and not job.follow_up_action and not manual_questions and not open_questions:
            continue
        manual_questions.extend(open_questions)
        checklist.append(
            {
                "apply_order": index,
                "job_id": job.id,
                "company": job.company,
                "title": job.title,
                "status": job.status,
                "application_state": job.application_state,
                "follow_up_action": job.follow_up_action,
                "last_status_email_at": job.last_status_email_at.isoformat() if job.last_status_email_at else "",
                "last_status_email_subject": job.last_status_email_subject,
                "last_status_email_url": job.last_status_email_url,
                "apply_url": job.apply_url,
                "location": job.location,
                "work_model": job.work_model,
                "fit_score": job.fit_score,
                "grade": grade.overall_grade if grade else "",
                "ready_to_send": grade.ready_to_send if grade else False,
                "materials": job.materials,
                "manual_questions": "\n".join(dict.fromkeys(manual_questions)),
                "resume_pdf_path": artifact.resume_pdf_path if artifact else "",
                "cover_letter_path": artifact.cover_letter_path if artifact else "",
                "resume_tex_path": artifact.resume_tex_path if artifact else "",
                "posting_age_text": job.posting_age_text,
                "posted_at": job.posted_at.isoformat() if job.posted_at else "",
                "first_seen_at": job.first_seen_at.isoformat(),
            }
        )
    return checklist


def export_current_json_csv(db: Session) -> dict[str, Path]:
    rows = current_export_rows(db)
    JSON_EXPORT_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    if rows:
        with CSV_EXPORT_PATH.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        CSV_EXPORT_PATH.write_text("", encoding="utf-8")
    return {"json": JSON_EXPORT_PATH, "csv": CSV_EXPORT_PATH}
