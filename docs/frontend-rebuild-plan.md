# JobFiller Frontend Rebuild Plan

## Goal

Rebuild the frontend as a dense JobFiller workflow operating system that matches the provided reference screenshot: fixed sidebar navigation, global top command bar, central table/list workspace, and persistent selected-record inspector.

## Orchestration Model

The rebuild followed the SRS subagent structure used in the DocBridge-style workflow:

- Frontend Director: owned route map, implementation integration, and acceptance checks.
- Design System Engineer: owned tokens, CSS density, badges, tables, buttons, cards, and shell sizing.
- Shell Navigation Engineer: owned `AppShell`, `SidebarNav`, `TopCommandBar`, responsive route rail, and route highlighting.
- Data State Engineer: owned typed fixtures, mock state, table helpers, async mock actions, and toast behavior.
- Route Engineers: implemented Jobs, Questions, Apply Queue, Profile Facts, Runs & Logs, Auto Generate, Assist Upload, Agent Import / MCP, Export Workbook, Settings, and Model Health.
- QA Visual Engineer: validated routing, resize behavior, interactions, screenshots, ImageGen artifacts, build, and test evidence.

## Route Map

| Route | Page | Core Content |
| --- | --- | --- |
| `/jobs` | Jobs | Discovered jobs table, fit/grade/status, notices, selected job inspector. |
| `/questions` | Questions | Extracted questions, answer editor, facts used, approve/regenerate/copy actions. |
| `/apply-queue` | Apply Queue | Application packet table and board view with checklist/status actions. |
| `/profile-facts` | Profile Facts | Structured profile facts, category tabs, fact editor and evidence. |
| `/runs-logs` | Runs & Logs | Automation runs, logs, status filters, retry/copy actions. |
| `/generate-queue` | Auto Generate | Automatic packet-generation status derived from imported jobs. |
| `/assist-upload` | Assist Upload | Upload area, recent uploads table, extraction/import/reprocess actions. |
| `/agent-import-mcp` | Agent Import / MCP | Finder sources, MCP server table, connection diagnostics. |
| `/export-workbook` | Export Workbook | Export templates, sheet preview, workbook settings/actions. |
| `/settings` | Settings | Dense settings table, editable inspector forms, toggles, save/test actions. |
| `/model-health` | Model Health | Service health, latency, diagnostics, model status actions. |

Legacy internal route aliases from the previous frontend are normalized to the new route names so old links such as `tomorrow`, `facts`, `reprocess`, `agent`, `export`, and `health` still land on the new pages.

## Shared Implementation

- `app/frontend/src/design/tokens.ts` defines shell sizing and typography targets.
- `app/frontend/src/styles/theme.css` defines Untitled-style color, radius, shadow, and layout variables.
- `app/frontend/src/styles/app.css` implements the shell, tables, inspector, controls, and responsive behavior.
- `app/frontend/src/components/ui/index.jsx` centralizes reusable components: page headers, metric cards, notice cards, filters, tables, badges, inspector, artifacts, action bars, pagination, empty states, skeletons, toasts, dialogs, and drawers.
- `app/frontend/src/router/routes.jsx` is the single route/navigation source of truth.
- `app/frontend/src/state/useJobFillerState.jsx` owns mock data state, selection, filters, sorting, pagination, loading, toasts, and mock actions.
- `app/frontend/src/pages/WorkflowPage.jsx` provides the shared page engine used by every route.

## ImageGen Artifacts

ImageGen prompts were saved for every page in `docs/ui-mockups/prompts/*.md`. Binary mockup PNGs are local artifacts and are not committed.

## Responsive Strategy

- Desktop keeps the sidebar, main workspace, and right inspector visible.
- At narrower desktop/tablet widths, the inspector stacks below the workspace and tables retain horizontal scrolling.
- Mobile hides the sidebar and shows a compact horizontal route rail.
- Tables use a dedicated `.dataTableScroller` so wide columns scroll inside the table frame without clipping or forcing document-level horizontal overflow.
