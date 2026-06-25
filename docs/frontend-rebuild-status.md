# JobFiller Frontend Rebuild Status

## Completed

- Rebuilt the frontend entry around a shared React app shell.
- Added the exact SRS sidebar pages: Jobs, Questions, Apply Queue, Profile Facts, Runs & Logs, Auto Generate, Assist Upload, Agent Import / MCP, Export Workbook, Settings, Model Health.
- Implemented the global top command bar with search, Scan Now, Import URL, health/finder/LLM status controls, settings, and appearance icon.
- Added shared theme tokens, app CSS, reusable UI primitives, route map, typed domain fixtures, table helpers, and mock async state.
- Implemented all eleven pages with realistic mock content, filters, sortable/paginated tables where appropriate, selected-row inspectors, and primary mock actions.
- Added table resize protection through an internal horizontal scroller and Playwright assertion for the right-most cell.
- Added ImageGen prompt Markdown files for every required route.
- Added route screenshot capture support; generated PNG captures are local artifacts and are not committed.
- Updated frontend smoke scripts to run the rebuild QA suite.
- Made live backend job hydration opt-in with `VITE_JOBFILLER_USE_API=true`; the default rebuild path is deterministic and fixture-backed.

## Key Files

- `app/frontend/src/App.jsx`
- `app/frontend/src/layout/AppShell.jsx`
- `app/frontend/src/layout/SidebarNav.jsx`
- `app/frontend/src/layout/TopCommandBar.jsx`
- `app/frontend/src/router/routes.jsx`
- `app/frontend/src/components/ui/index.jsx`
- `app/frontend/src/pages/WorkflowPage.jsx`
- `app/frontend/src/state/useJobFillerState.jsx`
- `app/frontend/src/data/fixtures/index.ts`
- `app/frontend/src/lib/table.ts`
- `app/frontend/tests/rebuild-smoke.mjs`

## Generated Design References

Prompt files for generated design references live in `docs/ui-mockups/prompts`. Binary mockups are treated as local artifacts and are not committed.

## Screenshots

The Playwright rebuild smoke test captures screenshots for every desktop route plus a mobile Jobs view. By default they are written to a temporary directory; set `JOBFILLER_UPDATE_DOC_SCREENSHOTS=true` to write local captures under `docs/screenshots`.

## Known QA Notes

- The frontend package does not currently define a lint or TypeScript typecheck script, and there is no frontend `tsconfig`/ESLint/Biome config in `app/frontend`. The production Vite build and Playwright rebuild smoke suite pass.
- Existing backend, docs, dist, and legacy test files had unrelated dirty-worktree changes before this rebuild. This pass preserved those changes and kept the SRS work scoped to the rebuilt frontend artifacts and docs.
