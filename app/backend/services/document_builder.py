from __future__ import annotations

import textwrap
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from ..settings import candidate_profile
from ..models import Job
from .text_utils import escape_tex, slugify, split_list


LETTER = (612.0, 792.0)


DEFAULT_EXPERIENCE = [
    {
        "title": "Add Your Experience",
        "company": "Configure Profile",
        "location": "",
        "dates": "",
        "bullets": [
            "Add your resume, work history, projects, and measurable impact in Settings or Profile Facts before sending applications.",
            "JobFiller will tailor this section to each role using only the profile facts and source materials you provide.",
        ],
    }
]

DEFAULT_PROJECTS = [
    {
        "name": "Configured Candidate Project",
        "description": "Add project descriptions in Settings so JobFiller can tailor truthful role-specific evidence.",
        "bullets": [
            "Replace this placeholder with a real project, technical scope, and supported outcomes.",
            "The generator blocks or asks questions when required experience is missing instead of inventing facts.",
        ],
    }
]


def _pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class SimplePdfCanvas:
    def __init__(self, path: Path, pagesize: tuple[float, float] = LETTER) -> None:
        self.path = path
        self.width, self.height = pagesize
        self.font_name = "Helvetica"
        self.font_size = 10.0
        self.title = ""
        self.author = ""
        self.commands: list[str] = []

    def setTitle(self, title: str) -> None:  # noqa: N802 - mirrors common PDF canvas APIs.
        self.title = title

    def setAuthor(self, author: str) -> None:  # noqa: N802 - mirrors common PDF canvas APIs.
        self.author = author

    def setFont(self, name: str, size: float) -> None:  # noqa: N802 - mirrors common PDF canvas APIs.
        self.font_name = "Helvetica-Bold" if "bold" in name.lower() else "Helvetica"
        self.font_size = float(size)

    def _font_ref(self) -> str:
        return "F2" if self.font_name == "Helvetica-Bold" else "F1"

    def _text_width(self, text: str) -> float:
        return len(text) * self.font_size * 0.48

    def drawString(self, x: float, y: float, text: str) -> None:  # noqa: N802 - mirrors common PDF canvas APIs.
        self.commands.append(
            f"BT /{self._font_ref()} {self.font_size:.2f} Tf {x:.2f} {y:.2f} Td ({_pdf_text(text)}) Tj ET"
        )

    def drawRightString(self, x: float, y: float, text: str) -> None:  # noqa: N802 - mirrors common PDF canvas APIs.
        self.drawString(x - self._text_width(text), y, text)

    def drawCentredString(self, x: float, y: float, text: str) -> None:  # noqa: N802 - mirrors common PDF canvas APIs.
        self.drawString(x - (self._text_width(text) / 2), y, text)

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.commands.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def save(self) -> None:
        content = "\n".join(self.commands).encode("latin-1", errors="replace")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                "/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
            ).encode("ascii"),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
            b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream",
            (
                f"<< /Title ({_pdf_text(self.title)}) /Author ({_pdf_text(self.author)}) "
                "/Creator (JobFiller) >>"
            ).encode("latin-1", errors="replace"),
        ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("wb") as handle:
            handle.write(b"%PDF-1.4\n")
            offsets = [0]
            for number, payload in enumerate(objects, start=1):
                offsets.append(handle.tell())
                handle.write(f"{number} 0 obj\n".encode("ascii"))
                handle.write(payload)
                handle.write(b"\nendobj\n")
            xref_offset = handle.tell()
            handle.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
            handle.write(b"0000000000 65535 f \n")
            for offset in offsets[1:]:
                handle.write(f"{offset:010d} 00000 n \n".encode("ascii"))
            handle.write(
                (
                    f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 7 0 R >>\n"
                    f"startxref\n{xref_offset}\n%%EOF\n"
                ).encode("ascii")
            )


def profile_ready(profile: dict[str, Any] | None = None) -> bool:
    profile = profile or candidate_profile()
    return bool(str(profile.get("name") or "").strip() and str(profile.get("email") or "").strip())


def profile_slug(profile: dict[str, Any] | None = None) -> str:
    profile = profile or candidate_profile()
    return slugify(str(profile.get("name") or "candidate"), "candidate")


def _profile() -> dict[str, Any]:
    return candidate_profile()


def _contact_parts(profile: dict[str, Any]) -> list[str]:
    parts = [
        profile.get("location"),
        profile.get("email"),
        profile.get("phone"),
        profile.get("website"),
        profile.get("linkedin"),
    ]
    return [str(part).strip() for part in parts if str(part or "").strip()]


def _education(profile: dict[str, Any]) -> list[dict[str, Any]]:
    items = profile.get("education") or []
    return items if isinstance(items, list) and items else []


def _experience(profile: dict[str, Any]) -> list[dict[str, Any]]:
    items = profile.get("experience") or []
    return items if isinstance(items, list) and items else DEFAULT_EXPERIENCE


def _projects(profile: dict[str, Any]) -> list[dict[str, Any]]:
    items = profile.get("projects") or []
    return items if isinstance(items, list) and items else DEFAULT_PROJECTS


def _skills(profile: dict[str, Any], job: Job) -> list[str]:
    skills = split_list(profile.get("skills"))
    job_keywords = split_list(job.keywords)
    merged = []
    for item in [*job_keywords, *skills]:
        if item and item.lower() not in {existing.lower() for existing in merged}:
            merged.append(item)
    return merged[:28]


def _job_keywords(job: Job) -> list[str]:
    return split_list(job.keywords) or split_list(job.key_requirements)[:6]


def _keyword_terms(job: Job) -> list[str]:
    terms: list[str] = []
    for item in [*_job_keywords(job), *split_list(job.key_requirements), str(job.title or ""), str(job.role_family or "")]:
        for term in str(item).replace("/", " ").replace("-", " ").split():
            clean = term.strip(" ,.;:()[]{}").lower()
            if len(clean) > 2 and clean not in terms:
                terms.append(clean)
    return terms


def _prioritized_texts(items: list[str], job: Job, limit: int) -> list[str]:
    terms = _keyword_terms(job)
    indexed = list(enumerate(item for item in items if str(item).strip()))

    def score(entry: tuple[int, str]) -> tuple[int, int]:
        index, text = entry
        lower = text.lower()
        return (sum(1 for term in terms if term in lower), -index)

    return [text for _, text in sorted(indexed, key=score, reverse=True)[:limit]]


def _prioritized_projects(profile: dict[str, Any], job: Job) -> list[dict[str, Any]]:
    keywords = " ".join(_keyword_terms(job)).lower()
    projects = list(_projects(profile))

    def score(project: dict[str, Any]) -> int:
        text = " ".join(
            [
                str(project.get("name") or ""),
                str(project.get("description") or ""),
                " ".join(split_list(project.get("skills"))),
                " ".join(str(item) for item in project.get("bullets") or []),
            ]
        ).lower()
        return sum(1 for keyword in keywords.split() if len(keyword) > 2 and keyword in text)

    return sorted(projects, key=score, reverse=True)[:2]


def _project_technologies(project: dict[str, Any]) -> list[str]:
    return split_list(project.get("skills"))[:8]


def _source_cover_letter(profile: dict[str, Any]) -> str:
    for key in ("cover_letter", "cover_letter_sample", "base_cover_letter", "source_cover_letter"):
        value = str(profile.get(key) or "").strip()
        if value:
            return value
    return ""


def _profile_prompt_summary(profile: dict[str, Any]) -> str:
    parts = [
        f"Name: {profile.get('name') or ''}",
        f"Summary: {profile.get('summary') or ''}",
        f"Skills: {', '.join(split_list(profile.get('skills'))[:28])}",
    ]
    experience = []
    for item in _experience(profile)[:4]:
        label = ", ".join(str(item.get(key) or "").strip() for key in ("title", "company") if str(item.get(key) or "").strip())
        bullets = "; ".join(str(bullet).strip() for bullet in (item.get("bullets") or [])[:4] if str(bullet).strip())
        if label or bullets:
            experience.append(f"{label}: {bullets}".strip(": "))
    projects = []
    for project in _projects(profile)[:4]:
        label = str(project.get("name") or "").strip()
        description = str(project.get("description") or "").strip()
        bullets = "; ".join(str(bullet).strip() for bullet in (project.get("bullets") or [])[:3] if str(bullet).strip())
        if label or description or bullets:
            projects.append(f"{label}: {description} {bullets}".strip(": "))
    if experience:
        parts.append("Experience: " + " | ".join(experience))
    if projects:
        parts.append("Projects: " + " | ".join(projects))
    return "\n".join(part for part in parts if part.strip())


def build_cover_letter_prompt(job: Job, fallback_draft: str) -> str:
    profile = _profile()
    source_cover_letter = _source_cover_letter(profile)
    return textwrap.dedent(
        f"""\
        You are an expert cover letter writer tailoring a cover letter for a real job application.

        Rules:
        - Use the user's own cover letter as the authoritative source for voice, structure, and personal information.
        - Preserve the information from the user's own cover letter unless it is clearly irrelevant to this job.
        - Make only the edits necessary to align the letter with this company, role, and requirements.
        - Do not invent employment, projects, metrics, credentials, location preferences, work authorization, or company facts.
        - Keep the result direct, human, and specific. Avoid over-polished sales language.
        - Return only the final cover letter text, with normal paragraphs and no Markdown.

        Job:
        Company: {job.company or ""}
        Role: {job.title or ""}
        Requirements: {job.key_requirements or ""}
        Keywords: {job.keywords or ""}
        Role family: {job.role_family or ""}

        Candidate facts:
        {_profile_prompt_summary(profile)}

        User's own cover letter:
        ---
        {source_cover_letter or "No source cover letter has been configured. Use the candidate facts and fallback draft without inventing details."}
        ---

        Fallback draft to edit if useful:
        ---
        {fallback_draft.strip()}
        ---
        """
    ).strip()


def _itemize(items: list[str] | tuple[str, ...]) -> str:
    return "\n".join(f"        \\item {escape_tex(item)}" for item in items if str(item).strip())


def _heading_line(left: str, right: str = "") -> str:
    if right:
        return rf"\begin{{twocolentry}}{{{escape_tex(right)}}}\textbf{{{escape_tex(left)}}}\end{{twocolentry}}"
    return rf"\begin{{onecolentry}}\textbf{{{escape_tex(left)}}}\end{{onecolentry}}"


def _lower_first(value: str) -> str:
    value = value.strip()
    return value[:1].lower() + value[1:] if value else value


def _sentence_body(value: str) -> str:
    return value.strip().rstrip(".")


def _article_for(value: str) -> str:
    first = value.strip()[:1].lower()
    return "an" if first in {"a", "e", "i", "o", "u"} else "a"


def _href_contact(kind: str, value: str) -> str:
    value = value.strip()
    if kind == "email":
        href = f"mailto:{value}"
        return rf"\mbox{{\hrefWithoutArrow{{{escape_tex(href)}}}{{{escape_tex(value)}}}}}%"
    if kind == "phone":
        tel = "".join(ch for ch in value if ch.isdigit() or ch == "+")
        href = f"tel:{tel}" if tel else value
        return rf"\mbox{{\hrefWithoutArrow{{{escape_tex(href)}}}{{{escape_tex(value)}}}}}%"
    if kind in {"website", "linkedin"}:
        href = value if value.startswith(("http://", "https://")) else f"https://{value}"
        return rf"\mbox{{\hrefWithoutArrow{{{escape_tex(href)}}}{{{escape_tex(value)}}}}}%"
    return rf"\mbox{{{escape_tex(value)}}}%"


def _contact_line(profile: dict[str, Any]) -> str:
    entries: list[str] = []
    for key in ["location", "email", "phone", "website", "linkedin"]:
        value = str(profile.get(key) or "").strip()
        if value:
            entries.append(_href_contact(key, value))
    if not entries:
        entries.append(r"\mbox{Add contact information in Settings}%")
    separator = "\n        \\kern 5.0 pt%\n        \\AND%\n        \\kern 5.0 pt%\n        "
    return "        " + separator.join(entries)


def _project_block(project: dict[str, Any], job: Job) -> str:
    name_text = str(project.get("name") or "Project").strip()
    description = str(project.get("description") or "").strip()
    bullets = [str(bullet) for bullet in project.get("bullets") or [] if str(bullet).strip()]
    if not bullets:
        bullets = ["Add concise, truthful technical bullets for this project."]
    technologies = _project_technologies(project)
    tech_line = (
        "\n" + rf"\textbf{{Technologies:}} {escape_tex(', '.join(technologies))}"
        if technologies
        else ""
    )
    return "\n".join(
        [
            _heading_line(name_text),
            "",
            r"\vspace{0.16 cm}",
            r"\begin{onecolentry}",
            escape_tex(description) if description else "",
            r"\begin{highlights}",
            _itemize(_prioritized_texts(bullets, job, 3)),
            r"\end{highlights}",
            tech_line,
            r"\end{onecolentry}",
        ]
    )


def build_tex(job: Job) -> str:
    profile = _profile()
    name = str(profile.get("name") or "Your Name").strip()
    contact_line = _contact_line(profile)

    education_blocks = []
    for item in _education(profile):
        school = str(item.get("school") or item.get("institution") or "").strip()
        degree = str(item.get("degree") or "").strip()
        detail = ", ".join(part for part in [school, degree] if part)
        if detail:
            education_blocks.append(_heading_line(detail, str(item.get("dates") or "")))
    if not education_blocks:
        education_blocks.append(_heading_line("Add education in Settings", ""))

    experience_blocks = []
    for item in _experience(profile):
        title = str(item.get("title") or "Experience").strip()
        company = str(item.get("company") or "").strip()
        location = str(item.get("location") or "").strip()
        dates = str(item.get("dates") or "").strip()
        label = ", ".join(part for part in [title, company] if part)
        suffix = f" -- {location}" if location else ""
        bullets = [str(bullet) for bullet in item.get("bullets") or [] if str(bullet).strip()]
        if not bullets:
            bullets = ["Add concise, truthful impact bullets for this experience."]
        experience_blocks.append(
            "\n".join(
                [
                    _heading_line(f"{label}{suffix}", dates),
                    "",
                    r"\vspace{0.10 cm}",
                    r"\begin{onecolentry}",
                    r"\begin{highlights}",
                    _itemize(_prioritized_texts(bullets, job, 3)),
                    r"\end{highlights}",
                    r"\end{onecolentry}",
                ]
            )
        )

    project_blocks = [_project_block(project, job) for project in _prioritized_projects(profile, job)]

    return rf"""\documentclass[10pt, letterpaper]{{article}}

% Packages:
\usepackage[
    ignoreheadfoot,
    top=2 cm,
    bottom=2 cm,
    left=2 cm,
    right=2 cm,
    footskip=1.0 cm,
]{{geometry}}
\usepackage{{titlesec}}
\usepackage{{tabularx}}
\usepackage{{array}}
\usepackage[dvipsnames]{{xcolor}}
\definecolor{{primaryColor}}{{RGB}}{{0, 0, 0}}
\usepackage{{enumitem}}
\usepackage{{fontawesome5}}
\usepackage{{amsmath}}
\usepackage[
    pdftitle={{{escape_tex(name)}'s CV}},
    pdfauthor={{{escape_tex(name)}}},
    pdfcreator={{LaTeX with RenderCV}},
    colorlinks=true,
    urlcolor=primaryColor
]{{hyperref}}
\usepackage[pscoord]{{eso-pic}}
\usepackage{{calc}}
\usepackage{{bookmark}}
\usepackage{{lastpage}}
\usepackage{{changepage}}
\usepackage{{etoolbox}}
\usepackage{{paracol}}
\usepackage{{ifthen}}
\usepackage{{needspace}}
\usepackage{{iftex}}

% Ensure that generated PDF is machine readable/ATS parsable:
\ifPDFTeX
    \input{{glyphtounicode}}
    \pdfgentounicode=1
    \usepackage[T1]{{fontenc}}
    \usepackage[utf8]{{inputenc}}
    \usepackage{{lmodern}}
\fi

\usepackage{{charter}}

% Some settings:
\raggedright
\AtBeginEnvironment{{adjustwidth}}{{\partopsep0pt}}
\pagestyle{{empty}}
\setcounter{{secnumdepth}}{{0}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\topskip}}{{0pt}}
\setlength{{\columnsep}}{{0.15cm}}
\pagenumbering{{gobble}}
\titleformat{{\section}}{{\needspace{{4\baselineskip}}\bfseries\large}}{{}}{{0pt}}{{}}[\vspace{{1pt}}\titlerule]
\titlespacing{{\section}}{{-1pt}}{{0.3 cm}}{{0.2 cm}}
\renewcommand\labelitemi{{$\vcenter{{\hbox{{\small$\bullet$}}}}$}}
\newenvironment{{highlights}}{{
    \begin{{itemize}}[
        topsep=0.10 cm,
        parsep=0.10 cm,
        partopsep=0pt,
        itemsep=0pt,
        leftmargin=0 cm + 10pt
    ]
}}{{
    \end{{itemize}}
}}
\newenvironment{{highlightsforbulletentries}}{{
    \begin{{itemize}}[
        topsep=0.10 cm,
        parsep=0.10 cm,
        partopsep=0pt,
        itemsep=0pt,
        leftmargin=10pt
    ]
}}{{
    \end{{itemize}}
}}
\newenvironment{{onecolentry}}{{
    \begin{{adjustwidth}}{{0 cm + 0.00001 cm}}{{0 cm + 0.00001 cm}}
}}{{
    \end{{adjustwidth}}
}}
\newenvironment{{twocolentry}}[2][]{{\onecolentry
    \def\secondColumn{{#2}}
    \setcolumnwidth{{\fill, 4.5 cm}}
    \begin{{paracol}}{{2}}
}}{{
    \switchcolumn \raggedleft \secondColumn
    \end{{paracol}}
    \endonecolentry
}}
\newenvironment{{threecolentry}}[3][]{{\onecolentry
    \def\thirdColumn{{#3}}
    \setcolumnwidth{{, \fill, 4.5 cm}}
    \begin{{paracol}}{{3}}
    {{\raggedright #2}} \switchcolumn
}}{{
    \switchcolumn \raggedleft \thirdColumn
    \end{{paracol}}
    \endonecolentry
}}
\newenvironment{{header}}{{
    \setlength{{\topsep}}{{0pt}}\par\kern\topsep\centering\linespread{{1.5}}
}}{{
    \par\kern\topsep
}}
\newcommand{{\placelastupdatedtext}}{{%
  \AddToShipoutPictureFG*{{%
    \put(
        \LenToUnit{{\paperwidth-2 cm-0 cm+0.05cm}},
        \LenToUnit{{\paperheight-1.0 cm}}
    ){{\vtop{{{{\null}}\makebox[0pt][c]{{%
        \small\color{{gray}}\textit{{Last updated in April 2026}}\hspace{{\widthof{{Last updated in April 2026}}}}
    }}}}}}%
  }}%
}}%
\let\hrefWithoutArrow\href

\begin{{document}}
    \newcommand{{\AND}}{{\unskip
        \cleaders\copy\ANDbox\hskip\wd\ANDbox
        \ignorespaces
    }}
    \newsavebox\ANDbox
    \sbox\ANDbox{{$|$}}

    \begin{{header}}
        \fontsize{{25 pt}}{{25 pt}}\selectfont {escape_tex(name)}

        \vspace{{5 pt}}

        \normalsize
{contact_line}
    \end{{header}}

    \vspace{{5 pt - 0.3 cm}}

\section{{Education}}
{chr(10).join(education_blocks)}

\section{{Experience}}
{chr(10).join(experience_blocks)}

\section{{Projects}}
{chr(10).join(project_blocks)}

\end{{document}}
"""


def make_cover_letter(job: Job) -> str:
    profile = _profile()
    name = str(profile.get("name") or "Your Name").strip()
    email = str(profile.get("email") or "add-your-email-in-settings").strip()
    phone = str(profile.get("phone") or "").strip()
    website = str(profile.get("website") or "").strip()
    strongest_project = _prioritized_projects(profile, job)[0]
    project_name = str(strongest_project.get("name") or "my strongest relevant project")
    project_description = str(strongest_project.get("description") or "a project configured in my candidate profile")
    project_bullets = [str(item) for item in strongest_project.get("bullets") or [] if str(item).strip()]
    project_proof = _prioritized_texts(project_bullets, job, 1)
    experience = _experience(profile)
    experience_proof = ""
    if experience:
        selected_experience = experience[0]
        exp_bullets = [str(item) for item in selected_experience.get("bullets") or [] if str(item).strip()]
        selected_bullets = _prioritized_texts(exp_bullets, job, 1)
        if selected_bullets:
            title = str(selected_experience.get("title") or "").strip()
            company = str(selected_experience.get("company") or "").strip()
            label = " at ".join(part for part in [title, company] if part) or "my prior experience"
            experience_proof = f"As {label}, I {selected_bullets[0][0].lower() + selected_bullets[0][1:]}"
    requirements = split_list(job.key_requirements)[:3] or split_list(job.keywords)[:3] or [str(job.title or "the role")]
    requirement_phrase = ", ".join(requirements)
    keywords = ", ".join(_job_keywords(job)[:4])
    contact = " | ".join(part for part in [email, phone, website] if part)
    project_body = _lower_first(_sentence_body(project_description))
    if project_body:
        needs_article = not project_body.startswith(("a ", "an ", "the ", "my "))
        article = f"{_article_for(project_body)} " if needs_article else ""
        project_sentence = f"{project_name} is {article}{project_body}."
    else:
        project_sentence = f"In {project_name}, I focused on the kind of technical execution this role needs."
    if project_proof:
        project_sentence += f" I also {_lower_first(project_proof[0])}"
    experience_sentence = experience_proof or (
        "My prior work has centered on evaluating technical quality, documenting edge cases, and building reliable workflows from real requirements."
    )

    return textwrap.dedent(
        f"""\
        {name}
        {contact}

        Dear {job.company or "Hiring"} Hiring Team,

        I am applying for the {job.title or "open role"} role at {job.company or "your team"} because it lines up with the kind of engineering work I want to keep doing: backend services, product-facing systems, and careful technical execution. The posting emphasizes requirements like {requirement_phrase}, and my strongest experience is in building and evaluating systems where reliability, maintainability, and clear data flow matter.

        {project_sentence} That work is especially relevant to a role focused on {keywords or "the listed technical requirements"} because it gave me practical experience turning messy inputs into structured, testable workflows.

        {experience_sentence} I have also worked across Python, Java, JavaScript, React, TypeScript, testing, analytics migration, and compliance-sensitive web workflows, so I am comfortable learning a codebase while still paying attention to the details that keep software usable in production.

        I would be glad to bring that mix of backend focus, AI/product experience, and careful implementation judgment to {job.company or "your team"}.

        Sincerely,
        {name}
        """
    ).strip() + "\n"


def _docx_paragraph_xml(text: str) -> str:
    from xml.sax.saxutils import escape

    if not text:
        return "<w:p/>"
    escaped = escape(text)
    return f'<w:p><w:r><w:t xml:space="preserve">{escaped}</w:t></w:r></w:p>'


def write_cover_letter_docx(path: Path, text: str) -> None:
    paragraphs = text.strip().splitlines()
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(_docx_paragraph_xml(line.strip()) for line in paragraphs)
        + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" '
        'w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)


def read_cover_letter_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        document = archive.read("word/document.xml")
    root = ElementTree.fromstring(document)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        paragraphs.append("".join(texts))
    return "\n".join(paragraphs).strip() + "\n"


def draw_wrapped(c: SimplePdfCanvas, text: str, x: float, y: float, chars: int, size: float = 8.2, leading: float = 9.1) -> float:
    c.setFont("Helvetica", size)
    for line in textwrap.wrap(text, width=chars, break_long_words=False, break_on_hyphens=False):
        c.drawString(x, y, line)
        y -= leading
    return y


def build_pdf(job: Job, pdf_path: Path) -> None:
    profile = _profile()
    name = str(profile.get("name") or "Your Name").strip()
    contact_line = " | ".join(_contact_parts(profile)) or "Add contact information in Settings"

    c = SimplePdfCanvas(pdf_path, pagesize=LETTER)
    c.setTitle(f"{name} Resume - {job.company}")
    c.setAuthor(name)
    width, height = LETTER
    left, right = 36, 36
    y = height - 30

    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, y, name)
    y -= 14
    c.setFont("Helvetica", 8.7)
    c.drawCentredString(width / 2, y, contact_line)
    y -= 14

    def section(title: str) -> None:
        nonlocal y
        y -= 5
        c.setFont("Helvetica-Bold", 10.2)
        c.drawString(left, y, title)
        c.line(left, y - 2, width - right, y - 2)
        y -= 11

    def bullet(text: str) -> None:
        nonlocal y
        c.setFont("Helvetica", 8.2)
        c.drawString(left + 6, y, "-")
        y = draw_wrapped(c, text, left + 16, y, 119)
        y -= 1

    section("Education")
    for item in _education(profile) or [{"school": "Add education in Settings", "degree": ""}]:
        c.setFont("Helvetica-Bold", 8.8)
        c.drawString(left, y, str(item.get("school") or item.get("institution") or "Education"))
        c.setFont("Helvetica", 8.8)
        c.drawString(left + 180, y, str(item.get("degree") or ""))
        y -= 10

    section("Experience")
    for item in _experience(profile):
        title = ", ".join(part for part in [str(item.get("title") or ""), str(item.get("company") or "")] if part)
        c.setFont("Helvetica-Bold", 10.0)
        c.drawString(left, y, title or "Experience")
        c.setFont("Helvetica", 8.3)
        c.drawRightString(width - right, y, str(item.get("dates") or ""))
        y -= 10
        for text in [str(bullet_text) for bullet_text in item.get("bullets") or []][:3]:
            bullet(text)

    section("Projects")
    for project in _prioritized_projects(profile, job):
        c.setFont("Helvetica-Bold", 10.2)
        c.drawString(left, y, str(project.get("name") or "Project"))
        y -= 9
        y = draw_wrapped(c, str(project.get("description") or ""), left, y, 126, 8.1, 9)
        for text in [str(bullet_text) for bullet_text in project.get("bullets") or []][:3]:
            bullet(text)
        y -= 6

    skills = ", ".join(_skills(profile, job))
    c.save()
