import http from "node:http";
import process from "node:process";
import { chromium } from "playwright";
import { createServer } from "vite";

const PORT = Number(process.env.JOBFILLER_BUTTON_TEST_PORT || 5178);
const BASE_URL = `http://127.0.0.1:${PORT}`;

const now = new Date("2026-06-24T12:00:00.000Z");
let artifactRevision = 2;
let nextJobId = 50;
let nextFactId = 10;
let exported = false;

const runs = [
  {
    id: 1,
    kind: "manual_scan",
    status: "SUCCEEDED",
    message: "Imported/updated jobs newest-first.",
    started_at: now.toISOString(),
    finished_at: now.toISOString(),
  },
];

const jobs = Array.from({ length: 12 }, (_, index) => {
  const id = index + 1;
  const companies = [
    "Ramp",
    "Brex",
    "Datadog",
    "Chime",
    "Snowflake",
    "Shopify",
    "Plaid",
    "Amex",
    "SeatGeek",
    "Rokt",
    "Intuit",
    "StubHub",
  ];
  const company = companies[index];
  const hasArtifact = id <= 4;
  const status = id === 2 ? "NEEDS_INFO" : id === 3 ? "GENERATING" : "QA";
  return {
    id,
    company,
    title: id === 1 ? "Software Engineer I, Backend" : `Backend Engineer ${id}`,
    location: id % 2 === 0 ? "Remote" : "Austin, TX",
    work_model: id % 2 === 0 ? "Remote" : "Hybrid",
    source: id % 3 === 0 ? "linkedin" : "manual",
    source_url: `https://www.linkedin.com/jobs/view/${9000 + id}`,
    apply_url: `https://example.com/apply/${id}`,
    fit_score: 94 - id,
    status,
    role_family: "Software Engineering",
    key_requirements: "Python; FastAPI; PostgreSQL; APIs; Testing",
    keywords: "backend; api; platform; testing",
    posting_age_text: id === 1 ? "2 hours ago" : `${id} days ago`,
    salary: "$120k - $160k",
    materials: "Resume and cover letter.",
    manual_questions: id === 2 ? "Confirm finance domain motivation." : "",
    posted_at: new Date(now.getTime() - id * 3600 * 1000).toISOString(),
    first_seen_at: now.toISOString(),
    last_seen_at: now.toISOString(),
    updated_at: now.toISOString(),
    latest_grade: id <= 4 ? "A" : "B+",
    ready_to_send: id !== 2,
    latest_resume_pdf_path: hasArtifact ? `/tmp/jobfiller/outputs/\resumes\\candidate-resume-${company.toLowerCase()}.pdf` : null,
    latest_cover_letter_path: hasArtifact ? `/tmp/jobfiller/outputs/\cover_letters\\candidate-cover-letter-${company.toLowerCase()}.md` : null,
    latest_artifact_id: hasArtifact ? 100 + id : null,
    artifact_count: hasArtifact ? 2 : 0,
    readiness_score: id === 2 ? 55 : 90 - id,
    open_questions: id === 2 ? 1 : 0,
  };
});

let questions = [
  {
    id: 201,
    job_id: 2,
    company: "Brex",
    title: "Backend Engineer 2",
    tag: "finance_motivation",
    impact: "High",
    impact_score: 95,
    question_text: "Have you worked with financial data, payments, or banking APIs outside of coursework?",
    blocking: true,
    status: "OPEN",
    answer: "",
    created_at: now.toISOString(),
  },
  {
    id: 202,
    job_id: 3,
    company: "Datadog",
    title: "Backend Engineer 3",
    tag: "kubernetes",
    impact: "Medium",
    impact_score: 65,
    question_text: "What is your hands-on experience with Kubernetes in production or staging environments?",
    blocking: true,
    status: "OPEN",
    answer: "",
    created_at: new Date(now.getTime() - 86400 * 1000).toISOString(),
  },
  {
    id: 203,
    job_id: 1,
    company: "Ramp",
    title: "Software Engineer I, Backend",
    tag: "go_backend",
    impact: "High",
    impact_score: 85,
    question_text: "Do you have experience writing production code in Go?",
    blocking: true,
    status: "SKIPPED",
    answer: "",
    created_at: new Date(now.getTime() - 2 * 86400 * 1000).toISOString(),
  },
];

let facts = [
  {
    id: 1,
    tag: "remote_preference",
    question_text: "Remote preference",
    answer: "Remote-first backend roles are preferred; hybrid roles near my location are acceptable.",
    confidence: 1,
    updated_at: now.toISOString(),
  },
];

function json(payload, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  };
}

function text(payload, contentType = "text/plain") {
  return { status: 200, contentType, body: payload };
}

function jobDetail(job) {
  const artifact = job.latest_artifact_id
    ? {
        id: job.latest_artifact_id,
        revision: artifactRevision,
        resume_tex_path: `/tmp/jobfiller/outputs/\resumes\\${job.company.toLowerCase()}\\main.tex`,
        resume_pdf_path: job.latest_resume_pdf_path,
        cover_letter_path: job.latest_cover_letter_path,
        resume_pdf_url: `/api/artifacts/${job.latest_artifact_id}/resume`,
        cover_letter_url: `/api/artifacts/${job.latest_artifact_id}/cover-letter`,
        folder_path: `/tmp/jobfiller/outputs/\app_artifacts\\job-${job.id}`,
        compile_status: "compiled",
        created_at: now.toISOString(),
      }
    : {};
  return {
    job,
    post: {
      summary: "Build backend services and APIs for a high-scale product platform.",
      parsed_requirements: job.key_requirements,
      parsed_keywords: job.keywords,
      compensation: job.salary,
    },
    questions: questions.filter((question) => question.job_id === job.id),
    artifact,
    grade: {
      overall_grade: job.latest_grade || "B+",
      ready_to_send: job.ready_to_send,
      risks: ["Clarify domain depth before final submission."],
      scores: {
        relevance: 92,
        impact: 90,
        skills_match: 93,
        clarity: 90,
        ats_readiness: 90,
      },
    },
  };
}

function updateArtifactForJob(jobId) {
  const job = jobs.find((row) => row.id === jobId);
  if (!job) return null;
  job.latest_artifact_id = job.latest_artifact_id || 100 + job.id;
  job.latest_resume_pdf_path = `/tmp/jobfiller/outputs/\resumes\\candidate-resume-${job.company.toLowerCase()}.pdf`;
  job.latest_cover_letter_path = `/tmp/jobfiller/outputs/\cover_letters\\candidate-cover-letter-${job.company.toLowerCase()}.md`;
  job.artifact_count = Math.max(job.artifact_count, 1);
  job.status = "QA";
  job.updated_at = new Date().toISOString();
  return job;
}

async function parseBody(request) {
  const textBody = request.postData() || "{}";
  try {
    return JSON.parse(textBody);
  } catch {
    return {};
  }
}

async function handleApi(route) {
  const request = route.request();
  const url = new URL(request.url());
  const path = url.pathname;
  const method = request.method();

  if (!path.startsWith("/api")) {
    return route.continue();
  }

  if (path === "/api/health") return route.fulfill(json({ status: "ok" }));
  if (path === "/api/session") return route.fulfill(json({ mutation_token: "test-token" }));
  if (path === "/api/settings" && method === "GET") {
    return route.fulfill(json({
      candidate: { name: "Test Candidate", email: "candidate@example.com", location: "Remote", summary: "Backend engineer test profile.", education: [], experience: [], projects: [] },
      scan: { remote_first: true, preferred_locations: "Remote, Hybrid", default_keywords: "backend, api", default_limit: 20 },
      llm: { provider: "ollama", model: "example-local-model:latest", ollama_url: "http://127.0.0.1:11434" },
    }));
  }
  if (path === "/api/settings" && method === "PUT") return route.fulfill(json(await parseBody(request)));
  if (path === "/api/model-health") {
    return route.fulfill(json({
      model: "example-local-model:latest",
      configured_model: "example-local-model:latest",
      provider: "Ollama",
      mode: "local",
      status: "connected",
      scanner: "idle",
      worker: "idle",
      queue_depth: questions.filter((question) => question.status === "OPEN").length,
      artifact_exports: {
        workbook_exists: exported,
        json_export_exists: exported,
        csv_export_exists: exported,
      },
      run_metrics: {
        total_runs: runs.length,
        successful_runs: runs.filter((run) => run.status === "SUCCEEDED").length,
        failed_runs: 0,
        running_runs: 0,
        recent_runs_count: runs.length,
      },
      job_status_counts: { QA: 10, NEEDS_INFO: 1, GENERATING: 1 },
    }));
  }

  if (path === "/api/jobs" && method === "GET") return route.fulfill(json(jobs));
  if (path === "/api/scans" && method === "POST") {
    const run = {
      id: runs.length + 1,
      kind: "manual_scan",
      status: "SUCCEEDED",
      message: "Mock scan complete.",
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
    };
    runs.unshift(run);
    return route.fulfill(json({ run_id: run.id, imported: jobs.length, message: "Mock scan complete." }));
  }
  if (path === "/api/jobs/import" && method === "POST") {
    const payload = await parseBody(request);
    const imported = {
      ...jobs[0],
      id: nextJobId++,
      company: payload.company || "ImportedCo",
      title: payload.title || "Imported Backend Engineer",
      source_url: payload.url,
      canonical_url: payload.url,
      apply_url: payload.url,
      latest_artifact_id: null,
      latest_resume_pdf_path: null,
      latest_cover_letter_path: null,
      artifact_count: 0,
      status: "QA",
      posting_age_text: "just now",
      updated_at: new Date().toISOString(),
    };
    jobs.unshift(imported);
    return route.fulfill(json(imported));
  }

  const jobMatch = path.match(/^\/api\/jobs\/(\d+)$/);
  if (jobMatch && method === "GET") {
    const job = jobs.find((row) => row.id === Number(jobMatch[1]));
    return route.fulfill(job ? json(jobDetail(job)) : json({ detail: "Not found" }, 404));
  }
  if (jobMatch && method === "PATCH") {
    const job = jobs.find((row) => row.id === Number(jobMatch[1]));
    if (!job) return route.fulfill(json({ detail: "Not found" }, 404));
    Object.assign(job, await parseBody(request), { updated_at: new Date().toISOString() });
    return route.fulfill(json(job));
  }
  if (jobMatch && method === "DELETE") {
    const index = jobs.findIndex((row) => row.id === Number(jobMatch[1]));
    if (index >= 0) jobs.splice(index, 1);
    return route.fulfill(json({ status: "deleted" }));
  }

  const jobArtifactGenerateMatch = path.match(/^\/api\/jobs\/(\d+)\/artifacts\/generate$/);
  if (jobArtifactGenerateMatch && method === "POST") {
    const job = updateArtifactForJob(Number(jobArtifactGenerateMatch[1]));
    return route.fulfill(job ? json(job) : json({ detail: "Not found" }, 404));
  }

  const jobArtifactsMatch = path.match(/^\/api\/jobs\/(\d+)\/artifacts$/);
  if (jobArtifactsMatch && method === "GET") {
    const job = jobs.find((row) => row.id === Number(jobArtifactsMatch[1]));
    return route.fulfill(json({
      job_id: job?.id,
      latest_artifact_id: job?.latest_artifact_id,
      artifacts: job?.latest_artifact_id ? [jobDetail(job).artifact] : [],
    }));
  }

  const jobQuestionsMatch = path.match(/^\/api\/jobs\/(\d+)\/questions$/);
  if (jobQuestionsMatch && method === "GET") {
    const status = url.searchParams.get("status") || "OPEN";
    const rows = questions.filter((question) => question.job_id === Number(jobQuestionsMatch[1]));
    return route.fulfill(json(status === "all" ? rows : rows.filter((question) => question.status === status)));
  }

  if (path === "/api/questions" && method === "GET") {
    const status = url.searchParams.get("status") || "OPEN";
    const tag = url.searchParams.get("tag") || "all";
    let rows = [...questions];
    if (status !== "all") rows = rows.filter((question) => question.status === status);
    if (tag !== "all") rows = rows.filter((question) => question.tag === tag);
    return route.fulfill(json(rows));
  }

  const questionAnswerMatch = path.match(/^\/api\/questions\/(\d+)\/answer$/);
  if (questionAnswerMatch && method === "POST") {
    const question = questions.find((row) => row.id === Number(questionAnswerMatch[1]));
    if (!question) return route.fulfill(json({ detail: "Not found" }, 404));
    const payload = await parseBody(request);
    question.answer = payload.answer;
    question.status = "ANSWERED";
    facts.unshift({
      id: nextFactId++,
      tag: question.tag,
      question_text: question.question_text,
      answer: question.answer,
      confidence: 1,
      updated_at: new Date().toISOString(),
    });
    return route.fulfill(json({ id: question.id, status: question.status, affected_jobs: [question.job_id] }));
  }

  const questionSkipMatch = path.match(/^\/api\/questions\/(\d+)\/skip$/);
  if (questionSkipMatch && method === "POST") {
    const question = questions.find((row) => row.id === Number(questionSkipMatch[1]));
    if (!question) return route.fulfill(json({ detail: "Not found" }, 404));
    question.status = "SKIPPED";
    return route.fulfill(json({ id: question.id, status: "SKIPPED" }));
  }

  if (path === "/api/profile-facts" && method === "GET") return route.fulfill(json(facts));
  if (path === "/api/profile-facts" && method === "POST") {
    const payload = await parseBody(request);
    const fact = {
      id: nextFactId++,
      tag: payload.tag,
      question_text: payload.question_text || "",
      answer: payload.answer,
      confidence: payload.confidence || 1,
      updated_at: new Date().toISOString(),
    };
    facts.unshift(fact);
    return route.fulfill(json(fact));
  }
  const factMatch = path.match(/^\/api\/profile-facts\/(\d+)$/);
  if (factMatch && method === "PATCH") {
    const fact = facts.find((row) => row.id === Number(factMatch[1]));
    if (!fact) return route.fulfill(json({ detail: "Not found" }, 404));
    Object.assign(fact, await parseBody(request), { updated_at: new Date().toISOString() });
    return route.fulfill(json(fact));
  }
  if (factMatch && method === "DELETE") {
    facts = facts.filter((row) => row.id !== Number(factMatch[1]));
    return route.fulfill(json({ status: "deleted" }));
  }

  if (path === "/api/runs" && method === "GET") return route.fulfill(json(runs));
  const runMatch = path.match(/^\/api\/runs\/(\d+)$/);
  if (runMatch && method === "GET") {
    const run = runs.find((row) => row.id === Number(runMatch[1]));
    return route.fulfill(json({ ...run, logs: ["mock run detail"], duration_ms: 25 }));
  }

  if (path === "/api/checklist/tomorrow" && method === "GET") {
    return route.fulfill(json(jobs.slice(0, 4).map((job, index) => ({
      job_id: job.id,
      apply_order: index + 1,
      company: job.company,
      title: job.title,
      status: job.status,
      apply_url: job.apply_url,
      location: job.location,
      work_model: job.work_model,
      fit_score: job.fit_score,
      grade: job.latest_grade,
      ready_to_send: job.ready_to_send,
      materials: job.materials,
      manual_questions: job.manual_questions,
      resume_pdf_path: job.latest_resume_pdf_path,
      cover_letter_path: job.latest_cover_letter_path,
      resume_tex_path: job.latest_artifact_id ? `/tmp/jobfiller/outputs/\resumes\\${job.company}\\main.tex` : "",
      posting_age_text: job.posting_age_text,
      posted_at: job.posted_at,
      first_seen_at: job.first_seen_at,
    }))));
  }

  if (path === "/api/workbook/export" && method === "POST") {
    exported = true;
    return route.fulfill(json({ status: "exported", path: "/tmp/jobfiller/outputs/\jobfiller-feedback-loop.xlsx", url: "/api/workbook/latest" }));
  }
  if (path === "/api/export/workbook" && method === "POST") {
    exported = true;
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
  if (path === "/api/workbook/latest") return route.fulfill(text("mock xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"));
  if (path === "/api/export/latest.json") return route.fulfill(json(jobs));
  if (path === "/api/export/latest.csv") return route.fulfill(text("company,title\nRamp,Software Engineer I", "text/csv"));

  const artifactContentMatch = path.match(/^\/api\/artifacts\/(\d+)\/content$/);
  if (artifactContentMatch && method === "GET") {
    return route.fulfill(json({
      artifact_id: Number(artifactContentMatch[1]),
      job_id: 1,
      revision: artifactRevision,
      kind: url.searchParams.get("kind") || "cover-letter",
      path: "/tmp/jobfiller/outputs/\mock-artifact.txt",
      content: "Mock artifact content.",
    }));
  }
  if (artifactContentMatch && method === "PATCH") {
    artifactRevision += 1;
    return route.fulfill(json({
      artifact_id: Number(artifactContentMatch[1]) + 1,
      job_id: 1,
      revision: artifactRevision,
      resume_pdf_path: jobs[0].latest_resume_pdf_path,
      resume_tex_path: "/tmp/jobfiller/outputs/\resumes\\ramp\\main.tex",
      cover_letter_path: jobs[0].latest_cover_letter_path,
      compile_status: "compiled",
    }));
  }

  const artifactActionMatch = path.match(/^\/api\/artifacts\/(\d+)\/(grade|open-folder|open|resume|cover-letter|latex|download)$/);
  if (artifactActionMatch) {
    const action = artifactActionMatch[2];
    if (action === "grade" && method === "POST") {
      return route.fulfill(json({ status: "graded", artifact_id: Number(artifactActionMatch[1]), job_id: 1, overall_grade: "A" }));
    }
    if (["open-folder", "open"].includes(action)) {
      return route.fulfill(json({ status: "opened", artifact_id: Number(artifactActionMatch[1]), folder: "/tmp/jobfiller/outputs" }));
    }
    return route.fulfill(text(`mock ${action}`));
  }

  const assistMatch = path.match(/^\/api\/jobs\/(\d+)\/assist-upload$/);
  if (assistMatch && method === "POST") {
    return route.fulfill(json({ status: "launched", path: "/tmp/jobfiller/outputs/\mock.pdf" }));
  }

  return route.fulfill(json({ detail: `Unhandled mocked API route ${method} ${path}` }, 404));
}

function waitForServer(url, timeoutMs = 15000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      http.get(url, (response) => {
        response.resume();
        resolve();
      }).on("error", (error) => {
        if (Date.now() - started > timeoutMs) {
          reject(error);
          return;
        }
        setTimeout(tick, 250);
      });
    };
    tick();
  });
}

async function expectVisible(page, selector, label) {
  await page.locator(selector).waitFor({ state: "visible", timeout: 5000 }).catch((error) => {
    throw new Error(`Expected visible ${label} (${selector}): ${error.message}`);
  });
}

async function expectText(page, text, label = text) {
  await page.getByText(text, { exact: false }).filter({ visible: true }).first().waitFor({ state: "visible", timeout: 5000 }).catch((error) => {
    throw new Error(`Expected visible text ${label}: ${error.message}`);
  });
}

async function click(page, testId) {
  await page.getByTestId(testId).click();
}

async function assertSrsAccessibility(page, label) {
  const result = await page.evaluate(() => {
    function isVisible(el) {
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    }
    function accessibleLabel(el) {
      const id = el.getAttribute("id");
      const explicit = id ? document.querySelector(`label[for="${CSS.escape(id)}"]`)?.textContent?.trim() : "";
      const implicit = el.closest("label")?.textContent?.trim() || "";
      return [
        el.getAttribute("aria-label"),
        el.getAttribute("title"),
        el.textContent,
        el.getAttribute("placeholder"),
        explicit,
        implicit,
      ]
        .filter(Boolean)
        .map((value) => value.replace(/\s+/g, " ").trim())
        .find(Boolean) || "";
    }
    const missingNames = [...document.querySelectorAll("button,a[href],input,select,textarea")]
      .filter(isVisible)
      .map((el) => ({
        tag: el.tagName.toLowerCase(),
        testId: el.getAttribute("data-testid"),
        href: el.getAttribute("href"),
        html: el.outerHTML.slice(0, 180),
        label: accessibleLabel(el),
      }))
      .filter((item) => !item.label);
    const tables = [...document.querySelectorAll('[role="table"],table')].map((el) => ({
      label: el.getAttribute("aria-label") || "",
      rows: el.querySelectorAll('[role="row"],tr').length,
      headers: el.querySelectorAll('[role="columnheader"],th').length,
    }));
    const tablists = [...document.querySelectorAll('[role="tablist"]')].map((el) => ({
      label: el.getAttribute("aria-label") || "",
      tabs: el.querySelectorAll('[role="tab"]').length,
      selected: el.querySelectorAll('[role="tab"][aria-selected="true"]').length,
    }));
    return { missingNames, tables, tablists };
  });

  const jobsTable = result.tables.find((table) => table.label === "Jobs table");
  const questionsTable = result.tables.find((table) => table.label === "Blocking questions table");
  const detailTabs = result.tablists.find((tablist) => tablist.label === "Job detail tabs");

  if (result.missingNames.length || !jobsTable || jobsTable.rows < 2 || jobsTable.headers < 10 || !questionsTable || questionsTable.rows < 1 || questionsTable.headers < 7 || !detailTabs || detailTabs.tabs < 4 || detailTabs.selected !== 1) {
    throw new Error(`SRS accessibility audit failed at ${label}:\n${JSON.stringify(result, null, 2)}`);
  }
}

async function assertGenericVisibleText(page, label) {
  const bodyText = await page.locator("body").innerText();
  const forbidden = ["local to me"];
  const matches = forbidden.filter((term) => bodyText.toLowerCase().includes(term.toLowerCase()));
  if (matches.length) {
    throw new Error(`Generic visible-text audit failed at ${label}: ${matches.join(", ")}`);
  }
}

async function main() {
  delete process.env.VITE_API_BASE;
  const viteServer = await createServer({
    root: process.cwd(),
    server: {
      host: "127.0.0.1",
      port: PORT,
      strictPort: true,
    },
    logLevel: "error",
  });
  let browser;
  const consoleMessages = [];
  const pageErrors = [];
  try {
    await viteServer.listen();
    await waitForServer(BASE_URL);
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 950 },
      permissions: ["clipboard-read", "clipboard-write"],
    });
    await context.route("**/api/**", handleApi);
    const page = await context.newPage();
    page.on("console", (message) => {
      if (["error", "warning"].includes(message.type())) consoleMessages.push(`${message.type()}: ${message.text()}`);
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
    await expectText(page, "JobFiller");
    await expectVisible(page, '[data-testid="scan-now"]', "Scan Now");
    await expectText(page, "Ramp");
    await assertSrsAccessibility(page, "initial jobs dashboard");
    await assertGenericVisibleText(page, "initial jobs dashboard");

    await click(page, "scan-now");
    await expectText(page, "Scan complete");

    await page.getByTestId("import-url-input").fill("not a url");
    await expectVisible(page, '[data-testid="import-url-button"]:disabled', "disabled invalid import");
    await page.getByTestId("import-url-input").fill("https://example.com/jobs/imported-backend");
    await click(page, "import-url-button");
    await expectText(page, "Imported job URL");

    await click(page, "health-pill-scanner");
    await expectText(page, "Runs & Logs");
    await click(page, "health-pill-worker");
    await expectText(page, "Generate Queue");
    await page.getByRole("button", { name: /Local LLM:/ }).click();
    await expectText(page, "Model Health");
    await click(page, "command-open-settings");
    await expectText(page, "Settings");
    await click(page, "top-user-menu");
    await expectText(page, "Remote-first mode");
    await click(page, "top-user-settings");
    await expectText(page, "Settings");

    for (const [testId, text] of [
      ["nav-jobs", "Ramp"],
      ["nav-questions", "Questions"],
      ["nav-tomorrow", "Tomorrow Checklist"],
      ["nav-facts", "Profile Facts"],
      ["nav-runs", "Runs & Logs"],
      ["nav-reprocess", "Generate Queue"],
      ["nav-agent", "Agent Import / MCP"],
      ["nav-assist", "Assist Upload"],
      ["nav-export", "Export Workbook"],
      ["nav-settings", "Settings"],
      ["nav-health", "Model Health"],
    ]) {
      await click(page, testId);
      await expectText(page, text);
    }

    await click(page, "nav-jobs");
    await page.getByTestId("jobs-search").fill("Brex");
    await expectText(page, "Brex");
    await page.getByTestId("jobs-filter-status").selectOption("NEEDS_INFO");
    await expectText(page, "NEEDS_INFO");
    await page.getByTestId("jobs-filter-source").selectOption("manual");
    await page.getByTestId("jobs-filter-work-model").selectOption("Remote");
    await page.getByTestId("jobs-sort").selectOption("fit");
    await click(page, "jobs-advanced-toggle");
    await expectText(page, "Remote-first ranking");
    await click(page, "advanced-clear-filters");
    await page.getByTestId("jobs-search").fill("");
    await click(page, "jobs-location-toggle");
    await click(page, "location-chip-remote");
    await page.getByTestId("location-custom").fill("Remote");
    await click(page, "location-clear");
    await click(page, "location-apply");

    await click(page, "jobs-page-next");
    await expectText(page, "11-13 of");
    await click(page, "jobs-page-prev");
    await expectText(page, "1-10 of");
    await page.getByTestId("jobs-page-size").selectOption("20");
    await expectText(page, "1-13 of");

    await click(page, "jobs-row-select-1");
    await expectVisible(page, '[data-testid="jobs-reprocess-selected"]', "jobs reprocess selected");
    await click(page, "jobs-reprocess-selected");
    await expectText(page, "Generated 1 selected job pack files.");
    await click(page, "jobs-role-2");
    await expectText(page, "Brex");
    await expectVisible(page, '[data-testid="inspector-apply-2"]', "inspector apply link");

    await page.getByTestId("dashboard-question-sort").selectOption("recent");
    await click(page, "question-open-list");
    await expectText(page, "Questions");
    await page.getByTestId("questions-search").fill("finance");
    await expectText(page, "financial data");
    await page.getByTestId("questions-status-filter").selectOption("OPEN");
    await page.getByTestId("questions-tag-filter").selectOption("finance_motivation");
    await page.getByTestId("questions-sort").selectOption("impact");
    await page.getByTestId("question-answer-201").fill("I have worked with payment-like validation and finance-oriented workflow data.");
    await click(page, "question-save-201");
    await expectText(page, "Saved answer");
    await page.getByTestId("questions-search").fill("");
    await page.getByTestId("questions-status-filter").selectOption("OPEN");
    await page.getByTestId("questions-tag-filter").selectOption("all");
    await click(page, "question-skip-202");
    await expectText(page, "Question skipped");
    await page.getByTestId("questions-status-filter").selectOption("all");
    await click(page, "question-open-201");
    await expectText(page, "Backend Engineer 2");

    await click(page, "inspector-tab-grade");
    await click(page, "grade-open-report");
    await expectText(page, "Full Local LLM Report");
    await click(page, "report-modal-close");
    await click(page, "inspector-tab-notes");
    await page.locator(".inspectorList textarea").fill("Apply tomorrow morning.");
    await click(page, "notes-save");
    await expectText(page, "Saved job notes");
    await click(page, "inspector-tab-artifacts");
    await click(page, "artifact-reprocess-2");
    await expectText(page, "Generated resume and cover letter for selected job");
    await click(page, "artifact-resume-folder-2");
    await expectText(page, "Opened artifact output folder");
    await click(page, "artifact-resume-regrade-2");
    await expectText(page, "Local LLM regrade completed");
    await click(page, "artifact-cover-edit-2");
    await expectText(page, "Edit Cover Letter");
    await page.getByTestId("artifact-editor-textarea").fill("Updated cover letter content.");
    await click(page, "save-artifact-editor");
    await expectText(page, "Saved artifact edit as a new revision");
    await click(page, "artifact-assist-resume-2");
    await expectText(page, "Upload helper launched");
    await click(page, "inspector-close");
    await expectVisible(page, ".board.detailClosed", "closed inspector layout");

    await click(page, "nav-tomorrow");
    await click(page, "tomorrow-copy-list");
    await expectText(page, "Copied");

    await click(page, "nav-facts");
    await page.getByTestId("fact-tag-input").fill("backend_depth");
    await page.getByTestId("fact-question-input").fill("Backend depth");
    await page.getByTestId("fact-confidence-input").fill("0.9");
    await page.getByTestId("fact-answer-input").fill("Built FastAPI services and document-processing workflows.");
    await click(page, "fact-save");
    await expectText(page, "Created profile fact");
    await click(page, "fact-edit-1");
    await page.getByTestId("fact-answer-input").fill("Updated remote preference fact.");
    await click(page, "fact-save");
    await expectText(page, "Updated profile fact");
    await click(page, "fact-delete-1");
    await expectText(page, "Deleted profile fact");

    await click(page, "nav-runs");
    await click(page, "run-row-1");
    await expectText(page, "mock run detail");

    await click(page, "nav-reprocess");
    await click(page, "reprocess-job-2");
    await click(page, "reprocess-selected");
    await expectText(page, "Queued");

    await click(page, "nav-assist");
    await page.getByTestId("assist-file-input").setInputFiles({
      name: "project-summary.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("FastAPI backend project summary"),
    });
    await click(page, "assist-parse-files");
    await expectText(page, "Parsed 1 file");
    await click(page, "assist-launch-helper");
    await expectText(page, "Upload helper launched");

    await click(page, "nav-export");
    await click(page, "export-workbook");
    await expectText(page, "Exported XLSX");
    await expectVisible(page, '[data-testid="export-link-xlsx"]', "xlsx export link");
    await expectVisible(page, '[data-testid="export-link-json"]', "json export link");
    await expectVisible(page, '[data-testid="export-link-csv"]', "csv export link");

    await click(page, "nav-settings");
    await page.getByTestId("settings-preferred-locations").fill("Remote, hybrid, flexible location");
    await page.getByTestId("settings-scan-limit").fill("25");
    await click(page, "settings-save");
    await expectText(page, "Saved settings");

    await click(page, "nav-health");
    await click(page, "model-health-refresh");
    await expectText(page, "Model health refreshed");

    if (pageErrors.length || consoleMessages.length) {
      throw new Error(`Browser errors found:\n${[...pageErrors, ...consoleMessages].join("\n")}`);
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




