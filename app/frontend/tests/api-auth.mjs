import process from "node:process";
import { chromium } from "playwright";
import { createServer } from "vite";

const PORT = Number(process.env.JOBFILLER_API_AUTH_TEST_PORT || 5183);
const TOKEN = "frontend-api-auth-token";
const now = "2026-06-24T12:00:00.000Z";
const transparentLogoPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);

const job = {
  id: 71,
  company: "AuthCo",
  title: "Backend API Engineer",
  location: "Remote",
  work_model: "Remote",
  source: "manual",
  source_url: "https://example.com/jobs/authco-backend",
  apply_url: "https://example.com/apply/authco",
  fit_score: 91,
  status: "QA",
  application_state: "DISCOVERED",
  follow_up_action: "",
  role_family: "Software Engineering",
  key_requirements: "Python; FastAPI; testing",
  keywords: "backend; api; tests",
  posting_age_text: "today",
  salary: "",
  materials: "Resume and cover letter.",
  manual_questions: "",
  posted_at: now,
  first_seen_at: now,
  last_seen_at: now,
  updated_at: now,
  latest_grade: "A",
  latest_grade_scores: {},
  latest_grade_passes: {},
  latest_grade_risks: [],
  latest_grade_breakdown: {},
  ready_to_send: true,
  latest_resume_pdf_path: "/tmp/jobfiller/authco-resume.pdf",
  latest_cover_letter_path: "/tmp/jobfiller/authco-cover.docx",
  latest_artifact_id: 701,
  artifact_count: 1,
  readiness_score: 90,
  open_questions: 0,
};

function json(payload, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  };
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

async function main() {
  delete process.env.VITE_API_BASE;
  const viteServer = await createServer({
    root: process.cwd(),
    server: { host: "127.0.0.1", port: PORT, strictPort: false },
    logLevel: "error",
  });
  const protectedRequests = [];
  const tokenViolations = [];
  const publicTokenLeaks = [];
  let scanCalled = false;
  let browser;
  try {
    await viteServer.listen();
    const baseUrl = viteServer.resolvedUrls?.local?.[0] || `http://127.0.0.1:${PORT}/`;
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
    await mockExternalLogoRequests(context);
    await context.route("**/api/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname;
      const method = request.method();
      const suppliedToken = request.headers()["x-jobfiller-token"] || "";
      const isPublic = path === "/api/health" || path === "/api/session";
      if (isPublic && suppliedToken) {
        publicTokenLeaks.push(`${method} ${path}`);
      }
      if (!isPublic) {
        protectedRequests.push(`${method} ${path}`);
        if (suppliedToken !== TOKEN) {
          tokenViolations.push(`${method} ${path} token=${suppliedToken || "<missing>"}`);
          return route.fulfill(json({ detail: "Missing or invalid local JobFiller token." }, 403));
        }
      }

      if (path === "/api/health") return route.fulfill(json({ status: "ok", version: "test" }));
      if (path === "/api/session") return route.fulfill(json({ mutation_token: TOKEN }));
      if (path === "/api/settings") {
        return route.fulfill(json({
          candidate: { name: "Test Candidate", email: "candidate@example.com", location: "Remote", summary: "Backend engineer.", education: [], experience: [], projects: [] },
          scan: { remote_first: true, preferred_locations: "Remote", default_keywords: "backend, api", default_limit: 20 },
          llm: { provider: "ollama", model: "local-model", ollama_url: "http://127.0.0.1:11434" },
        }));
      }
      if (path === "/api/model-health") {
        return route.fulfill(json({
          model: "local-model",
          configured_model: "local-model",
          provider: "Ollama",
          mode: "local",
          status: "connected",
          scanner: "idle",
          worker: "idle",
          queue_depth: 1,
          artifact_exports: { workbook_exists: false, json_export_exists: false, csv_export_exists: false },
          run_metrics: { total_runs: 0, successful_runs: 0, failed_runs: 0, running_runs: 0, recent_runs_count: 0 },
          job_status_counts: { QA: 1 },
        }));
      }
      if (path === "/api/jobs") return route.fulfill(json([job]));
      if (path === "/api/application-events") return route.fulfill(json([]));
      if (path === "/api/profile-facts") return route.fulfill(json([]));
      if (path === "/api/questions") return route.fulfill(json([]));
      if (path === "/api/runs") {
        return route.fulfill(json(scanCalled ? [{ id: 1, kind: "manual_scan", status: "SUCCEEDED", message: "Mock scan complete.", started_at: now, finished_at: now }] : []));
      }
      if (path === "/api/scans" && method === "POST") {
        scanCalled = true;
        return route.fulfill(json({ run_id: 1, imported: 1, message: "Mock scan complete." }));
      }
      if (path === "/api/checklist/apply-queue" || path === "/api/checklist/tomorrow") return route.fulfill(json([]));
      return route.fulfill(json({ detail: `Unhandled mocked API route ${method} ${path}` }, 404));
    });

    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.getByText("AuthCo", { exact: false }).first().waitFor({ state: "visible" });
    const scanResponse = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/scans" && response.request().method() === "POST";
    });
    await Promise.all([scanResponse, page.getByRole("button", { name: "Scan Now" }).click()]);
    await page.locator(".pageTitleLine h1", { hasText: "Runs & Logs" }).waitFor({ state: "visible" });

    if (!scanCalled) throw new Error("Expected dashboard scan action to call POST /api/scans.");
    if (tokenViolations.length) throw new Error(`Protected API calls missed the token:\n${tokenViolations.join("\n")}`);
    if (publicTokenLeaks.length) throw new Error(`Public bootstrap calls should not carry the mutation token:\n${publicTokenLeaks.join("\n")}`);
    if (!protectedRequests.some((item) => item === "POST /api/scans")) {
      throw new Error(`Expected POST /api/scans in protected request log, got ${protectedRequests.join(", ")}`);
    }
    if (pageErrors.length) throw new Error(`Page errors found:\n${pageErrors.join("\n")}`);
  } finally {
    if (browser) await browser.close();
    await viteServer.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
