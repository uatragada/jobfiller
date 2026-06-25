from __future__ import annotations

import re
from pathlib import Path


CONTRACT_PATHS = [
    Path("app/frontend/src/layout/TopCommandBar.jsx"),
    Path("app/frontend/src/layout/SidebarNav.jsx"),
    Path("app/frontend/src/pages/WorkflowPage.jsx"),
    Path("app/frontend/src/components/ui/index.jsx"),
    Path("app/frontend/src/components/jobfiller-ui.jsx"),
]


def _frontend_source(*paths: Path) -> str:
    selected = paths or tuple(CONTRACT_PATHS)
    return "\n".join(path.read_text(encoding="utf-8") for path in selected)


def _assert_static_testid(source: str, test_id: str) -> None:
    pattern = rf"(?:data-testid|testId)=['\"]{re.escape(test_id)}['\"]"
    assert re.search(pattern, source), f"Missing real static test id {test_id}"


def _assert_dynamic_testid(source: str, template_key: str) -> None:
    prop_pattern = rf"(?:data-testid|testId)=\{{`{re.escape(template_key)}-\$\{{[^}}]+}}\`}}"
    config_pattern = rf"{re.escape(template_key)}-\$\{{[^}}]+}}"
    assert re.search(prop_pattern, source) or re.search(config_pattern, source), f"Missing real dynamic test id for {template_key}"


def test_main_entrypoint_does_not_hold_static_contract_markers() -> None:
    source = Path("app/frontend/src/main.jsx").read_text(encoding="utf-8")

    assert "SRS_CONTROL_MARKERS" not in source
    assert "SRS static control patterns" not in source


def test_top_command_bar_controls_have_real_testids() -> None:
    source = _frontend_source(Path("app/frontend/src/layout/TopCommandBar.jsx"))

    for test_id in [
        "scan-now",
        "import-url-input",
        "import-url-button",
        "health-pill-scanner",
        "health-pill-worker",
        "health-pill-llm",
        "command-open-settings",
        "top-user-menu",
        "top-user-settings",
    ]:
        _assert_static_testid(source, test_id)


def test_sidebar_navigation_uses_route_backed_testids() -> None:
    source = _frontend_source(Path("app/frontend/src/layout/SidebarNav.jsx"), Path("app/frontend/src/router/routes.jsx"))

    assert 'data-testid={navTestIds[route.id] || `nav-${route.id}`}' in source
    for route_id in ["jobs", "questions", "settings"]:
        assert f'id: "{route_id}"' in source
    for test_id in ["nav-tomorrow", "nav-facts", "nav-runs", "nav-reprocess", "nav-agent", "nav-assist", "nav-export", "nav-health"]:
        assert f'"{test_id}"' in source


def test_filter_table_and_pagination_controls_are_rendered_from_real_props() -> None:
    source = _frontend_source(Path("app/frontend/src/components/ui/index.jsx"), Path("app/frontend/src/pages/WorkflowPage.jsx"))

    for marker in [
        "`${testIdPrefix}-search`",
        "`${testIdPrefix}-filter-${testIdKey(filter.key)}`",
        "`${testIdPrefix}-advanced-toggle`",
        "`${testIdPrefix}-page-prev`",
        "`${testIdPrefix}-page-next`",
        "`${testIdPrefix}-page-size`",
        'testIdPrefix={pageId}',
    ]:
        assert marker in source

    for marker in [
        'filter("status", "Status"',
        'filter("source", "Source"',
        'filter("workModel", "Work model"',
    ]:
        assert marker in source

    for test_id in [
        "jobs-sort",
        "jobs-sort-posted",
        "jobs-sort-imported",
        "jobs-sort-source",
        "jobs-sort-company",
        "jobs-sort-role",
        "jobs-sort-location",
        "jobs-sort-status",
        "jobs-sort-fit",
        "jobs-sort-grade",
        "jobs-sort-ready",
        "jobs-sort-artifacts",
        "advanced-clear-filters",
        "jobs-location-toggle",
        "location-clear",
        "location-apply",
        "questions-status-filter",
        "questions-tag-filter",
    ]:
        assert test_id in source


def test_question_and_artifact_row_actions_have_dynamic_testids() -> None:
    source = _frontend_source(Path("app/frontend/src/pages/WorkflowPage.jsx"), Path("app/frontend/src/components/ui/index.jsx"))

    for template_key in [
        "row",
        "jobs-role",
        "artifact-resume-download",
        "artifact-resume-open",
        "artifact-resume-tex",
        "artifact-resume-folder",
        "artifact-resume-regrade",
        "artifact-cover-download",
        "artifact-cover-open",
        "artifact-cover-folder",
        "artifact-cover-edit",
        "artifact-reprocess",
        "artifact-assist-resume",
        "artifact-assist-cover",
        "question-answer",
        "question-save",
        "question-skip",
        "question-open",
        "inspector-apply",
    ]:
        _assert_dynamic_testid(source, template_key)

    assert "rowTestIdPrefix ? `${rowTestIdPrefix}-row-select-${id}`" in source
    assert 'rowTestIdFor={pageId === "runs-logs" ? (_row, id) => `run-row-${id}` : undefined}' in source


def test_static_action_controls_have_real_testids() -> None:
    source = _frontend_source(Path("app/frontend/src/pages/WorkflowPage.jsx"), Path("app/frontend/src/components/ui/index.jsx"))

    for test_id in [
        "dashboard-question-sort",
        "question-open-list",
        "questions-sort",
        "fact-tag-input",
        "fact-question-input",
        "fact-confidence-input",
        "fact-answer-input",
        "fact-save",
        "reprocess-selected",
        "assist-file-input",
        "assist-parse-files",
        "assist-launch-helper",
        "export-workbook",
        "export-link-xlsx",
        "export-link-json",
        "export-link-csv",
        "settings-save",
        "model-health-refresh",
        "inspector-close",
        "grade-open-report",
        "report-modal-close",
        "artifact-editor-textarea",
        "artifact-editor-cancel",
        "save-artifact-editor",
        "notes-save",
    ]:
        _assert_static_testid(source, test_id)


def test_assist_upload_client_requires_explicit_confirmation() -> None:
    source = Path("app/frontend/src/api.js").read_text(encoding="utf-8")

    assert "confirm=review-before-submit" in source


def test_company_cells_request_real_logo_assets_with_initial_fallback() -> None:
    source = _frontend_source(Path("app/frontend/src/components/ui/index.jsx"), Path("app/frontend/src/pages/WorkflowPage.jsx"))
    styles = Path("app/frontend/src/styles/app.css").read_text(encoding="utf-8")

    assert "KNOWN_COMPANY_DOMAINS" in source
    assert "https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64" in source
    assert "logoUrl={companyLogoUrl" in source
    assert "onError={() => setLogoFailed(true)}" in source
    assert ".entityAvatar.hasLogo" in styles
    assert "object-fit: contain" in styles


def test_srs_accessibility_semantics_are_declared_on_real_components() -> None:
    source = _frontend_source(Path("app/frontend/src/components/ui/index.jsx"), Path("app/frontend/src/pages/WorkflowPage.jsx"))

    for marker in [
        'role="table"',
        'aria-label={label}',
        'role="rowgroup"',
        'role="columnheader"',
        'role="row"',
        'role="cell"',
        "aria-selected={isSelected}",
        'role="tablist"',
        'role="tab"',
        'aria-selected={activeTab === tab}',
        'label={pageId === "questions" ? "Blocking questions table" : `${title} table`}',
    ]:
        assert marker in source
