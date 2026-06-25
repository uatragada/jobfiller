import process from "node:process";
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { createServer } from "vite";

const REQUESTED_PORT = Number(process.env.JOBFILLER_REBUILD_TEST_PORT || 0);
const __dirname = dirname(fileURLToPath(import.meta.url));
const updateDocsScreenshots = ["1", "true", "yes"].includes(String(process.env.JOBFILLER_UPDATE_DOC_SCREENSHOTS || "").toLowerCase());
const screenshotsDir = process.env.JOBFILLER_REBUILD_SCREENSHOTS_DIR
  ? resolve(process.env.JOBFILLER_REBUILD_SCREENSHOTS_DIR)
  : updateDocsScreenshots
    ? resolve(__dirname, "../../../docs/screenshots")
    : resolve(tmpdir(), "jobfiller-rebuild-smoke", String(process.pid));
const transparentLogoPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);

const routes = [
  ["jobs", "Jobs"],
  ["email-alerts", "Email Alerts"],
  ["questions", "Questions"],
  ["apply-queue", "Apply Queue"],
  ["profile-facts", "Profile Facts"],
  ["runs-logs", "Runs & Logs"],
  ["generate-queue", "Auto Generate"],
  ["assist-upload", "Assist Upload"],
  ["agent-import-mcp", "Agent Import / MCP"],
  ["export-workbook", "Export Workbook"],
  ["settings", "Settings"],
  ["model-health", "Model Health"],
];

async function visible(page, selector, label) {
  await page.locator(selector).waitFor({ state: "visible", timeout: 7000 }).catch((error) => {
    throw new Error(`Expected visible ${label}: ${error.message}`);
  });
}

async function mockExternalLogoRequests(context) {
  await context.route("https://www.google.com/s2/favicons**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/png",
      body: transparentLogoPng,
    }),
  );
}

async function assertNoDocumentOverflow(page, label) {
  const result = await page.evaluate(() => ({
    viewport: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
    tableScrollers: [...document.querySelectorAll(".dataTableScroller")].map((el) => ({
      clientWidth: el.clientWidth,
      scrollWidth: el.scrollWidth,
      canScroll: el.scrollWidth >= el.clientWidth,
    })),
  }));
  if (result.documentWidth > result.viewport + 1 || result.bodyWidth > result.viewport + 1) {
    throw new Error(`Document overflow at ${label}: ${JSON.stringify(result)}`);
  }
}

async function assertTableRightEdgeReachable(page, label) {
  const result = await page.evaluate(() => {
    const scroller = document.querySelector(".dataTableScroller");
    if (!scroller) return { ok: false, reason: "missing scroller" };
    scroller.scrollLeft = scroller.scrollWidth;
    const lastCell = document.querySelector(".dataTableGrid.row > [role='cell']:last-child");
    if (!lastCell) return { ok: false, reason: "missing last cell" };
    const rect = lastCell.getBoundingClientRect();
    const parent = scroller.getBoundingClientRect();
    return { ok: rect.right <= parent.right + 2 && rect.left >= parent.left - 2, rect, parent };
  });
  if (!result.ok) {
    throw new Error(`Table right edge unreachable at ${label}: ${JSON.stringify(result)}`);
  }
  await page.evaluate(() => {
    const scroller = document.querySelector(".dataTableScroller");
    if (scroller) scroller.scrollLeft = 0;
  });
}

async function assertJobsTableCellsUnclipped(page, label) {
  const clipped = await page.evaluate(() => {
    const scroller = document.querySelector(".route-jobs .dataTableScroller");
    if (!scroller) return [{ label: "table", text: "missing scroller" }];
    scroller.scrollLeft = 0;
    const selectors = [
      ".route-jobs .dataTableGrid.header > [role='columnheader']",
      ".route-jobs .dataTableGrid.row > [role='cell']",
      ".route-jobs .companyCell",
      ".route-jobs .companyName",
      ".route-jobs .cellStack strong",
      ".route-jobs .cellStack small",
      ".route-jobs .statusBadge",
    ];
    return selectors
      .flatMap((selector) => [...document.querySelectorAll(selector)])
      .filter((el) => {
        const style = window.getComputedStyle(el);
        const canClip = style.overflowX !== "visible" || style.overflowY !== "visible";
        return canClip && (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1);
      })
      .map((el) => ({
        label: el.getAttribute("data-label") || el.getAttribute("role") || el.className || el.tagName,
        text: (el.textContent || "").replace(/\s+/g, " ").trim(),
        clientWidth: el.clientWidth,
        scrollWidth: el.scrollWidth,
        clientHeight: el.clientHeight,
        scrollHeight: el.scrollHeight,
        overflowX: window.getComputedStyle(el).overflowX,
        overflowY: window.getComputedStyle(el).overflowY,
      }));
  });
  if (clipped.length) {
    throw new Error(`Jobs table clipped cells at ${label}:\n${JSON.stringify(clipped, null, 2)}`);
  }
}

async function assertJobsDateSortUsesChronology(browser, baseUrl) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  try {
    await mockExternalLogoRequests(context);
    await context.route("**/api/**", (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      const json = (body) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
      if (path === "/api/health") return json({ status: "ok", version: "test" });
      if (path === "/api/session") return json({ mutation_token: "frontend-smoke-token" });
      if (path === "/api/settings" || path === "/api/model-health") return json({});
      if (path === "/api/application-events") return json([]);
      if (path === "/api/jobs") {
        return json([
          {
            id: 901,
            company: "May Systems",
            title: "May Backend Engineer",
            location: "Remote",
            status: "NEW",
            fit_score: 81,
            posted_at: "2026-05-30T15:00:00Z",
            first_seen_at: "2026-05-30T15:05:00Z",
            updated_at: "2026-05-30T15:05:00Z",
          },
          {
            id: 902,
            company: "June Labs",
            title: "June Backend Engineer",
            location: "Remote",
            status: "NEW",
            fit_score: 86,
            posted_at: "2026-06-01T09:00:00Z",
            first_seen_at: "2026-06-01T09:05:00Z",
            updated_at: "2026-06-01T09:05:00Z",
          },
          {
            id: 903,
            company: "April Cloud",
            title: "April Backend Engineer",
            location: "Remote",
            status: "NEW",
            fit_score: 78,
            posted_at: "2026-04-29T21:00:00Z",
            first_seen_at: "2026-04-29T21:05:00Z",
            updated_at: "2026-04-29T21:05:00Z",
          },
        ]);
      }
      return json({});
    });
    const page = await context.newPage();
    await page.goto(`${baseUrl}/jobs`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("row-902").waitFor({ state: "visible" });
    await expectFirstJobCompany(page, "June Labs", "default imported desc");
    await page.getByRole("button", { name: /Posted/ }).click();
    await expectFirstJobCompany(page, "April Cloud", "posted asc");
    await page.getByRole("button", { name: /Posted/ }).click();
    await expectFirstJobCompany(page, "June Labs", "posted desc");
    await page.getByTestId("jobs-sort-imported").click();
    await expectFirstJobCompany(page, "April Cloud", "imported asc");
    await page.getByTestId("jobs-sort-imported").click();
    await expectFirstJobCompany(page, "June Labs", "imported desc");
  } finally {
    await context.close();
  }
}

async function expectFirstJobCompany(page, expected, label) {
  const actual = await page.locator(".route-jobs .dataTableGrid.row").first().locator(".companyName").innerText();
  if (actual !== expected) throw new Error(`Expected first job company for ${label} to be ${expected}, got ${actual}`);
}

async function assertSettingsSidecarTracksRowSelection(page, baseUrl) {
  await page.goto(`${baseUrl}/settings`, { waitUntil: "domcontentloaded" });
  await page.getByTestId("row-Profile").click();
  const profileState = await settingsSidecarState(page);
  if (profileState.title !== "Profile" || profileState.label !== "Profile email" || !profileState.value) {
    throw new Error(`Settings sidecar did not show Profile details: ${JSON.stringify(profileState)}`);
  }

  await page.getByTestId("row-Job Finder").click();
  const finderState = await settingsSidecarState(page);
  if (finderState.title !== "Job Finder" || finderState.label !== "Daily scan limit" || !finderState.value) {
    throw new Error(`Settings sidecar did not show Job Finder details: ${JSON.stringify(finderState)}`);
  }
}

async function settingsSidecarState(page) {
  return page.evaluate(() => {
    const panel = document.querySelector(".inspectorPanel");
    const selectedInput = panel?.querySelector('[data-testid="settings-selected-value"]');
    return {
      title: panel?.querySelector("h2")?.textContent?.trim() || "",
      label: panel?.querySelector(".settingsForm label:first-child span")?.textContent?.trim() || "",
      value: selectedInput?.value || "",
    };
  });
}

async function assertTableStatusLabels(page, labels, route) {
  const visibleLabels = await page.locator(`.route-${route} .dataTableGrid.row .statusBadge`).evaluateAll((badges) =>
    badges.map((badge) => badge.textContent?.trim() || ""),
  );
  for (const label of labels) {
    if (!visibleLabels.includes(label)) {
      throw new Error(`Expected ${route} table status labels to include ${label}, got ${JSON.stringify(visibleLabels)}`);
    }
  }
}

async function assertApplicationStatesUseDocumentedLabels(browser, baseUrl) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
  const states = [
    ["DISCOVERED", "Discovered"],
    ["APPLIED", "Applied"],
    ["ACTION_NEEDED", "Action Needed"],
    ["INTERVIEW", "Interview"],
    ["REJECTED", "Rejected"],
  ];
  const jobs = states.map(([state, label], index) => ({
    id: 950 + index,
    company: `${label} Co`,
    title: `${label} Engineer`,
    location: "Remote",
    source: "email",
    source_url: `https://example.com/jobs/${state.toLowerCase()}`,
    fit_score: 80 + index,
    status: "QA",
    application_state: state,
    ready_to_send: true,
    posted_at: "2026-06-20T12:00:00Z",
    first_seen_at: "2026-06-20T12:00:00Z",
    updated_at: "2026-06-20T12:00:00Z",
  }));
  const checklistRows = jobs.map((job, index) => ({
    apply_order: index + 1,
    job_id: job.id,
    company: job.company,
    title: job.title,
    status: job.status,
    application_state: job.application_state,
    fit_score: job.fit_score,
    ready_to_send: true,
    apply_url: job.source_url,
  }));
  try {
    await mockExternalLogoRequests(context);
    await context.route("**/api/**", (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      const json = (body) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
      if (path === "/api/health") return json({ status: "ok", version: "test" });
      if (path === "/api/session") return json({ mutation_token: "frontend-smoke-token" });
      if (path === "/api/settings" || path === "/api/model-health") return json({});
      if (path === "/api/jobs") return json(jobs);
      if (path === "/api/checklist/apply-queue") return json(checklistRows);
      if (["/api/profile-facts", "/api/questions", "/api/runs", "/api/application-events"].includes(path)) return json([]);
      return json({});
    });
    const page = await context.newPage();
    await page.goto(`${baseUrl}/jobs`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("row-950").waitFor({ state: "visible" });
    await assertTableStatusLabels(page, states.map(([, label]) => label), "jobs");
    await page.getByTestId("jobs-filter-status").selectOption("Rejected");
    await page.getByTestId("row-954").waitFor({ state: "visible" });
    if ((await page.locator(".dataTableGrid.row").count()) !== 1) {
      throw new Error("Rejected Jobs filter should show exactly one documented-state row.");
    }

    await page.goto(`${baseUrl}/apply-queue`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("row-950").waitFor({ state: "visible" });
    await assertTableStatusLabels(page, states.map(([, label]) => label), "apply-queue");
    await page.getByTestId("apply-queue-filter-status").selectOption("Interview");
    await page.getByTestId("row-953").waitFor({ state: "visible" });
    if ((await page.locator(".dataTableGrid.row").count()) !== 1) {
      throw new Error("Interview Apply Queue filter should show exactly one documented-state row.");
    }
  } finally {
    await context.close();
  }
}

async function main() {
  await mkdir(screenshotsDir, { recursive: true });
  const server = await createServer({
    root: process.cwd(),
    server: { host: "127.0.0.1", port: REQUESTED_PORT, strictPort: REQUESTED_PORT !== 0 },
    logLevel: "error",
  });
  let browser;
  try {
    await server.listen();
    const address = server.httpServer?.address();
    const port = typeof address === "object" && address ? address.port : REQUESTED_PORT;
    const baseUrl = `http://127.0.0.1:${port}`;
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
    await mockExternalLogoRequests(context);
    await context.route("**/api/**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: false, reason: "frontend smoke uses fixture data" }),
      }),
    );
    const page = await context.newPage();
    const consoleMessages = [];
    const pageErrors = [];
    page.on("console", (message) => {
      if (message.text().includes("Failed to load resource: net::ERR_FAILED")) return;
      if (["error", "warning"].includes(message.type())) consoleMessages.push(`${message.type()}: ${message.text()}`);
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));

    for (const [route, title] of routes) {
      await page.goto(`${baseUrl}/${route}`, { waitUntil: "domcontentloaded" });
      await visible(page, ".pageTitleLine h1", `${title} header`);
      const actualTitle = await page.locator(".pageTitleLine h1").innerText();
      if (actualTitle !== title) throw new Error(`Expected ${title}, got ${actualTitle}`);
      if (route === "email-alerts") {
        const metrics = await page.locator(".metricCard").evaluateAll((cards) =>
          cards.map((card) => ({
            label: card.querySelector("span")?.textContent?.trim() || "",
            value: card.querySelector("strong")?.textContent?.trim() || "",
          })),
        );
        if (!metrics.some((metric) => metric.label === "Accepted" && metric.value === "0")) {
          throw new Error(`Expected separate Accepted email metric, got ${JSON.stringify(metrics)}`);
        }
        if (!metrics.some((metric) => metric.label === "Applied" && metric.value === "1")) {
          throw new Error(`Expected separate Applied email metric, got ${JSON.stringify(metrics)}`);
        }
        if (metrics.some((metric) => metric.label === "Accepted / Applied")) {
          throw new Error("Email Alerts should split Accepted and Applied metrics.");
        }
        const alertTabs = await page.locator(".tabStrip button").evaluateAll((tabs) => tabs.map((tab) => tab.textContent?.trim() || ""));
        if (!alertTabs.includes("Accepted") || !alertTabs.includes("Applied") || alertTabs.includes("Acceptance")) {
          throw new Error(`Email Alerts filters should split Accepted and Applied, got ${JSON.stringify(alertTabs)}`);
        }
        await page.locator(".tabStrip button", { hasText: /^Applied$/ }).click();
        await page.waitForFunction(() => document.querySelectorAll(".dataTableGrid.row").length === 1);
        const appliedRowText = await page.locator(".dataTableGrid.row").first().innerText();
        if (!appliedRowText.includes("Applied")) throw new Error(`Expected Applied filter to show only applied rows, got ${appliedRowText}`);
        await page.locator(".tabStrip button", { hasText: /^Accepted$/ }).click();
        await page.waitForFunction(() => document.querySelectorAll(".dataTableGrid.row").length === 0);
        await page.locator(".tabStrip button", { hasText: /^All$/ }).click();
        await page.waitForFunction(() => document.querySelectorAll(".dataTableGrid.row").length === 3);
      }
      await visible(page, ".inspectorPanel", `${title} inspector`);
      await assertNoDocumentOverflow(page, `${route} desktop`);
      if (route !== "settings") await assertTableRightEdgeReachable(page, route);
      if (route === "jobs") await assertJobsTableCellsUnclipped(page, `${route} desktop`);
      await page.screenshot({ path: resolve(screenshotsDir, `${route}.png`), fullPage: false });
    }

    await assertJobsDateSortUsesChronology(browser, baseUrl);
    await assertSettingsSidecarTracksRowSelection(page, baseUrl);
    await assertApplicationStatesUseDocumentedLabels(browser, baseUrl);

    await page.goto(`${baseUrl}/jobs`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("row-3").click();
    await page.getByRole("tab", { name: "Local LLM Grade" }).click();
    await visible(page, ".gradeBreakdown", "Local LLM grade breakdown");
    const gradeBreakdownText = await page.locator(".gradeBreakdown").innerText();
    if (!gradeBreakdownText.includes("Role Fit") || !gradeBreakdownText.includes("Keywords")) {
      throw new Error(`Expected detailed Local LLM score breakdown, got: ${gradeBreakdownText}`);
    }
    await page.getByTestId("grade-open-report").click();
    await page.getByRole("dialog", { name: "Full Local LLM Report" }).waitFor({ state: "visible" });
    await page.getByRole("button", { name: "Cancel" }).click();
    await page.getByRole("tab", { name: "Questions" }).click();
    const jobSidecarQuestionText = await page.locator(".inspectorPanel .jobQuestionList").innerText();
    if (!jobSidecarQuestionText.includes("Describe a payment-like system you built where correctness mattered.")) {
      throw new Error(`Expected job sidecar to show concrete questions, got: ${jobSidecarQuestionText}`);
    }
    if (jobSidecarQuestionText.includes("One or more profile facts need review before applying.")) {
      throw new Error("Job sidecar should not replace concrete questions with the generic profile-facts review message.");
    }
    await page.goto(`${baseUrl}/jobs`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("row-3").click();
    await page.locator(".actionBar").getByRole("button", { name: "Add to Apply Queue" }).click();
    await page.getByText("Stripe added to Apply Queue", { exact: false }).waitFor({ state: "visible" });

    await page.goto(`${baseUrl}/jobs`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("row-3").click();
    await page.locator(".actionBar").getByRole("button", { name: "Mark as Applied" }).click();
    await page.getByTestId("row-3").filter({ hasText: "Applied" }).waitFor({ state: "visible" });
    await page.locator(".searchField input").fill("OpenAI");
    await page.getByTestId("row-1").waitFor({ state: "visible" });
    await page.locator(".appFilterBar").getByRole("button", { name: "Reset" }).click();
    await page.getByRole("button", { name: /^More filters/ }).click();
    await visible(page, ".advancedFilterPanel", "Jobs advanced filters");
    await page.locator('select[aria-label="Role"]').selectOption("Backend");
    await page.getByTestId("row-3").waitFor({ state: "visible" });
    const backendRows = await page.locator(".dataTableGrid.row").count();
    if (backendRows !== 1) throw new Error(`Expected Backend filter to show one row, got ${backendRows}`);
    await page.locator('select[aria-label="Location"]').selectOption("Seattle, WA");
    await page.locator('select[aria-label="Minimum fit"]').selectOption("80");
    await page.getByTestId("row-3").filter({ hasText: "Seattle, WA" }).waitFor({ state: "visible" });
    await page.locator(".advancedFilterHeader").getByRole("button", { name: "Clear advanced" }).click();
    if ((await page.locator('select[aria-label="Role"]').inputValue()) !== "all") throw new Error("Expected Clear advanced to reset Role filter");

    await page.goto(`${baseUrl}/jobs`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Review" }).first().click();
    await visible(page, ".pageTitleLine h1", "Email Alerts from Review");
    const reviewTitle = await page.locator(".pageTitleLine h1").innerText();
    if (reviewTitle !== "Email Alerts") throw new Error(`Expected Review to open Email Alerts, got ${reviewTitle}`);
    const activeAlertTab = await page.locator(".tabStrip button.active").innerText();
    if (activeAlertTab !== "Action Needed") throw new Error(`Expected Action Needed alert filter, got ${activeAlertTab}`);

    await page.goto(`${baseUrl}/questions`, { waitUntil: "domcontentloaded" });
    const answerEditor = page.getByTestId("questions-inspector-answer");
    await answerEditor.fill("Custom payment-system answer draft.");
    await page.getByTestId("row-102").click();
    const inspectorQuestionText = await page.evaluate(() => document.querySelector(".inspectorPanel .textPanel p")?.textContent || "");
    if (!inspectorQuestionText.includes("What hands-on evaluation work have you done")) {
      throw new Error(`Expected inspector to switch to Anthropic question, got: ${inspectorQuestionText}`);
    }
    const switchedAnswer = await answerEditor.inputValue();
    if (!switchedAnswer.startsWith("I have built eval-oriented workflows")) {
      throw new Error(`Expected selected question answer to refresh without reload, got: ${switchedAnswer}`);
    }
    await page.locator(".actionBar").getByRole("button", { name: "Approve Answer" }).click();
    await page.getByText("Answer approved", { exact: false }).waitFor({ state: "visible" });
    await page.locator(".actionBar").getByRole("button", { name: "Regenerate" }).click();
    await page.getByText("Regenerated answer draft", { exact: false }).waitFor({ state: "visible" });

    await page.goto(`${baseUrl}/apply-queue`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Board" }).click();
    await visible(page, ".boardView", "Apply Queue board");
    await page.locator(".actionBar").getByRole("button", { name: "Mark Applied" }).click();
    await page.getByText("Moved Stripe to Applied", { exact: false }).waitFor({ state: "visible" });

    await page.goto(`${baseUrl}/settings`, { waitUntil: "domcontentloaded" });
    await page.locator(".actionBar").getByRole("button", { name: "Save" }).click();
    await page.getByText("Settings saved", { exact: false }).waitFor({ state: "visible" });

    await page.goto(`${baseUrl}/model-health`, { waitUntil: "domcontentloaded" });
    await page.locator(".pageHeaderActions").getByRole("button", { name: "Run Diagnostic" }).click();
    await page.getByText("Diagnostic complete", { exact: false }).waitFor({ state: "visible" });

    await page.setViewportSize({ width: 720, height: 920 });
    await page.goto(`${baseUrl}/jobs`, { waitUntil: "domcontentloaded" });
    await visible(page, ".mobileRouteRail", "mobile route rail");
    await assertNoDocumentOverflow(page, "jobs mobile");
    await page.screenshot({ path: resolve(screenshotsDir, "jobs-mobile.png"), fullPage: false });

    if (pageErrors.length || consoleMessages.length) {
      throw new Error(`Browser errors found:\n${[...pageErrors, ...consoleMessages].join("\n")}`);
    }
  } finally {
    if (browser) await browser.close();
    await server.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
