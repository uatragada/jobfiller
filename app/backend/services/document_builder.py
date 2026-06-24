from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

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


def _prioritized_projects(profile: dict[str, Any], job: Job) -> list[dict[str, Any]]:
    keywords = " ".join(_job_keywords(job)).lower()
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

    return sorted(projects, key=score, reverse=True)[:3]


def _itemize(items: list[str] | tuple[str, ...]) -> str:
    return "\n".join(f"        \\item {escape_tex(item)}" for item in items if str(item).strip())


def _heading_line(left: str, right: str = "") -> str:
    if right:
        return rf"\begin{{twocolentry}}{{{escape_tex(right)}}}\textbf{{{escape_tex(left)}}}\end{{twocolentry}}"
    return rf"\begin{{onecolentry}}\textbf{{{escape_tex(left)}}}\end{{onecolentry}}"


def build_tex(job: Job) -> str:
    profile = _profile()
    name = str(profile.get("name") or "Your Name").strip()
    contact_parts = _contact_parts(profile)
    contact_line = "    \\AND%\n    ".join(rf"\mbox{{{escape_tex(part)}}}%" for part in contact_parts)
    if contact_line:
        contact_line = f"    {contact_line}"
    else:
        contact_line = r"    \mbox{Add contact information in Settings}%"

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
                    r"\begin{onecolentry}",
                    r"\begin{highlights}",
                    _itemize(bullets[:4]),
                    r"\end{highlights}",
                    r"\end{onecolentry}",
                ]
            )
        )

    project_blocks = []
    for project in _prioritized_projects(profile, job):
        name_text = str(project.get("name") or "Project").strip()
        description = str(project.get("description") or "").strip()
        bullets = [str(bullet) for bullet in project.get("bullets") or [] if str(bullet).strip()]
        if not bullets:
            bullets = ["Add concise, truthful technical bullets for this project."]
        project_blocks.append(
            "\n".join(
                [
                    _heading_line(name_text),
                    r"\begin{onecolentry}",
                    escape_tex(description) if description else "",
                    r"\begin{highlights}",
                    _itemize(bullets[:4]),
                    r"\end{highlights}",
                    r"\end{onecolentry}",
                ]
            )
        )

    skills = ", ".join(_skills(profile, job))
    skills_block = (
        "\n".join([r"\section{Skills}", r"\begin{onecolentry}", escape_tex(skills), r"\end{onecolentry}"])
        if skills
        else ""
    )

    return rf"""\documentclass[10pt, letterpaper]{{article}}
\usepackage[ignoreheadfoot,top=1.25cm,bottom=1.25cm,left=1.35cm,right=1.35cm,footskip=0.6cm]{{geometry}}
\usepackage{{titlesec}}
\usepackage{{tabularx}}
\usepackage{{array}}
\usepackage[dvipsnames]{{xcolor}}
\definecolor{{primaryColor}}{{RGB}}{{0,0,0}}
\usepackage{{enumitem}}
\usepackage[
    pdftitle={{{escape_tex(name)} Resume - {escape_tex(job.company)}}},
    pdfauthor={{{escape_tex(name)}}},
    pdfcreator={{JobFiller}},
    colorlinks=true,
    urlcolor=primaryColor
]{{hyperref}}
\usepackage{{bookmark}}
\usepackage{{changepage}}
\usepackage{{paracol}}
\usepackage{{needspace}}
\usepackage{{iftex}}
\ifPDFTeX
    \input{{glyphtounicode}}
    \pdfgentounicode=1
    \usepackage[T1]{{fontenc}}
    \usepackage[utf8]{{inputenc}}
    \usepackage{{lmodern}}
\fi
\usepackage{{charter}}
\raggedright
\pagestyle{{empty}}
\setcounter{{secnumdepth}}{{0}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\topskip}}{{0pt}}
\setlength{{\columnsep}}{{0.15cm}}
\pagenumbering{{gobble}}
\titleformat{{\section}}{{\needspace{{4\baselineskip}}\bfseries\large}}{{}}{{0pt}}{{}}[\vspace{{1pt}}\titlerule]
\titlespacing{{\section}}{{-1pt}}{{0.3cm}}{{0.2cm}}
\renewcommand\labelitemi{{$\vcenter{{\hbox{{\small$\bullet$}}}}$}}
\newenvironment{{highlights}}{{\begin{{itemize}}[topsep=0.10cm,parsep=0.10cm,partopsep=0pt,itemsep=0pt,leftmargin=0cm + 10pt]}}{{\end{{itemize}}}}
\newenvironment{{onecolentry}}{{\begin{{adjustwidth}}{{0cm}}{{0cm}}}}{{\end{{adjustwidth}}}}
\newenvironment{{twocolentry}}[2][]{{\onecolentry\def\secondColumn{{#2}}\setcolumnwidth{{\fill,4.5cm}}\begin{{paracol}}{{2}}}}{{\switchcolumn\raggedleft\secondColumn\end{{paracol}}\endonecolentry}}
\newcommand{{\AND}}{{\unskip\cleaders\hbox{{$|$}}\hskip 1.1em\ignorespaces}}
\begin{{document}}
\begin{{center}}
    \fontsize{{25pt}}{{25pt}}\selectfont {escape_tex(name)}

    \vspace{{5pt}}
    \normalsize
{contact_line}
\end{{center}}
\vspace{{5pt - 0.3cm}}

\section{{Education}}
{chr(10).join(education_blocks)}

\section{{Experience}}
{chr(10).join(experience_blocks)}

\section{{Projects}}
{chr(10).join(project_blocks)}

{skills_block}

\end{{document}}
"""


def make_cover_letter(job: Job) -> str:
    profile = _profile()
    name = str(profile.get("name") or "Your Name").strip()
    email = str(profile.get("email") or "add-your-email-in-settings").strip()
    summary = str(profile.get("summary") or "").strip()
    strongest_project = _prioritized_projects(profile, job)[0]
    project_name = str(strongest_project.get("name") or "my strongest relevant project")
    project_description = str(strongest_project.get("description") or "a project configured in my candidate profile")
    requirements = ", ".join(split_list(job.key_requirements)[:3] or [job.title])
    keywords = ", ".join(_job_keywords(job)[:5])
    if not summary:
        summary = "I am configuring JobFiller with my own background, source resume, and profile facts so each application packet stays grounded in verified experience."

    return textwrap.dedent(
        f"""\
        {name}
        {email}

        Dear {job.company or "Hiring"} Team,

        I am interested in the {job.title or "open"} role. The posting emphasizes {requirements}, and I am using JobFiller to prepare a tailored application packet grounded in my configured profile facts and source materials.

        {summary}

        One relevant example is {project_name}: {project_description} This maps naturally to the role's focus on {keywords or "the listed requirements"}. I have kept this draft concise so it can be reviewed and adjusted before submission.

        I would be glad to bring this background to {job.company or "your team"} and continue the conversation.

        Sincerely,
        {name}
        """
    ).strip() + "\n"


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
        for text in [str(bullet_text) for bullet_text in item.get("bullets") or []][:4]:
            bullet(text)

    section("Projects")
    for project in _prioritized_projects(profile, job):
        c.setFont("Helvetica-Bold", 10.2)
        c.drawString(left, y, str(project.get("name") or "Project"))
        y -= 9
        y = draw_wrapped(c, str(project.get("description") or ""), left, y, 126, 8.1, 9)
        for text in [str(bullet_text) for bullet_text in project.get("bullets") or []][:4]:
            bullet(text)
        y -= 6

    skills = ", ".join(_skills(profile, job))
    if skills and y > 80:
        section("Skills")
        y = draw_wrapped(c, skills, left, y, 126, 8.2, 9)
    c.save()
