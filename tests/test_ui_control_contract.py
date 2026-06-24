from __future__ import annotations

import re
from pathlib import Path


def _frontend_source() -> str:
    return Path("app/frontend/src/main.jsx").read_text(encoding="utf-8")



def test_question_queue_testids_are_hardcoded() -> None:
    source = _frontend_source()

    expected = [
        'data-testid="dashboard-question-sort"',
        'data-testid="question-open-list"',
        'data-testid="question-view-all"',
    ]

    for marker in expected:
        assert marker in source, f"Missing frontend contract marker {marker}"


def test_question_row_dynamic_testids_are_template_literals() -> None:
    source = _frontend_source()

    for template_key in ["question-answer", "question-save", "question-skip", "question-open"]:
        pattern = rf"data-testid=\{{`{template_key}-\$\{{q\.id\}}`\}}"
        assert re.search(pattern, source), f"Missing dynamic question row marker for {template_key}"


def test_srs_page_controls_have_stable_testids() -> None:
    source = _frontend_source()

    expected = [
        # Top command bar and sidebar.
        'data-testid="scan-now"',
        'data-testid="import-url-input"',
        'data-testid="import-url-button"',
        'data-testid="health-pill-scanner"',
        'data-testid="health-pill-worker"',
        'data-testid="health-pill-llm"',
        'data-testid="command-open-settings"',
        'data-testid="top-user-menu"',
        'data-testid="top-user-settings"',
        'data-testid="nav-jobs"',
        'data-testid="nav-questions"',
        'data-testid="nav-facts"',
        'data-testid="nav-runs"',
        'data-testid="nav-reprocess"',
        'data-testid="nav-agent"',
        'data-testid="nav-assist"',
        'data-testid="nav-export"',
        'data-testid="nav-settings"',
        'data-testid="nav-health"',
        # Jobs workspace controls.
        'data-testid="jobs-search"',
        'data-testid="setup-open-settings"',
        'data-testid="setup-open-agent"',
        'data-testid="setup-scan-now"',
        'data-testid="jobs-filter-status"',
        'data-testid="jobs-filter-source"',
        'data-testid="jobs-location-toggle"',
        'data-testid="jobs-filter-work-model"',
        'data-testid="jobs-sort"',
        'data-testid="jobs-advanced-toggle"',
        'data-testid="advanced-clear-filters"',
        'data-testid="location-clear"',
        'data-testid="location-apply"',
        'data-testid="jobs-select-all"',
        'data-testid="jobs-page-prev"',
        'data-testid="jobs-page-next"',
        'data-testid="jobs-page-size"',
        # Utility pages.
        'data-testid="questions-search"',
        'data-testid="questions-status-filter"',
        'data-testid="questions-tag-filter"',
        'data-testid="questions-sort"',
        'data-testid="fact-tag-input"',
        'data-testid="fact-question-input"',
        'data-testid="fact-confidence-input"',
        'data-testid="fact-answer-input"',
        'data-testid="fact-save"',
        'data-testid="reprocess-selected"',
        'data-testid="agent-copy-payload"',
        'data-testid="assist-file-input"',
        'data-testid="assist-parse-files"',
        'data-testid="assist-launch-helper"',
        'data-testid="export-workbook"',
        'data-testid="settings-save"',
        'data-testid="model-health-refresh"',
        'data-testid="model-health-loading"',
        # Detail panel and modals.
        'data-testid="inspector-close"',
        'data-testid="grade-open-report"',
        'data-testid="report-modal-close"',
        'data-testid="artifact-editor-textarea"',
        'data-testid="artifact-editor-close"',
        'data-testid="artifact-editor-cancel"',
        'data-testid="save-artifact-editor"',
        'data-testid="notes-save"',
    ]

    for marker in expected:
        assert marker in source, f"Missing SRS control marker {marker}"


def test_assist_upload_client_requires_explicit_confirmation() -> None:
    source = Path("app/frontend/src/api.js").read_text(encoding="utf-8")

    assert "confirm=review-before-submit" in source


def test_dynamic_srs_action_controls_have_template_testids() -> None:
    source = _frontend_source()

    templates = [
        "job-row",
        "jobs-row-select",
        "jobs-role",
        "jobs-role-open",
        "jobs-artifact-resume",
        "jobs-artifact-latex",
        "jobs-open-folder",
        "inspector-apply",
        "inspector-tab",
        "artifact-resume-download",
        "artifact-resume-open",
        "artifact-resume-tex",
        "artifact-resume-folder",
        "artifact-resume-regrade",
        "artifact-resume-edit",
        "artifact-cover-download",
        "artifact-cover-open",
        "artifact-cover-folder",
        "artifact-cover-edit",
        "artifact-reprocess",
        "artifact-assist-resume",
        "artifact-assist-cover",
        "artifact-apply",
        "fact-edit",
        "fact-delete",
        "run-row",
        "reprocess-job",
    ]

    for template_key in templates:
        pattern = rf"data-testid=\{{`{template_key}-\$\{{[^}}]+}}\`}}"
        assert re.search(pattern, source), f"Missing dynamic SRS action marker for {template_key}"


def test_srs_accessibility_semantics_are_declared() -> None:
    source = _frontend_source()

    expected_markers = [
        'role="table"',
        'aria-label="Jobs table"',
        'aria-label="Blocking questions table"',
        'role="rowgroup"',
        'role="columnheader"',
        'role="row"',
        'role="cell"',
        'aria-selected={selectedId === job.id}',
        'role="tablist"',
        'aria-label="Job detail tabs"',
        'role="tab"',
        'aria-selected={activeTab === tab}',
        'aria-label="Open settings"',
        'aria-label="Advanced job filters"',
        'aria-label="Close location preferences"',
        'aria-label="Close job detail panel"',
        'aria-label={`Select ${job.company} ${job.title}`}',
        'aria-label={`Open ${job.company} resume PDF`}',
        'aria-label={`Open ${job.company} resume TeX`}',
        'aria-label={`Open artifact folder for ${job.company}`}',
        'aria-label={`Open context for ${q.company} question`}',
    ]

    for marker in expected_markers:
        assert marker in source, f"Missing SRS accessibility marker {marker}"
