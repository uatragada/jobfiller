import process from "node:process";
import { chromium } from "playwright";
import { createServer } from "vite";

const PORT = Number(process.env.JOBFILLER_PERFORMANCE_TEST_PORT || 5182);
const now = new Date("2026-06-24T12:00:00.000Z");
const thresholds = {
  loadMs: Number(process.env.JOBFILLER_PERF_LOAD_MS || 1000),
  filterMs: Number(process.env.JOBFILLER_PERF_FILTER_MS || 300),
  detailMs: Number(process.env.JOBFILLER_PERF_DETAIL_MS || 500),
};

const jobs = Array.from({ length: 1000 }, (_, index) => {
  const id = index + 1;
  const company = `Company ${id}`;
  return {
    id,
    company,
    title: `Backend Engineer ${id}`,
    location: id % 3 === 0 ? "Chicago, IL" : "Remote",
    work_model: id % 3 === 0 ? "Hybrid" : "Remote",
    source: id % 2 === 0 ? "linkedin" : "manual",
    source_url: `https://example.com/jobs/${id}`,
    apply_url: `https://example.com/apply/${id}`,
    fit_score: 100 - (id % 50),
    status: id % 7 === 0 ? "NEEDS_INFO" : "QA",
    role_family: "Software Engineering",
    key_requirements: "Python; FastAPI; APIs; testing; PostgreSQL",
    keywords: "backend; api; platform",
    posting_age_text: `${id} hours ago`,
    salary: "$110k - $150k",
    materials: "Resume and cover letter.",
    manual_questions: "",
    posted_at: new Date(now.getTime() - id * 3600 * 1000).toISOString(),
    first_seen_at: now.toISOString(),
    last_seen_at: now.toISOString(),
    updated_at: now.toISOString(),
    latest_grade: id % 7 === 0 ? "B+" : "A",
    ready_to_send: id % 7 !== 0,
    latest_resume_pdf_path: `/tmp/jobfiller/outputs/\resumes\\candidate-resume-company-${id}.pdf`,
    latest_cover_letter_path: `/tmp/jobfiller/outputs/\cover_letters\\candidate-cover-letter-company-${id}.md`,
    latest_artifact_id: 1000 + id,
    artifact_count: 1,
    readiness_score: id % 7 === 0 ? 62 : 91,
    open_questions: id % 7 === 0 ? 1 : 0,
  };
});

function json(payload, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  };
}

function detailFor(job) {
  return {
    job,
    post: {
      summary: `Build backend services for ${job.company} across APIs, data validation, and internal workflow automation.`,
      parsed_requirements: job.key_requirements,
      parsed_keywords: job.keywords,
      compensation: job.salary,
    },
    questions: [],
    artifact: {
      id: job.latest_artifact_id,
      revision: 1,
      resume_tex_path: `/tmp/jobfiller/outputs/\resumes\\company-${job.id}\\main.tex`,
      resume_pdf_path: job.latest_resume_pdf_path,
      cover_letter_path: job.latest_cover_letter_path,
      resume_pdf_url: `/api/artifacts/${job.latest_artifact_id}/resume`,
      cover_letter_url: `/api/artifacts/${job.latest_artifact_id}/cover-letter`,
      folder_path: `/tmp/jobfiller/outputs/\app_artifacts\\job-${job.id}`,
      compile_status: "compiled",
      created_at: now.toISOString(),
    },
    grade: {
      overall_grade: job.latest_grade,
      ready_to_send: job.ready_to_send,
      scores: { relevance: 92, impact: 90, skills_match: 93 },
      risks: [],
    },
  };
}

async function handleApi(route) {
  const request = route.request();
  const url = new URL(request.url());
  const path = url.pathname;
  const method = request.method();

  if (path === "/api/health") return route.fulfill(json({ status: "ok" }));
  if (path === "/api/session") return route.fulfill(json({ mutation_token: "test-token" }));
  if (path === "/api/settings" && method === "GET") {
    return route.fulfill(json({
      candidate: { name: "Test Candidate", email: "candidate@example.com", location: "Remote", summary: "Backend engineer test profile.", education: [], experience: [], projects: [] },
      scan: { remote_first: true, preferred_locations: "Remote, Hybrid", default_keywords: "backend, api", default_limit: 20 },
      llm: { provider: "ollama", model: "example-local-model:latest", ollama_url: "http://127.0.0.1:11434" },
    }));
  }
  if (path === "/api/jobs" && method === "GET") return route.fulfill(json(jobs));
  if (path === "/api/questions" && method === "GET") return route.fulfill(json([]));
  if (path === "/api/profile-facts" && method === "GET") return route.fulfill(json([]));
  if (path === "/api/runs" && method === "GET") return route.fulfill(json([]));
  if ((path === "/api/checklist/apply-queue" || path === "/api/checklist/tomorrow") && method === "GET") return route.fulfill(json([]));
  if (path === "/api/model-health" && method === "GET") {
    return route.fulfill(json({
      model: "example-local-model:latest",
      configured_model: "example-local-model:latest",
      provider: "Ollama",
      mode: "local",
      status: "connected",
      scanner: "idle",
      worker: "idle",
      queue_depth: 0,
      artifact_exports: { workbook_exists: false, json_export_exists: false, csv_export_exists: false },
      run_metrics: { total_runs: 0, successful_runs: 0, failed_runs: 0, running_runs: 0, recent_runs_count: 0 },
      job_status_counts: { QA: 857, NEEDS_INFO: 143 },
    }));
  }
  const jobMatch = path.match(/^\/api\/jobs\/(\d+)$/);
  if (jobMatch && method === "GET") {
    const job = jobs.find((row) => row.id === Number(jobMatch[1]));
    return route.fulfill(job ? json(detailFor(job)) : json({ detail: "Not found" }, 404));
  }
  return route.fulfill(json({ detail: `Unhandled mocked API route ${method} ${path}` }, 404));
}

async function main() {
  delete process.env.VITE_API_BASE;
  const viteServer = await createServer({
    root: process.cwd(),
    server: { host: "127.0.0.1", port: PORT, strictPort: false },
    logLevel: "error",
  });
  let browser;
  try {
    await viteServer.listen();
    const baseUrl = viteServer.resolvedUrls?.local?.[0] || `http://127.0.0.1:${PORT}/`;
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1440, height: 950 } });
    await context.route("**/api/**", handleApi);
    const page = await context.newPage();

    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.getByText("1000 jobs", { exact: false }).waitFor({ state: "visible" });

    const loadStart = Date.now();
    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });
    await page.getByText("1000 jobs", { exact: false }).waitFor({ state: "visible" });
    await page.getByTestId("jobs-role-1").waitFor({ state: "visible" });
    const loadMs = Date.now() - loadStart;

    const filterStart = Date.now();
    await page.getByTestId("jobs-search").fill("Company 999");
    await page.getByTestId("jobs-role-999").waitFor({ state: "visible" });
    await page.getByText("1-1 of 1", { exact: false }).waitFor({ state: "visible" });
    const filterMs = Date.now() - filterStart;

    const detailStart = Date.now();
    await page.getByTestId("jobs-role-999").click();
    await page.getByText("Build backend services for Company 999", { exact: false }).waitFor({ state: "visible" });
    const detailMs = Date.now() - detailStart;

    const failures = [];
    if (loadMs > thresholds.loadMs) failures.push(`load ${loadMs}ms > ${thresholds.loadMs}ms`);
    if (filterMs > thresholds.filterMs) failures.push(`filter ${filterMs}ms > ${thresholds.filterMs}ms`);
    if (detailMs > thresholds.detailMs) failures.push(`detail ${detailMs}ms > ${thresholds.detailMs}ms`);
    if (failures.length) {
      throw new Error(`Performance thresholds failed: ${failures.join("; ")}`);
    }
    console.log(`Performance OK: load=${loadMs}ms filter=${filterMs}ms detail=${detailMs}ms`);
  } finally {
    if (browser) await browser.close();
    await viteServer.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});




