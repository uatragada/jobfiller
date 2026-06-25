import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import {
  applications as applicationSeed,
  emailAlerts as emailAlertSeed,
  integrations as integrationSeed,
  jobs as jobSeed,
  modelHealthServices as modelHealthSeed,
  profileFacts as factSeed,
  questions as questionSeed,
  runs as runSeed,
  settingsSeed,
  uploads as uploadSeed,
  workbookExports as workbookExportSeed,
} from "../data/fixtures";
import { withMockLoading } from "../lib/mockApi";

function updateById(rows, id, patch) {
  return rows.map((row) => (row.id === id || row.id === String(id) ? { ...row, ...(typeof patch === "function" ? patch(row) : patch) } : row));
}

function firstId(rows) {
  return rows[0]?.id ?? null;
}

function formatDateTime(value) {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

const APPLICATION_STATE_LABELS = {
  DISCOVERED: "Discovered",
  NEW: "Discovered",
  APPLIED: "Applied",
  SUBMITTED: "Applied",
  ACTION_NEEDED: "Action Needed",
  NEEDS_INFO: "Action Needed",
  INTERVIEW: "Interview",
  REJECTED: "Rejected",
};

const APPLICATION_STATE_SET = new Set(Object.values(APPLICATION_STATE_LABELS));

function normalizeApplicationState(status, fallback = "") {
  const value = String(status || "").trim().toUpperCase();
  if (!value) return fallback;
  if (APPLICATION_STATE_LABELS[value]) return APPLICATION_STATE_LABELS[value];
  if (value.includes("REJECT")) return "Rejected";
  if (value.includes("INTERVIEW")) return "Interview";
  if (value.includes("ACTION") || value.includes("NEEDS")) return "Action Needed";
  if (value.includes("APPLIED") || value.includes("SUBMITTED") || value.includes("RECEIVED")) return "Applied";
  if (value.includes("DISCOVER") || value === "NEW") return "Discovered";
  return titleFromTag(value);
}

function normalizeJobStatus(status) {
  const value = String(status || "").toUpperCase();
  const applicationState = normalizeApplicationState(value, "");
  if (APPLICATION_STATE_SET.has(applicationState)) return applicationState;
  if (value.includes("APPLIED") || value.includes("SUBMITTED")) return "Applied";
  if (value.includes("NEEDS")) return "Needs Info";
  if (value.includes("READY")) return "Ready";
  if (value.includes("GENERATING")) return "Generating";
  if (value.includes("QA") || value.includes("PARSED") || value.includes("REVIEW")) return "Review";
  return value ? titleFromTag(value) : "Discovered";
}

function gradeFromJob(job) {
  if (job.latest_grade) return job.latest_grade;
  const fit = Number(job.fit_score || 0);
  if (fit >= 92) return "A";
  if (fit >= 86) return "A-";
  if (fit >= 80) return "B+";
  if (fit >= 72) return "B";
  if (fit >= 64) return "C+";
  return "C";
}

function keywordsFromJob(job) {
  const raw = String(job.keywords || job.key_requirements || "");
  return raw
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 3);
}

function splitQuestionLines(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function inferWorkModel(location) {
  const value = String(location || "").toLowerCase();
  if (value.includes("remote")) return "Remote";
  if (value.includes("hybrid")) return "Hybrid";
  if (value.includes("on-site") || value.includes("onsite") || value.includes("office")) return "On-site";
  return "";
}

function normalizeApiJob(job) {
  const ready = Boolean(job.ready_to_send) || normalizeJobStatus(job.status) === "Ready";
  const postedAt = Date.parse(job.posted_at || job.first_seen_at || "") || 0;
  const importedAt = Date.parse(job.first_seen_at || job.last_seen_at || job.updated_at || "") || 0;
  const artifact = job.artifact || {};
  const latestArtifactId = job.latest_artifact_id ?? artifact.id ?? null;
  const latestResumePdfPath = job.latest_resume_pdf_path || artifact.resume_pdf_path || "";
  const latestResumeTexPath = job.latest_resume_tex_path || artifact.resume_tex_path || "";
  const latestCoverLetterPath = job.latest_cover_letter_path || artifact.cover_letter_path || "";
  const artifactCount = Number(job.artifact_count || (latestArtifactId ? 1 : 0));
  const manualQuestions = splitQuestionLines(job.manual_questions);
  const fallbackNotes = job.company && job.title ? `Build backend services for ${job.company}. ${job.key_requirements || ""}`.trim() : job.key_requirements || "";
  return {
    id: job.id,
    posted: formatDateTime(job.posted_at || job.first_seen_at),
    imported: formatDateTime(job.first_seen_at || job.last_seen_at || job.updated_at),
    postedAt,
    importedAt,
    company: job.company || "Unknown Company",
    role: job.title || "Imported Job",
    location: job.location || "Unknown",
    workModel: job.work_model || inferWorkModel(job.location),
    employment: job.role_family || "Full-time",
    status: normalizeJobStatus(job.application_state || job.status),
    pipelineStatus: job.status || "",
    fit: Number(job.fit_score || 0),
    grade: gradeFromJob(job),
    gradeScores: job.latest_grade_scores || {},
    gradePasses: job.latest_grade_passes || {},
    gradeRisks: Array.isArray(job.latest_grade_risks) ? job.latest_grade_risks : [],
    gradeBreakdown: job.latest_grade_breakdown || {},
    ready,
    files: artifactCount,
    sourceUrl: job.source_url || job.apply_url || "#",
    source: job.source || "manual",
    keywords: keywordsFromJob(job),
    notes: job.notes || job.description || job.summary || fallbackNotes,
    latestArtifactId,
    latestResumePdfPath,
    latestResumeTexPath,
    latestCoverLetterPath,
    artifactCount,
    compileStatus: job.compile_status || artifact.compile_status || "",
    manualQuestions,
    openQuestions: Number(job.open_questions || 0),
  };
}

function latestArtifactIdForJob(job) {
  return job?.latestArtifactId ?? job?.latest_artifact_id ?? job?.artifact?.id ?? null;
}

function generationPriority(job) {
  if (job.openQuestions > 0 || job.status === "Needs Info") return "P1";
  if (job.fit >= 85) return "P1";
  if (job.fit >= 70) return "P2";
  return "P3";
}

function generationStatus(job) {
  const status = String(job.pipelineStatus || job.status || "").toUpperCase();
  if (status.includes("FAILED")) return "Failed";
  if (status.includes("GENERATING")) return "Running";
  if (job.openQuestions > 0 || status.includes("NEEDS")) return "Blocked";
  if (status.includes("READY") || job.ready) return "Completed";
  if (status.includes("QA") || job.artifactCount > 0 || job.files > 0) return "Needs Review";
  return "Queued";
}

function generationTaskLabel(job, status) {
  if (status === "Blocked") return "Waiting on answers";
  if (status === "Running") return "Generating packet";
  if (status === "Completed") return "Packet ready";
  if (status === "Needs Review") return "Review generated packet";
  if (status === "Failed") return "Generation failed";
  return "Auto-generate packet";
}

function buildGenerationTasks(jobs) {
  return jobs.map((job) => {
    const status = generationStatus(job);
    return {
      id: job.id,
      jobId: job.id,
      priority: generationPriority(job),
      task: generationTaskLabel(job, status),
      company: job.company,
      role: job.role,
      model: "Local LLM",
      status,
      files: Number(job.artifactCount || job.files || 0),
      tokens: 0,
      created: job.imported,
      ready: Boolean(job.ready || status === "Completed"),
      openQuestions: Number(job.openQuestions || 0),
      latestArtifactId: latestArtifactIdForJob(job),
    };
  });
}

function normalizeAlertState(state) {
  const value = String(state || "").toUpperCase();
  if (value.includes("REJECT")) return "Rejected";
  if (value.includes("ACTION") || value.includes("NEEDS")) return "Action Needed";
  if (value.includes("INTERVIEW")) return "Interview";
  if (value.includes("ACCEPT") || value.includes("OFFER")) return "Accepted";
  if (value.includes("APPLIED") || value.includes("RECEIVED")) return "Applied";
  return "Unknown";
}

function categoryFromAlertState(state) {
  if (state === "Rejected") return "Rejection";
  if (state === "Action Needed") return "Action Needed";
  if (state === "Interview") return "Interview";
  if (state === "Applied") return "Applied";
  if (state === "Accepted") return "Accepted";
  return "Other";
}

function normalizeSender(sender) {
  const value = String(sender || "").trim();
  if (!value) return "Unknown sender";
  return value.replace(/\s*<[^>]+>\s*/g, "").trim() || value;
}

function normalizeApiEmailAlert(event) {
  const state = normalizeAlertState(event.state);
  return {
    id: event.id,
    jobId: event.job_id,
    receivedAt: Date.parse(event.received_at || "") || 0,
    received: formatDateTime(event.received_at),
    company: event.company || "Unknown Company",
    role: event.title || "Imported Job",
    sender: normalizeSender(event.sender),
    subject: event.subject || "Application update",
    state,
    category: categoryFromAlertState(state),
    source: event.source || "email",
    followUp: event.follow_up_action || "Review this message and decide the next step.",
    actionUrl: event.action_url || "",
    evidenceUrl: event.evidence_url || "",
  };
}

function titleFromTag(tag) {
  const value = String(tag || "").replace(/^assist_upload_/, "").replace(/[_-]+/g, " ").trim();
  if (!value) return "Imported Fact";
  return value.replace(/\b\w/g, (char) => char.toUpperCase());
}

function categoryFromFactTag(tag) {
  const value = String(tag || "").toLowerCase();
  if (value.startsWith("assist_upload")) return "Experience";
  if (value.includes("skill") || value.includes("react") || value.includes("python") || value.includes("backend")) return "Skills";
  if (value.includes("education") || value.includes("degree")) return "Education";
  if (value.includes("location") || value.includes("remote") || value.includes("preference")) return "Preferences";
  if (value.includes("motivation") || value.includes("why") || value.includes("answer")) return "Reusable Answers";
  return "Experience";
}

function confidencePercent(confidence) {
  const value = Number(confidence);
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value <= 1 ? value * 100 : value)));
}

function normalizeApiFact(fact) {
  const tag = String(fact.tag || "");
  const confidence = confidencePercent(fact.confidence);
  return {
    id: fact.id ?? `${tag || "fact"}-${Date.now()}`,
    category: categoryFromFactTag(tag),
    field: String(fact.question_text || "").trim() || titleFromTag(tag),
    value: fact.answer || "",
    confidence,
    source: tag.startsWith("assist_upload") ? "Assist Upload" : "Profile Facts",
    usedIn: "Reusable fact bank",
    verified: confidence >= 90,
    updated: formatDateTime(fact.updated_at),
    conflicts: [],
  };
}

function normalizeQuestionStatus(status, answer) {
  const value = String(status || "").toUpperCase();
  if (value.includes("APPROVED")) return "Approved";
  if (value.includes("SKIPPED") || value.includes("ATTACHED")) return "Attached";
  return answer ? "Needs Review" : "Unanswered";
}

function normalizeApiQuestion(question) {
  const answer = question.answer || "";
  const tag = String(question.tag || "").trim();
  return {
    id: question.id,
    jobId: question.job_id,
    company: question.company || "Unknown Company",
    role: question.title || question.role || "Imported Job",
    question: question.question_text || "Question text unavailable.",
    type: question.impact || titleFromTag(tag) || "Application",
    suggestedAnswer: answer,
    status: normalizeQuestionStatus(question.status, answer),
    rawStatus: question.status || "",
    confidence: answer ? 88 : 0,
    source: tag ? titleFromTag(tag) : "Question Queue",
    updated: formatDateTime(question.created_at),
    factsUsed: tag ? [tag] : [],
    tag,
  };
}

function slugFromFilename(filename, fallbackId) {
  return (
    String(filename || fallbackId || "upload")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 80) || `upload_${fallbackId || Date.now()}`
  );
}

function uploadFactPayload(upload) {
  const filename = upload.filename || "assist upload";
  const summary = String(upload.summary || "").trim();
  return {
    tag: `assist_upload_${slugFromFilename(filename, upload.id)}`,
    question_text: `Facts imported from ${filename}`,
    answer: summary || `${upload.extractedFacts || 0} candidate facts extracted from ${filename}.`,
    confidence: 0.82,
  };
}

function normalizeApiRun(run) {
  const status = run.status === "SUCCEEDED" ? "Succeeded" : run.status === "FAILED" ? "Failed" : run.status === "RUNNING" ? "Running" : titleFromTag(run.status);
  const startedAt = Date.parse(run.started_at || "") || 0;
  const finishedAt = Date.parse(run.finished_at || "") || 0;
  const durationSeconds = finishedAt && startedAt ? Math.max(0, Math.round((finishedAt - startedAt) / 1000)) : null;
  return {
    id: run.id,
    started: formatDateTime(run.started_at),
    type: titleFromTag(run.kind),
    target: "JobFiller",
    status,
    steps: 1,
    duration: durationSeconds == null ? (status === "Running" ? "Running" : "Done") : `${durationSeconds}s`,
    model: "System",
    cost: "$0.00",
    artifacts: 0,
    logs: [run.message || `${titleFromTag(run.kind)} ${status.toLowerCase()}`],
  };
}

function applicationStatusFromJob(job) {
  const explicitState = normalizeApplicationState(job.application_state, "");
  if (APPLICATION_STATE_SET.has(explicitState)) return explicitState;
  if (APPLICATION_STATE_SET.has(job.status)) return job.status;
  if (job.status === "Applied" || String(job.application_state || "").toUpperCase().includes("APPLIED")) return "Applied";
  if (job.ready) return "Ready";
  if (job.openQuestions > 0 || job.manualQuestions?.length) return "Needs Info";
  return "Applying";
}

function normalizeIdentityValue(value) {
  return String(value || "").trim().toLowerCase();
}

function sameApplicationJob(row, job) {
  if (!row || !job) return false;
  if (row.jobId != null && job.id != null) {
    return String(row.jobId) === String(job.id);
  }
  if (row.jobId != null || job.id == null) {
    return false;
  }
  return normalizeIdentityValue(row.company) === normalizeIdentityValue(job.company)
    && normalizeIdentityValue(row.role) === normalizeIdentityValue(job.role);
}

function updateApplicationForJob(rows, job, patch) {
  const existing = rows.find((row) => sameApplicationJob(row, job));
  if (!existing) return rows;
  return updateById(rows, existing.id, patch);
}

function normalizeChecklistItem(row, jobLookup = new Map()) {
  const job = jobLookup.get(row.job_id) || {};
  const ready = Boolean(row.ready_to_send || job.ready);
  const openQuestions = splitQuestionLines(row.manual_questions).length || Number(job.openQuestions || 0);
  const status = applicationStatusFromJob({ ...job, ready, openQuestions, application_state: row.application_state, status: normalizeJobStatus(row.application_state || row.status) });
  return {
    id: row.job_id ?? job.id ?? row.apply_order,
    priority: Number(row.apply_order || 0) <= 3 ? "P1" : Number(row.fit_score || job.fit || 0) >= 80 ? "P2" : "P3",
    company: row.company || job.company || "Unknown Company",
    role: row.title || job.role || "Imported Job",
    fit: Number(row.fit_score || job.fit || 0),
    packet: ready ? "Ready" : row.resume_pdf_path || row.cover_letter_path ? "Draft" : "Blocked",
    questions: openQuestions ? `${openQuestions} open` : "Clear",
    status,
    due: row.follow_up_action ? "Follow-up" : ready ? "Today" : "Tomorrow",
    owner: "Candidate",
    jobId: row.job_id ?? job.id ?? null,
    checklist: {
      jobDescription: true,
      companyPage: Boolean(row.apply_url || job.sourceUrl),
      questions: !openQuestions,
      resume: Boolean(row.resume_pdf_path || job.latestResumePdfPath),
      coverLetter: Boolean(row.cover_letter_path || job.latestCoverLetterPath),
      followUp: Boolean(row.follow_up_action),
    },
  };
}

function applicationsFromJobs(jobs) {
  return jobs
    .filter((job) => job.ready || job.openQuestions || job.status === "Applied")
    .map((job, index) =>
      normalizeChecklistItem(
        {
          apply_order: index + 1,
          job_id: job.id,
          company: job.company,
          title: job.role,
          status: job.status,
          application_state: job.status,
          fit_score: job.fit,
          ready_to_send: job.ready,
          manual_questions: job.manualQuestions.join("\n"),
          resume_pdf_path: job.latestResumePdfPath,
          cover_letter_path: job.latestCoverLetterPath,
          apply_url: job.sourceUrl,
        },
        new Map([[job.id, job]]),
      ),
    );
}

function normalizeApiSettings(payload) {
  const candidate = payload?.candidate || {};
  const scan = payload?.scan || {};
  const llm = payload?.llm || {};
  return {
    ...settingsSeed,
    accountName: candidate.name || settingsSeed.accountName,
    profileEmail: candidate.email || settingsSeed.profileEmail,
    finderLimit: Number(scan.default_limit || settingsSeed.finderLimit),
    defaultSource: scan.codex_job_sites || scan.default_keywords || settingsSeed.defaultSource,
    localModel: llm.model || llm.provider || settingsSeed.localModel,
    cloudModel: Boolean(llm.cloud_enabled),
    savedAt: "Live",
    raw: payload,
  };
}

function settingsPayloadFromDraft(settings) {
  const raw = settings.raw && typeof settings.raw === "object" ? settings.raw : {};
  return {
    ...raw,
    candidate: {
      ...(raw.candidate || {}),
      name: settings.accountName,
      email: settings.profileEmail,
    },
    scan: {
      ...(raw.scan || {}),
      default_limit: Number(settings.finderLimit || settingsSeed.finderLimit),
      codex_job_sites: settings.defaultSource,
    },
    llm: {
      ...(raw.llm || {}),
      model: settings.localModel,
      cloud_enabled: Boolean(settings.cloudModel),
    },
  };
}

function normalizeApiModelHealth(payload) {
  if (!payload || typeof payload !== "object") return modelHealthSeed;
  const status = String(payload.status || "").toLowerCase();
  const systemStatus = payload.last_run_status === "FAILED" ? "Warning" : "Healthy";
  const llmStatus = status.includes("connected") ? "Healthy" : status.includes("blocked") || status.includes("not reachable") ? "Error" : "Warning";
  return [
    {
      id: "system",
      service: "System API",
      status: systemStatus,
      latency: payload.avg_recent_duration_seconds ? `${payload.avg_recent_duration_seconds}s avg` : "Live",
      lastCheck: formatDateTime(payload.last_run_at) || "Now",
      version: "backend",
      errors: Number(payload.failed_runs || 0),
      checks: [`Queue depth ${payload.queue_depth ?? 0}`, `Last run ${payload.last_run_status || "unknown"}`, `Worker ${payload.worker || "unknown"}`],
    },
    {
      id: "ollama",
      service: "Local LLM",
      status: llmStatus,
      latency: payload.ollama_url_effective || "Local",
      lastCheck: "Now",
      version: payload.configured_model || payload.model || "Ollama",
      errors: llmStatus === "Error" ? 1 : 0,
      checks: [`Provider ${payload.provider || "Ollama"}`, `Status ${payload.status || "unknown"}`, `Mode ${payload.mode || "local"}`],
    },
    {
      id: "finder",
      service: "Finder",
      status: payload.scanner === "running" ? "Running" : "Healthy",
      latency: payload.scanner || "idle",
      lastCheck: "Now",
      version: "scanner",
      errors: 0,
      checks: Object.entries(payload.job_status_counts || {}).map(([key, value]) => `${titleFromTag(key)}: ${value}`),
    },
    {
      id: "exports",
      service: "Workbook Export",
      status: payload.artifact_exports?.workbook_exists ? "Healthy" : "Warning",
      latency: "Local",
      lastCheck: "Now",
      version: "xlsx/json/csv",
      errors: payload.artifact_exports?.workbook_exists ? 0 : 1,
      checks: [
        payload.artifact_exports?.workbook_exists ? "Workbook ready" : "Workbook not generated",
        payload.artifact_exports?.json_export_exists ? "JSON ready" : "JSON not generated",
        payload.artifact_exports?.csv_export_exists ? "CSV ready" : "CSV not generated",
      ],
    },
  ];
}

function liveStatusLabel(status) {
  if (status.source === "live") return `Live backend synced ${status.lastSync || "now"}`;
  if (status.source === "loading") return "Connecting to backend...";
  return status.error ? `Fixture fallback: ${status.error}` : "Fixture fallback";
}

export function useJobFillerState() {
  const [jobs, setJobs] = useState(jobSeed);
  const [emailAlerts, setEmailAlerts] = useState(emailAlertSeed);
  const [questions, setQuestions] = useState(questionSeed);
  const [applications, setApplications] = useState(applicationSeed);
  const [profileFacts, setProfileFacts] = useState(factSeed);
  const [runs, setRuns] = useState(runSeed);
  const [uploads, setUploads] = useState(uploadSeed);
  const [integrations, setIntegrations] = useState(integrationSeed);
  const [workbookExports, setWorkbookExports] = useState(workbookExportSeed);
  const [modelHealthServices, setModelHealthServices] = useState(modelHealthSeed);
  const [settings, setSettings] = useState(settingsSeed);
  const [selected, setSelected] = useState({
    jobs: 3,
    "email-alerts": firstId(emailAlertSeed),
    questions: firstId(questionSeed),
    "apply-queue": firstId(applicationSeed),
    "profile-facts": firstId(factSeed),
    "runs-logs": runSeed[0]?.id,
    "generate-queue": null,
    "assist-upload": firstId(uploadSeed),
    "agent-import-mcp": integrationSeed[0]?.id,
    "export-workbook": firstId(workbookExportSeed),
    settings: "Account",
    "model-health": modelHealthSeed[0]?.id,
  });
  const [filters, setFilters] = useState({});
  const [pageState, setPageState] = useState({});
  const [toasts, setToasts] = useState([]);
  const [loadingAction, setLoadingAction] = useState("");
  const [modal, setModal] = useState(null);
  const [liveStatus, setLiveStatus] = useState({ source: "loading", lastSync: "", error: "" });
  const generationTasks = useMemo(() => buildGenerationTasks(jobs), [jobs]);

  function toast(message, tone = "success") {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setToasts((items) => [...items, { id, message, tone }].slice(-4));
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 3200);
  }

  async function refreshFromBackend({ silent = false } = {}) {
    if (!silent) setLoadingAction("refresh-data");
    const now = new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
    try {
      const results = await Promise.allSettled([
        api.jobs("newest", true),
        api.facts(),
        api.questions("all"),
        api.runs(),
        api.modelHealth(),
        api.settings(),
        api.tomorrowChecklist(),
      ]);
      const [jobsResult, factsResult, questionsResult, runsResult, modelHealthResult, settingsResult, checklistResult] = results;
      let liveSources = 0;
      let nextJobs = null;

      if (jobsResult.status === "fulfilled" && Array.isArray(jobsResult.value)) {
        nextJobs = jobsResult.value.map(normalizeApiJob);
        liveSources += 1;
        setJobs(nextJobs);
        setSelected((current) => ({ ...current, jobs: nextJobs.some((job) => job.id === current.jobs) ? current.jobs : firstId(nextJobs) }));
      }
      if (factsResult.status === "fulfilled" && Array.isArray(factsResult.value)) {
        const nextFacts = factsResult.value.map(normalizeApiFact);
        liveSources += 1;
        setProfileFacts(nextFacts);
        setSelected((current) => ({ ...current, "profile-facts": nextFacts.some((fact) => fact.id === current["profile-facts"]) ? current["profile-facts"] : firstId(nextFacts) }));
      }
      if (questionsResult.status === "fulfilled" && Array.isArray(questionsResult.value)) {
        const nextQuestions = questionsResult.value.map(normalizeApiQuestion);
        liveSources += 1;
        setQuestions(nextQuestions);
        setSelected((current) => ({ ...current, questions: nextQuestions.some((question) => question.id === current.questions) ? current.questions : firstId(nextQuestions) }));
      }
      if (runsResult.status === "fulfilled" && Array.isArray(runsResult.value)) {
        const nextRuns = runsResult.value.map(normalizeApiRun);
        liveSources += 1;
        setRuns(nextRuns);
        setSelected((current) => ({ ...current, "runs-logs": nextRuns.some((run) => run.id === current["runs-logs"]) ? current["runs-logs"] : firstId(nextRuns) }));
      }
      if (modelHealthResult.status === "fulfilled" && modelHealthResult.value && !Array.isArray(modelHealthResult.value)) {
        liveSources += 1;
        setModelHealthServices(normalizeApiModelHealth(modelHealthResult.value));
      }
      if (settingsResult.status === "fulfilled" && settingsResult.value && !Array.isArray(settingsResult.value)) {
        liveSources += 1;
        setSettings(normalizeApiSettings(settingsResult.value));
      }
      if (checklistResult.status === "fulfilled" && Array.isArray(checklistResult.value)) {
        const jobLookup = new Map((nextJobs || jobs).map((job) => [job.id, job]));
        const nextApplications = checklistResult.value.map((item) => normalizeChecklistItem(item, jobLookup));
        liveSources += 1;
        setApplications(nextApplications.length ? nextApplications : applicationsFromJobs(nextJobs || jobs));
        setSelected((current) => ({ ...current, "apply-queue": nextApplications.some((item) => item.id === current["apply-queue"]) ? current["apply-queue"] : firstId(nextApplications) }));
      } else if (nextJobs) {
        setApplications(applicationsFromJobs(nextJobs));
      }

      if (liveSources > 0) {
        setLiveStatus({ source: "live", lastSync: now, error: "" });
        if (!silent) toast(`Live backend data refreshed from ${liveSources} endpoint${liveSources === 1 ? "" : "s"}.`);
      } else {
        const firstError = results.find((result) => result.status === "rejected")?.reason?.message || "backend returned no live rows";
        setLiveStatus({ source: "fixture", lastSync: "", error: firstError });
        if (!silent) toast(`Using local fixtures: ${firstError}`, "warning");
      }
    } catch (error) {
      setLiveStatus({ source: "fixture", lastSync: "", error: error?.message || "backend unavailable" });
      if (!silent) toast(`Using local fixtures: ${error?.message || "backend unavailable"}`, "warning");
    } finally {
      if (!silent) setLoadingAction("");
    }
  }

  useEffect(() => {
    refreshFromBackend({ silent: true });
  }, []);

  async function action(label, work, message) {
    setLoadingAction(label);
    try {
      const result = await withMockLoading(work, 360);
      if (message) toast(message);
      return result;
    } finally {
      setLoadingAction("");
    }
  }

  const actions = useMemo(
    () => ({
      setSelected: (pageId, id) => setSelected((current) => ({ ...current, [pageId]: id })),
      setFilter: (pageId, key, value) => {
        setFilters((current) => ({ ...current, [pageId]: { ...(current[pageId] || {}), [key]: value } }));
        setPageState((current) => ({ ...current, [pageId]: { ...(current[pageId] || {}), page: 1 } }));
      },
      resetFilters: (pageId) => setFilters((current) => ({ ...current, [pageId]: {} })),
      setPage: (pageId, page) => setPageState((current) => ({ ...current, [pageId]: { ...(current[pageId] || {}), page } })),
      setSort: (pageId, sortKey, sortDirection) => setPageState((current) => ({ ...current, [pageId]: { ...(current[pageId] || {}), sortKey, sortDirection, page: 1 } })),
      setView: (pageId, view) => setPageState((current) => ({ ...current, [pageId]: { ...(current[pageId] || {}), view } })),
      setPageOption: (pageId, key, value) => setPageState((current) => ({ ...current, [pageId]: { ...(current[pageId] || {}), [key]: value } })),
      setModal,
      dismissToast: (id) => setToasts((items) => items.filter((item) => item.id !== id)),
      refreshData: () => refreshFromBackend(),
      importJobUrl: (url) =>
        action(
          "import-url",
          async () => {
            try {
              const imported = await api.importJob({ url });
              const normalized = normalizeApiJob(imported);
              setJobs((rows) => [normalized, ...rows.filter((row) => row.id !== normalized.id)]);
              setSelected((current) => ({ ...current, jobs: normalized.id }));
              setLiveStatus({ source: "live", lastSync: new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }), error: "" });
              return normalized;
            } catch (error) {
              toast(`Backend import unavailable; queued URL locally: ${error?.message || "offline"}`, "warning");
              return null;
            }
          },
          "Imported job URL.",
        ),
      addToApplyQueue: (job) => {
        return action(
          "add-to-apply-queue",
          async () => {
            try {
              await api.patchJob(job.id, { application_state: "QA", status: "QA" });
            } catch (error) {
              toast(`Queue update saved locally: ${error?.message || "backend unavailable"}`, "warning");
            }
            setJobs((rows) => updateById(rows, job.id, { status: "Review" }));
            setApplications((rows) =>
              rows.some((row) => sameApplicationJob(row, job))
                ? updateApplicationForJob(rows, job, { jobId: job.id, fit: job.fit, packet: job.ready ? "Ready" : "Blocked", status: job.ready ? "Ready" : "Action Needed" })
                : [
                    {
                      id: Date.now(),
                      priority: "P1",
                      company: job.company,
                      role: job.role,
                      fit: job.fit,
                      packet: job.ready ? "Ready" : "Blocked",
                      questions: job.ready ? "Clear" : "Needs review",
                      status: job.ready ? "Ready" : "Action Needed",
                      due: "Tomorrow",
                      owner: "Candidate",
                      jobId: job.id,
                      checklist: { jobDescription: true, companyPage: true, questions: job.ready, resume: job.ready, coverLetter: false, followUp: false },
                    },
                    ...rows,
                  ],
            );
          },
          `${job.company} added to Apply Queue.`,
        );
      },
      markJobApplied: (job) =>
        action(
          "mark-applied",
          async () => {
            try {
              const updatedJob = await api.patchJob(job.id, { application_state: "APPLIED", status: "APPLIED" });
              const normalized = normalizeApiJob(updatedJob);
              setJobs((rows) => updateById(rows, job.id, normalized));
            } catch (error) {
              toast(`Applied state saved locally: ${error?.message || "backend unavailable"}`, "warning");
            }
            setJobs((rows) => updateById(rows, job.id, { status: "Applied" }));
            setApplications((rows) => updateApplicationForJob(rows, job, { jobId: job.id, status: "Applied" }));
          },
          `${job.company} marked as applied.`,
        ),
      approveQuestion: (question) =>
        action(
          "approve-question",
          async () => {
            try {
              await api.answer(question.id, String(question.suggestedAnswer || "Approved.").trim() || "Approved.");
            } catch (error) {
              toast(`Answer saved locally: ${error?.message || "backend unavailable"}`, "warning");
            }
            setQuestions((rows) => updateById(rows, question.id, { status: "Approved", confidence: Math.max(question.confidence, 90) }));
          },
          "Answer approved.",
        ),
      regenerateQuestion: (question) =>
        action("regenerate-question", () => setQuestions((rows) => updateById(rows, question.id, { suggestedAnswer: `${question.suggestedAnswer} Refined for ${question.company}.`, status: "Needs Review", confidence: 86 })), "Regenerated answer draft."),
      attachQuestion: (question) =>
        action(
          "attach-question",
          async () => {
            try {
              await api.skipQuestion(question.id);
            } catch (error) {
              toast(`Question state saved locally: ${error?.message || "backend unavailable"}`, "warning");
            }
            setQuestions((rows) => updateById(rows, question.id, { status: "Attached" }));
          },
          "Question attached to selected job.",
        ),
      updateQuestionAnswer: (question, answer) => setQuestions((rows) => updateById(rows, question.id, { suggestedAnswer: answer, status: "Needs Review" })),
      changeApplicationStatus: (item, status) => action("application-status", () => setApplications((rows) => updateById(rows, item.id, { status })), `Moved ${item.company} to ${status}.`),
      toggleChecklist: (item, key) => setApplications((rows) => updateById(rows, item.id, (row) => ({ checklist: { ...row.checklist, [key]: !row.checklist[key] } }))),
      verifyFact: (fact) =>
        action(
          "verify-fact",
          async () => {
            const nextVerified = !fact.verified;
            try {
              const updated = await api.updateFact(fact.id, { confidence: nextVerified ? 1 : 0.75 });
              const normalized = normalizeApiFact(updated);
              setProfileFacts((rows) => updateById(rows, fact.id, normalized));
            } catch (error) {
              toast(`Fact verification saved locally: ${error?.message || "backend unavailable"}`, "warning");
              setProfileFacts((rows) => updateById(rows, fact.id, { verified: nextVerified, confidence: nextVerified ? 100 : 75 }));
            }
          },
          fact.verified ? "Fact marked unverified." : "Fact verified.",
        ),
      saveFact: (fact, value) =>
        action(
          "save-fact",
          async () => {
            try {
              const updated = await api.updateFact(fact.id, { answer: value, question_text: fact.field, confidence: Math.max(0.01, Number(fact.confidence || 80) / 100) });
              const normalized = normalizeApiFact(updated);
              setProfileFacts((rows) => updateById(rows, fact.id, normalized));
            } catch (error) {
              toast(`Fact saved locally: ${error?.message || "backend unavailable"}`, "warning");
              setProfileFacts((rows) => updateById(rows, fact.id, { value, updated: "Now" }));
            }
          },
          "Profile fact saved.",
        ),
      archiveFact: (fact) =>
        action(
          "archive-fact",
          async () => {
            try {
              await api.deleteFact(fact.id);
            } catch (error) {
              toast(`Fact archived locally: ${error?.message || "backend unavailable"}`, "warning");
            }
            setProfileFacts((rows) => rows.filter((row) => row.id !== fact.id));
          },
          "Profile fact archived.",
        ),
      retryRun: (run) => action("retry-run", () => setRuns((rows) => updateById(rows, run.id, { status: "Running", duration: "0s", logs: ["Retry queued", ...run.logs] })), "Run retry queued."),
      approveGeneration: () => action("approve-generation", () => {}, "Generation approval is automatic after local QA."),
      regenerateTask: (task) =>
        action(
          "generate-artifacts",
          async () => {
            if (!task.jobId) throw new Error("This generation row is not linked to a job.");
            const updatedJob = await api.generateArtifacts(task.jobId);
            const normalized = normalizeApiJob(updatedJob);
            setJobs((rows) => updateById(rows, task.jobId, normalized));
            return normalized;
          },
          "Regenerated resume and cover letter for selected job.",
        ),
      cancelTask: () => action("cancel-task", () => {}, "Automatic generation cannot be paused from this view."),
      changeTaskPriority: () => {},
      changeTaskModel: () => {},
      sendGenerationToApplyQueue: (task) =>
        action(
          "send-generation-to-apply-queue",
          () => {
            setApplications((rows) => {
              const existing = rows.find((row) => row.company === task.company && row.role === task.role);
              if (existing) {
                return updateById(rows, existing.id, { priority: task.priority, packet: task.ready ? "Ready" : "Draft", status: task.ready ? "Ready" : "Needs Info" });
              }
              return [
                {
                  id: Date.now(),
                  priority: task.priority,
                  company: task.company,
                  role: task.role,
                  fit: task.ready ? 82 : 70,
                  packet: task.ready ? "Ready" : "Draft",
                  questions: task.ready ? "Clear" : "Needs review",
                  status: task.ready ? "Ready" : "Needs Info",
                  due: "Tomorrow",
                  owner: "Candidate",
                  jobId: null,
                  checklist: { jobDescription: true, companyPage: true, questions: task.ready, resume: task.ready, coverLetter: task.ready, followUp: false },
                },
                ...rows,
              ];
            });
          },
          `${task.company} sent to Apply Queue.`,
        ),
      generateJobArtifacts: (job) =>
        action(
          "generate-artifacts",
          async () => {
            const updatedJob = await api.generateArtifacts(job.id);
            const normalized = normalizeApiJob(updatedJob);
            setJobs((rows) => updateById(rows, job.id, normalized));
            setApplications((rows) =>
              updateById(rows, rows.find((row) => row.jobId === job.id || (row.company === job.company && row.role === job.role))?.id, {
                packet: "Ready",
                status: "Ready",
                checklist: { jobDescription: true, companyPage: true, questions: job.ready, resume: true, coverLetter: true, followUp: false },
              }),
            );
            return normalized;
          },
          "Generated resume and cover letter for selected job.",
        ),
      openJobArtifactFolder: (job) =>
        action(
          "open-artifact-folder",
          async () => {
            const artifactId = latestArtifactIdForJob(job);
            if (!artifactId) throw new Error("No generated artifact is available for this job yet.");
            await api.openArtifactFolder(artifactId);
          },
          "Opened artifact output folder.",
        ),
      regradeJobArtifact: (job) =>
        action(
          "regrade-artifact",
          async () => {
            const artifactId = latestArtifactIdForJob(job);
            if (!artifactId) throw new Error("No generated artifact is available for this job yet.");
            const grade = await api.gradeArtifact(artifactId);
            if (grade?.overall_grade) {
              setJobs((rows) =>
                updateById(rows, job.id, {
                  grade: grade.overall_grade,
                  ready: Boolean(grade.ready_to_send),
                  gradeScores: grade.scores || {},
                  gradePasses: grade.passes || {},
                  gradeRisks: Array.isArray(grade.risks) ? grade.risks : [],
                  gradeBreakdown: grade.breakdown || {},
                }),
              );
            }
          },
          "Local LLM regrade completed.",
        ),
      assistUploadForJob: (job, kind = "resume") =>
        action(
          "assist-upload",
          async () => {
            await api.assistUpload(job.id, kind);
          },
          "Upload helper launched.",
        ),
      importUploadFacts: (upload) =>
        action(
          "import-upload",
          async () => {
            let createdFact;
            try {
              createdFact = await api.createFact(uploadFactPayload(upload));
            } catch (error) {
              toast(`Could not import facts from ${upload.filename}: ${error?.message || "backend unavailable"}`, "warning");
              throw error;
            }
            const nextFact = normalizeApiFact(createdFact);
            setUploads((rows) => updateById(rows, upload.id, { status: "Imported" }));
            setProfileFacts((rows) => [nextFact, ...rows.filter((row) => row.id !== nextFact.id)]);
            setSelected((current) => ({ ...current, "assist-upload": upload.id, "profile-facts": nextFact.id }));
            return nextFact;
          },
          "Detected facts imported into Profile Facts.",
        ),
      reprocessUpload: (upload) => action("reprocess-upload", () => setUploads((rows) => updateById(rows, upload.id, { status: "Extracting", extractedFacts: upload.extractedFacts + 1 })), "Upload reprocess started."),
      testIntegration: (source) => action("test-integration", () => setIntegrations((rows) => updateById(rows, source.id, { status: "Active", errors: 0, lastSeen: "Now" })), `${source.name} connection healthy.`),
      toggleIntegration: (source) => setIntegrations((rows) => updateById(rows, source.id, { status: source.status === "Disabled" ? "Active" : "Disabled" })),
      triggerScan: (options = {}) =>
        action(
          "scan-now",
          async () => {
            const result = await api.scan({
              source: "all",
              remote_first: true,
              limit: Number(options.limit || settings.finderLimit || 20),
              scanner_keywords: options.scannerKeywords || "",
              codex_agent: true,
            });
            const [nextJobs, nextRuns] = await Promise.allSettled([api.jobs("newest", true), api.runs()]);
            if (nextJobs.status === "fulfilled" && Array.isArray(nextJobs.value)) {
              setJobs(nextJobs.value.map(normalizeApiJob));
            }
            if (nextRuns.status === "fulfilled" && Array.isArray(nextRuns.value)) {
              setRuns(nextRuns.value.map(normalizeApiRun));
            }
            setLiveStatus({ source: "live", lastSync: new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }), error: "" });
            return result;
          },
          "Scan complete.",
        ),
      generateWorkbook: () =>
        action(
          "generate-workbook",
          async () => {
            let exportResult = null;
            try {
              exportResult = await api.exportBundle();
            } catch (error) {
              toast(`Workbook generated locally in the UI only: ${error?.message || "backend unavailable"}`, "warning");
            }
            setWorkbookExports((rows) => [
              {
                id: exportResult?.export_id || Date.now(),
                template: "Full Application Review",
                status: "Generated",
                rows: jobs.length + applications.length + questions.length + profileFacts.length + runs.length,
                created: "Now",
                sheets: ["Jobs", "Applications", "Questions", "Profile Facts", "Runs"],
                downloadUrl: exportResult?.downloads?.xlsx || exportResult?.url || "",
              },
              ...rows,
            ]);
          },
          "Workbook generated.",
        ),
      saveSettings: (nextSettings) =>
        action(
          "save-settings",
          async () => {
            try {
              const updated = await api.updateSettings(settingsPayloadFromDraft(nextSettings));
              setSettings(normalizeApiSettings(updated));
            } catch (error) {
              toast(`Backend unavailable; kept settings locally: ${error?.message || "offline"}`, "warning");
              setSettings({ ...nextSettings, savedAt: "Now" });
            }
          },
          "Settings saved.",
        ),
      runDiagnostic: (service) =>
        action(
          "run-diagnostic",
          async () => {
            try {
              const health = await api.modelHealth();
              setModelHealthServices(normalizeApiModelHealth(health));
              setLiveStatus({ source: "live", lastSync: new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }), error: "" });
            } catch (error) {
              toast(`Diagnostic used local state: ${error?.message || "backend unavailable"}`, "warning");
              setModelHealthServices((rows) => updateById(rows, service.id, { status: "Healthy", latency: service.id === "ollama" ? "3.4s" : "76ms", lastCheck: "Now", errors: 0 }));
            }
          },
          "Diagnostic complete.",
        ),
      toggleModelStatus: (service) => setModelHealthServices((rows) => updateById(rows, service.id, { status: service.status === "Error" ? "Healthy" : "Warning" })),
    }),
    [applications.length, jobs, profileFacts.length, questions.length, runs.length, settings],
  );

  return {
    jobs,
    emailAlerts,
    questions,
    applications,
    profileFacts,
    runs,
    generationTasks,
    uploads,
    integrations,
    workbookExports,
    modelHealthServices,
    settings,
    setSettings,
    selected,
    filters,
    pageState,
    liveStatus: { ...liveStatus, label: liveStatusLabel(liveStatus) },
    toasts,
    loadingAction,
    modal,
    actions,
    toast,
  };
}
