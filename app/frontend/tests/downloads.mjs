import process from "node:process";
import { chromium } from "playwright";
import { createServer } from "vite";

const PORT = Number(process.env.JOBFILLER_DOWNLOAD_TEST_PORT || 5181);
const now = new Date("2026-06-24T12:00:00.000Z").toISOString();

const job = {
  id: 1,
  company: "Ramp",
  title: "Software Engineer I, Backend",
  location: "Remote",
  work_model: "Remote",
  source: "manual",
  source_url: "https://example.com/jobs/ramp-backend",
  apply_url: "https://example.com/apply/ramp",
  fit_score: 94,
  status: "QA",
  role_family: "Software Engineering",
  key_requirements: "Python; FastAPI; APIs; testing",
  keywords: "backend; api; platform",
  posting_age_text: "2 hours ago",
  salary: "$120k - $160k",
  materials: "Resume and cover letter.",
  manual_questions: "",
  posted_at: now,
  first_seen_at: now,
  last_seen_at: now,
  updated_at: now,
  latest_grade: "A",
  ready_to_send: true,
  latest_resume_pdf_path: "/tmp/jobfiller/outputs/\resumes\\candidate-resume-ramp.pdf",
  latest_cover_letter_path: "/tmp/jobfiller/outputs/\cover_letters\\candidate-cover-letter-ramp.md",
  latest_artifact_id: 101,
  artifact_count: 1,
  readiness_score: 91,
  open_questions: 0,
};

function json(payload, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  };
}

function attachment(body, contentType, filename) {
  return {
    status: 200,
    headers: {
      "content-type": contentType,
      "content-disposition": `attachment; filename="${filename}"`,
    },
    body,
  };
}

function attachmentForPath(path) {
  if (path === "/api/artifacts/101/resume") {
    return attachment("%PDF-1.4\n% JobFiller resume\n", "application/pdf", "candidate-resume-ramp.pdf");
  }
  if (path === "/api/workbook/latest") {
    return attachment("mock workbook", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "jobfiller-feedback-loop.xlsx");
  }
  if (path === "/api/export/latest.json") return attachment("[]", "application/json", "jobfiller-feedback-loop.json");
  if (path === "/api/export/latest.csv") return attachment("company,title\nRamp,Software Engineer I", "text/csv", "jobfiller-feedback-loop.csv");
  return null;
}

function downloadMiddlewarePlugin() {
  return {
    name: "jobfiller-download-test-api",
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const path = new URL(request.url || "/", "http://127.0.0.1").pathname;
        const mocked = attachmentForPath(path);
        if (!mocked) {
          next();
          return;
        }
        response.statusCode = mocked.status;
        for (const [name, value] of Object.entries(mocked.headers || {})) {
          response.setHeader(name, value);
        }
        response.end(mocked.body);
      });
    },
  };
}

function jobDetail() {
  return {
    job,
    post: {
      summary: "Build backend services and APIs for finance workflows.",
      parsed_requirements: job.key_requirements,
      parsed_keywords: job.keywords,
      compensation: job.salary,
    },
    questions: [],
    artifact: {
      id: job.latest_artifact_id,
      revision: 1,
      resume_tex_path: "/tmp/jobfiller/outputs/\resumes\\ramp\\main.tex",
      resume_pdf_path: job.latest_resume_pdf_path,
      cover_letter_path: job.latest_cover_letter_path,
      resume_pdf_url: `/api/artifacts/${job.latest_artifact_id}/resume`,
      cover_letter_url: `/api/artifacts/${job.latest_artifact_id}/cover-letter`,
      folder_path: "/tmp/jobfiller/outputs/\app_artifacts\\job-1",
      compile_status: "compiled",
      created_at: now,
    },
    grade: {
      overall_grade: "A",
      ready_to_send: true,
      scores: { relevance: 92, impact: 91, skills_match: 93 },
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
  if (path === "/api/jobs" && method === "GET") return route.fulfill(json([job]));
  if (path === "/api/questions" && method === "GET") return route.fulfill(json([]));
  if (path === "/api/profile-facts" && method === "GET") return route.fulfill(json([]));
  if (path === "/api/runs" && method === "GET") return route.fulfill(json([]));
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
      artifact_exports: { workbook_exists: true, json_export_exists: true, csv_export_exists: true },
      run_metrics: { total_runs: 0, successful_runs: 0, failed_runs: 0, running_runs: 0, recent_runs_count: 0 },
      job_status_counts: { QA: 1 },
    }));
  }
  if ((path === "/api/checklist/apply-queue" || path === "/api/checklist/tomorrow") && method === "GET") return route.fulfill(json([]));
  if (path === "/api/jobs/1" && method === "GET") return route.fulfill(json(jobDetail()));
  if (path === "/api/export/workbook" && method === "POST") {
    return route.fulfill(json({
      status: "exported",
      formats: {
        xlsx: "/tmp/jobfiller/outputs/\jobfiller-feedback-loop.xlsx",
        json: "/tmp/jobfiller/outputs/\jobfiller-feedback-loop.json",
        csv: "/tmp/jobfiller/outputs/\jobfiller-feedback-loop.csv",
      },
      urls: {
        xlsx: "/api/workbook/latest",
        json: "/api/export/latest.json",
        csv: "/api/export/latest.csv",
      },
    }));
  }
  const mockedAttachment = attachmentForPath(path);
  if (mockedAttachment) return route.fulfill(mockedAttachment);
  return route.fulfill(json({ detail: `Unhandled mocked API route ${method} ${path}` }, 404));
}

async function main() {
  delete process.env.VITE_API_BASE;
  const viteServer = await createServer({
    root: process.cwd(),
    server: { host: "127.0.0.1", port: PORT, strictPort: false },
    plugins: [downloadMiddlewarePlugin()],
    logLevel: "error",
  });
  let browser;
  try {
    await viteServer.listen();
    const baseUrl = viteServer.resolvedUrls?.local?.[0] || `http://127.0.0.1:${PORT}/`;
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 950 } });
    await context.route("**/api/**", handleApi);
    const page = await context.newPage();
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.getByText("Ramp", { exact: false }).first().waitFor({ state: "visible" });
    await page.getByTestId("jobs-role-1").click();
    await page.getByTestId("artifact-resume-download-1").waitFor({ state: "visible" });
    const resumeHref = await page.getByTestId("artifact-resume-download-1").getAttribute("href");
    if (!resumeHref?.endsWith("/api/artifacts/101/resume")) {
      throw new Error(`Unexpected resume download href ${resumeHref}`);
    }

    const [resumeDownload] = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("artifact-resume-download-1").click(),
    ]);
    if (resumeDownload.suggestedFilename() !== "candidate-resume-ramp.pdf") {
      throw new Error(`Unexpected resume download filename ${resumeDownload.suggestedFilename()} from ${resumeHref}`);
    }

    await page.getByTestId("nav-export").click();
    await page.getByTestId("export-workbook").click();
    await page.getByTestId("export-link-xlsx").waitFor({ state: "visible" });
    const [workbookDownload] = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("export-link-xlsx").click(),
    ]);
    if (workbookDownload.suggestedFilename() !== "jobfiller-feedback-loop.xlsx") {
      throw new Error(`Unexpected workbook download filename ${workbookDownload.suggestedFilename()}`);
    }
  } finally {
    if (browser) await browser.close();
    await viteServer.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});




