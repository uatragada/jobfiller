import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  CalendarCheck2,
  ArrowDown,
  ArrowUpDown,
  Briefcase,
  ChevronDown,
  Database,
  Download,
  ExternalLink,
  FileCode2,
  FileText,
  FolderOpen,
  HelpCircle,
  Link2,
  Loader2,
  MapPin,
  Pencil,
  Play,
  Plus,
  RefreshCcw,
  Save,
  Search,
  Settings,
  SkipForward,
  SlidersHorizontal,
  Trash2,
  Upload,
  UserRound,
  X,
} from "lucide-react";
import { api } from "./api";
import "./styles.css";

const LOCATION_GROUPS = [
  { title: "Remote First", items: ["Remote", "Hybrid", "Timezone-Aligned Remote", "Remote Global", "Open to Relocation"] },
  { title: "Work Model", items: ["Onsite", "Hybrid", "Remote", "Open to Relocation"] },
  { title: "Regions", items: ["Candidate Region", "Candidate Country", "Nearby Hybrid", "Global"] },
  { title: "Custom", items: ["My City", "My Region", "No Location Preference"] },
];

function slugLocationTestId(value) {
  return String(value).toLowerCase().replace(/\s+/g, "-");
}

const LOCATION_CHIP_FIRST_GROUP = LOCATION_GROUPS.reduce((firstGroup, group) => {
  for (const item of group.items) {
    if (!firstGroup.has(item)) firstGroup.set(item, group.title);
  }
  return firstGroup;
}, new Map());

function locationChipTestId(groupTitle, item) {
  const base = `location-chip-${slugLocationTestId(item)}`;
  return LOCATION_CHIP_FIRST_GROUP.get(item) === groupTitle ? base : `${base}-${slugLocationTestId(groupTitle)}`;
}

const LOGO_PALETTE = [
  ["#1d4ed8", "#ffffff"],
  ["#047857", "#ffffff"],
  ["#7c2d12", "#ffffff"],
  ["#4338ca", "#ffffff"],
  ["#0f766e", "#ffffff"],
  ["#334155", "#ffffff"],
  ["#be123c", "#ffffff"],
  ["#854d0e", "#ffffff"],
];

const DEFAULT_SETTINGS = {
  remoteFirst: true,
  preferredLocations: "Remote, hybrid, flexible location",
  scannerKeywords: "entry level, associate, junior, new grad, remote, hybrid",
  ollamaModel: "",
  ollamaUrl: "http://127.0.0.1:11434",
  candidateName: "",
  candidateEmail: "",
  candidateLocation: "",
  candidateSummary: "",
  candidateProfileJson: "",
  scanSource: "all",
  scanLimit: 20,
};

function safeJsonParse(value, fallback) {
  try {
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

function settingsFromServer(payload) {
  const candidate = payload?.candidate || {};
  const scan = payload?.scan || {};
  const llm = payload?.llm || {};
  return {
    ...DEFAULT_SETTINGS,
    remoteFirst: scan.remote_first ?? DEFAULT_SETTINGS.remoteFirst,
    preferredLocations: scan.preferred_locations || DEFAULT_SETTINGS.preferredLocations,
    scannerKeywords: scan.default_keywords || DEFAULT_SETTINGS.scannerKeywords,
    scanLimit: scan.default_limit || DEFAULT_SETTINGS.scanLimit,
    ollamaModel: llm.model || "",
    ollamaUrl: llm.ollama_url || DEFAULT_SETTINGS.ollamaUrl,
    candidateName: candidate.name || "",
    candidateEmail: candidate.email || "",
    candidateLocation: candidate.location || "",
    candidateSummary: candidate.summary || "",
    candidateProfileJson: JSON.stringify(candidate, null, 2),
  };
}

function parseCandidateProfileJson(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) return { ok: true, value: {} };
  try {
    const parsed = JSON.parse(trimmed);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      return { ok: false, error: "Candidate profile JSON must be an object." };
    }
    return { ok: true, value: parsed };
  } catch (error) {
    return { ok: false, error: `Candidate profile JSON is invalid: ${error.message}` };
  }
}

function settingsToServer(settings, parsedCandidate = null) {
  const candidate = parsedCandidate || parseCandidateProfileJson(settings.candidateProfileJson).value || {};
  return {
    candidate: {
      ...candidate,
      name: settings.candidateName || candidate.name || "",
      email: settings.candidateEmail || candidate.email || "",
      location: settings.candidateLocation || candidate.location || "",
      summary: settings.candidateSummary || candidate.summary || "",
    },
    scan: {
      remote_first: Boolean(settings.remoteFirst),
      preferred_locations: settings.preferredLocations,
      default_keywords: settings.scannerKeywords,
      default_limit: Number(settings.scanLimit || 20),
    },
    llm: {
      provider: "ollama",
      model: settings.ollamaModel || "",
      ollama_url: settings.ollamaUrl || DEFAULT_SETTINGS.ollamaUrl,
    },
  };
}

function statusClass(status) {
  return `status ${String(status || "").toLowerCase().replace(/_/g, "-")}`;
}

function gradeClass(grade) {
  return `gradeBadge ${String(grade || "-").toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

function logoFor(company) {
  const words = String(company || "?").match(/[A-Za-z0-9]+/g) || ["?"];
  const label = words.slice(0, 2).map((word) => word[0]).join("").toUpperCase();
  const hash = String(company || "").split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const [bg, fg] = LOGO_PALETTE[hash % LOGO_PALETTE.length];
  return { label, style: { "--logo-bg": bg, "--logo-fg": fg } };
}

function fmtDate(value) {
  if (!value) return "unknown";
  return new Date(value).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function timeAgo(value) {
  if (!value) return "recently";
  const diff = Date.now() - new Date(value).getTime();
  const hours = Math.max(1, Math.round(diff / 36e5));
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function readiness(job) {
  if (job.readiness_score != null) return job.readiness_score;
  if (job.status === "READY") return 88;
  if (job.status === "NEEDS_INFO") return 55;
  return null;
}

function isValidImportUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol);
  } catch {
    return false;
  }
}

function safeExternalUrl(value) {
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol)) return "";
    if (url.username || url.password) return "";
    const host = url.hostname.toLowerCase();
    if (host === "localhost" || host === "127.0.0.1" || host === "::1" || host.endsWith(".localhost")) return "";
    return url.href;
  } catch {
    return "";
  }
}

function sortQuestionsByImpact(rows, sort = "impact") {
  const copy = [...rows];
  if (sort === "impact-low") {
    copy.sort((a, b) => (a.impact_score || 0) - (b.impact_score || 0) || new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  } else if (sort === "recent") {
    copy.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  } else if (sort === "oldest") {
    copy.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  } else {
    copy.sort((a, b) => (b.impact_score || 0) - (a.impact_score || 0) || new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }
  return copy;
}

function scoreGrade(job) {
  return job.latest_grade || (job.status === "READY" ? "A" : job.status === "NEEDS_INFO" ? "B+" : "-");
}

function remoteRank(job) {
  const text = `${job.location} ${job.work_model}`.toLowerCase();
  if (text.includes("remote")) return 2;
  if (text.includes("hybrid")) return 1;
  return 0;
}

function filterJobs(jobs, filters) {
  return jobs.filter((job) => {
    const haystack = [
      job.company,
      job.title,
      job.location,
      job.work_model,
      job.status,
      job.key_requirements,
      job.keywords,
      job.source,
    ].join(" ").toLowerCase();
    if (filters.search && !haystack.includes(filters.search.toLowerCase())) return false;
    if (filters.status !== "all" && job.status !== filters.status) return false;
    if (filters.source !== "all" && job.source !== filters.source) return false;
    if (filters.workModel !== "all" && !String(job.work_model).toLowerCase().includes(filters.workModel.toLowerCase())) return false;
    if (filters.locations.length) {
      const locationText = `${job.location} ${job.work_model}`.toLowerCase();
      const matched = filters.locations.some((location) => {
        const value = location.toLowerCase();
        if (["remote", "timezone-aligned remote", "remote global"].includes(value)) return locationText.includes("remote");
        if (value === "hybrid") return locationText.includes("hybrid");
        if (value === "onsite") return !locationText.includes("remote") && !locationText.includes("hybrid");
        if (["candidate region", "candidate country", "nearby hybrid"].includes(value)) return locationText.includes("hybrid") || locationText.includes("remote");
        if (value === "global") return locationText.includes("global") || locationText.includes("remote global");
        return locationText.includes(value) || locationText.includes(value.replace("new ", ""));
      });
      if (!matched && !filters.customLocation) return false;
    }
    if (filters.customLocation && !`${job.location} ${job.work_model}`.toLowerCase().includes(filters.customLocation.toLowerCase())) return false;
    if (filters.remoteOnly && !`${job.location} ${job.work_model}`.toLowerCase().includes("remote")) return false;
    return true;
  });
}

function sortJobs(jobs, sort, settings) {
  const rows = [...jobs];
  const gradeValue = (grade) => ({ "A+": 5.3, A: 5, "A-": 4.7, "B+": 4.3, B: 4, "B-": 3.7, C: 3, D: 2, F: 1, "-": 0 }[grade || "-"] || 0);
  rows.sort((a, b) => {
    const remoteBias = settings.remoteFirst ? remoteRank(b) - remoteRank(a) : 0;
    if (remoteBias) return remoteBias;
    if (sort === "oldest") return (new Date(a.posted_at || 0).getTime()) - (new Date(b.posted_at || 0).getTime());
    if (sort === "fit") return b.fit_score - a.fit_score;
    if (sort === "fit-low") return a.fit_score - b.fit_score;
    if (sort === "grade") return gradeValue(scoreGrade(b)) - gradeValue(scoreGrade(a));
    if (sort === "grade-low") return gradeValue(scoreGrade(a)) - gradeValue(scoreGrade(b));
    if (sort === "ready") return (readiness(b) || 0) - (readiness(a) || 0);
    if (sort === "recently-updated") return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    if (sort === "needs-info") return Number(b.status === "NEEDS_INFO") - Number(a.status === "NEEDS_INFO");
    if (sort === "company") return a.company.localeCompare(b.company);
    if (sort === "status") return a.status.localeCompare(b.status);
    const aTime = a.posted_at ? new Date(a.posted_at).getTime() : 0;
    const bTime = b.posted_at ? new Date(b.posted_at).getTime() : 0;
    return bTime - aTime || new Date(b.first_seen_at).getTime() - new Date(a.first_seen_at).getTime() || b.fit_score - a.fit_score;
  });
  return rows;
}

function App() {
  const [jobs, setJobs] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [facts, setFacts] = useState([]);
  const [runs, setRuns] = useState([]);
  const [modelHealth, setModelHealth] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [detail, setDetail] = useState(null);
  const [detailOpen, setDetailOpen] = useState(true);
  const [page, setPage] = useState("jobs");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tomorrowChecklist, setTomorrowChecklist] = useState([]);
  const [answers, setAnswers] = useState({});
  const [questionSort, setQuestionSort] = useState("impact");
  const [activeTab, setActiveTab] = useState("artifacts");
  const [reportOpen, setReportOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [runDetail, setRunDetail] = useState(null);
  const [exportInfo, setExportInfo] = useState(null);
  const [uploadFiles, setUploadFiles] = useState([]);
  const [questionTag, setQuestionTag] = useState("all");
  const [settings, setSettings] = useState(() => {
    const saved = safeJsonParse(localStorage.getItem("jobfiller-settings"), {});
    return { ...DEFAULT_SETTINGS, ...saved };
  });
  const [filters, setFilters] = useState({
    search: "",
    status: "all",
    source: "all",
    workModel: "all",
    sort: "newest",
    locations: [],
    customLocation: "",
    remoteOnly: false,
  });
  const [locationOpen, setLocationOpen] = useState(false);
  const [pageNumber, setPageNumber] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [factForm, setFactForm] = useState({ tag: "", question_text: "", answer: "", confidence: 1 });
  const [editingFactId, setEditingFactId] = useState(null);
  const [noteDraft, setNoteDraft] = useState("");

  function scanPayload() {
    const payload = { remote_first: settings.remoteFirst };
    const scanSource = String(settings.scanSource || "all").trim();
    if (scanSource && scanSource !== "all") {
      payload.source = scanSource;
    }
    const scanLimit = Number(settings.scanLimit);
    if (Number.isFinite(scanLimit) && scanLimit > 0) {
      payload.limit = Math.floor(scanLimit);
    }
    const scannerKeywords = String(settings.scannerKeywords || "").trim();
    if (scannerKeywords) {
      payload.scanner_keywords = scannerKeywords;
    }
    return payload;
  }

  async function load() {
    const [jobRows, questionRows, factRows, runRows, health, checklistRows] = await Promise.all([
      api.jobs("newest", settings.remoteFirst),
      api.questions("all", questionSort, questionTag),
      api.facts(),
      api.runs(),
      api.modelHealth().catch(() => null),
      api.tomorrowChecklist().catch(() => []),
    ]);
    setJobs(jobRows);
    setQuestions(questionRows);
    setFacts(factRows);
    setRuns(runRows);
    setModelHealth(health);
    setTomorrowChecklist(Array.isArray(checklistRows) ? checklistRows : []);
    if (!selectedId && jobRows.length) setSelectedId(jobRows[0].id);
  }

  async function loadSettings() {
    const serverSettings = await api.settings();
    const next = settingsFromServer(serverSettings);
    localStorage.setItem("jobfiller-settings", JSON.stringify(next));
    setSettings(next);
  }

  const importUrlValid = isValidImportUrl(url);
  const importDisabledReason = url && !importUrlValid ? "Enter a valid http/https job URL." : "";

  async function loadDetail(id) {
    if (!id) return;
    const jobDetail = await api.job(id);
    setDetail(jobDetail);
    setNoteDraft(jobDetail.job?.notes || "");
  }

  useEffect(() => {
    loadSettings().catch(() => {});
  }, []);

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = setInterval(() => load().catch(() => {}), 30000);
    return () => clearInterval(timer);
  }, [settings.remoteFirst, questionSort, questionTag]);

  useEffect(() => {
    loadDetail(selectedId).catch((err) => setError(err.message));
  }, [selectedId]);

  useEffect(() => {
    setPageNumber(1);
  }, [filters, rowsPerPage]);

  const openQuestions = questions.filter((question) => question.status === "OPEN");
  const questionTags = useMemo(() => [...new Set(questions.map((question) => question.tag))].sort(), [questions]);
  const filteredJobs = useMemo(() => sortJobs(filterJobs(jobs, filters), filters.sort, settings), [jobs, filters, settings]);
  const pagedJobs = filteredJobs.slice((pageNumber - 1) * rowsPerPage, pageNumber * rowsPerPage);
  const maxPage = Math.max(1, Math.ceil(filteredJobs.length / rowsPerPage));
  const sources = useMemo(() => [...new Set(jobs.map((job) => job.source).filter(Boolean))], [jobs]);
  const statuses = useMemo(() => [...new Set(jobs.map((job) => job.status).filter(Boolean))], [jobs]);
  const reprocessJobs = jobs.filter((job) => ["NEEDS_INFO", "QA", "GENERATING", "PARSED", "DISCOVERED"].includes(job.status));
  const latestRun = runs[0];

  async function runAction(action, successMessage = "") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await action();
      if (successMessage) setNotice(successMessage);
      await load();
      if (selectedId) await loadDetail(selectedId);
      return result;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  function openPage(nextPage) {
    setPage(nextPage);
    setNotice("");
    setError("");
  }

  function startScan() {
    return runAction(
      () => api.scan(scanPayload()),
      "Scan complete. Newest jobs processed first.",
    );
  }

  function toggleLocation(value) {
    const next = filters.locations.includes(value)
      ? filters.locations.filter((item) => item !== value)
      : [...filters.locations, value];
    setFilters({ ...filters, locations: next });
  }

  function toggleSelected(id) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  }

  async function exportAll() {
    const result = await runAction(api.exportBundle, "Exported XLSX, JSON, and CSV.");
    setExportInfo(result);
  }

  async function saveFact() {
    const payload = { ...factForm, confidence: Number(factForm.confidence || 1) };
    if (editingFactId) {
      await runAction(() => api.updateFact(editingFactId, payload), "Updated profile fact.");
    } else {
      await runAction(() => api.createFact(payload), "Created profile fact.");
    }
    setFactForm({ tag: "", question_text: "", answer: "", confidence: 1 });
    setEditingFactId(null);
  }

  async function reprocessSelected(ids) {
    const targets = ids.length ? ids : Array.from(selectedIds);
    for (const id of targets) {
      await api.generateArtifacts(id);
    }
    setNotice(`Queued ${targets.length} job${targets.length === 1 ? "" : "s"} for reprocess.`);
    await load();
  }

  async function openArtifactFolder(artifactId) {
    return runAction(async () => {
      try {
        return await api.openArtifactFolderAlias(artifactId);
      } catch (error) {
        return api.openArtifactFolder(artifactId);
      }
    }, "Opened artifact output folder.");
  }

  async function parseUploadedFiles() {
    for (const file of uploadFiles) {
      const textLike = /text|markdown|json|csv|xml|latex|plain/i.test(file.type)
        || /\.(txt|md|markdown|tex|json|csv|log)$/i.test(file.name);
      let extracted = "";
      if (textLike) {
        extracted = (await file.text()).slice(0, 8000);
      }
      await api.createFact({
        tag: `uploaded_${file.name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "")}`,
        question_text: "Assist Upload parsed document",
        answer: [
          `Local support document: ${file.name} (${file.type || "unknown type"}, ${file.size} bytes).`,
          extracted ? `Extracted text:\n${extracted}` : "Binary or unsupported file type; use this fact as a reminder to summarize the document manually if it contains relevant experience.",
        ].join("\n\n"),
        confidence: extracted ? 0.85 : 0.65,
      });
    }
    setNotice(`Parsed ${uploadFiles.length} file${uploadFiles.length === 1 ? "" : "s"} into profile facts.`);
    setUploadFiles([]);
    await load();
  }

  const commonProps = {
    jobs,
    questions,
    openQuestions,
    questionSort,
    setQuestionSort,
    setActiveTab,
    facts,
    runs,
    modelHealth,
    settings,
    setSettings,
    page,
    openPage,
    selectedId,
    setSelectedId,
    selectedIds,
    setSelectedIds,
    runAction,
    answers,
    setAnswers,
    questionTag,
    setQuestionTag,
    questionTags,
    tomorrowChecklist,
    saveFact,
    factForm,
    setFactForm,
    editingFactId,
    setEditingFactId,
    runDetail,
    setRunDetail,
    exportAll,
    exportInfo,
    uploadFiles,
    setUploadFiles,
    parseUploadedFiles,
    reprocessSelected,
    setNotice,
    setError,
    busy,
  };

  return (
    <div className="appShell">
      <Sidebar {...commonProps} />
      <main className="workspace">
        <CommandBar
          busy={busy}
          url={url}
          setUrl={setUrl}
          latestRun={latestRun}
          modelHealth={modelHealth}
          onScan={startScan}
          onImport={() => {
            if (!importUrlValid) return;
            return runAction(async () => {
              await api.importJob({ url });
              setUrl("");
            }, "Imported job URL.");
          }}
          importDisabledReason={importDisabledReason}
          openPage={openPage}
          userMenuOpen={userMenuOpen}
          setUserMenuOpen={setUserMenuOpen}
          settings={settings}
        />
        <MobileNav jobs={jobs} openQuestions={openQuestions} facts={facts} page={page} openPage={openPage} />
        {error && <div className="errorBanner">{error}</div>}
        {notice && <div className="noticeBanner">{notice}</div>}

        {page === "jobs" ? (
          <>
            <SetupPanel settings={settings} modelHealth={modelHealth} openPage={openPage} onScan={startScan} busy={busy} />
            <FilterBar
              filters={filters}
              setFilters={setFilters}
              statuses={statuses}
              sources={sources}
              locationOpen={locationOpen}
              setLocationOpen={setLocationOpen}
              toggleLocation={toggleLocation}
              advancedOpen={advancedOpen}
              setAdvancedOpen={setAdvancedOpen}
              settings={settings}
            />
            {advancedOpen && <AdvancedFilters filters={filters} setFilters={setFilters} settings={settings} setSettings={setSettings} />}
            <section className={`board ${detailOpen ? "" : "detailClosed"}`}>
              <div className="leftPane">
                <JobsTable
                  jobs={pagedJobs}
                  total={jobs.length}
                  filteredTotal={filteredJobs.length}
                  selectedId={selectedId}
                  setSelectedId={(id) => {
                    setSelectedId(id);
                    setDetailOpen(true);
                  }}
                  selectedIds={selectedIds}
                  toggleSelected={toggleSelected}
                  selectAll={() => {
                    const allVisible = pagedJobs.every((job) => selectedIds.has(job.id));
                    setSelectedIds(new Set(allVisible ? [] : pagedJobs.map((job) => job.id)));
                  }}
                  pageNumber={pageNumber}
                  setPageNumber={setPageNumber}
                  maxPage={maxPage}
                  rowsPerPage={rowsPerPage}
                  setRowsPerPage={setRowsPerPage}
                  runAction={runAction}
                  latestRun={latestRun}
                  onOpenArtifactFolder={openArtifactFolder}
                  busy={busy}
                  filters={filters}
                  settings={settings}
                />
                <QuestionQueue
                  questionSort={questionSort}
                  setQuestionSort={setQuestionSort}
                  questions={openQuestions}
                  answers={answers}
                  setAnswers={setAnswers}
                  runAction={runAction}
                    selectJob={(id) => {
                    setSelectedId(id);
                    setActiveTab("questions");
                    setDetailOpen(true);
                  }}
                  openPage={openPage}
                />
              </div>
              {detailOpen && (
                <JobInspector
                  detail={detail}
                  activeTab={activeTab}
                  setActiveTab={setActiveTab}
                  busy={busy}
                  runAction={runAction}
                  onOpenArtifactFolder={openArtifactFolder}
                  close={() => setDetailOpen(false)}
                  setReportOpen={setReportOpen}
                  noteDraft={noteDraft}
                  setNoteDraft={setNoteDraft}
                  setNotice={setNotice}
                />
              )}
            </section>
          </>
        ) : (
          <UtilityPage {...commonProps} />
        )}
      </main>
      {reportOpen && <ReportModal detail={detail} close={() => setReportOpen(false)} />}
    </div>
  );
}

function MobileNav({ jobs, openQuestions, facts, page, openPage }) {
  const items = [
    ["jobs", "Jobs", <Briefcase size={16} />, jobs.length],
    ["questions", "Questions", <HelpCircle size={16} />, openQuestions.length],
    ["tomorrow", "Tomorrow", <CalendarCheck2 size={16} />, 0],
    ["facts", "Facts", <UserRound size={16} />, facts.length],
    ["runs", "Runs", <FileText size={16} />],
    ["reprocess", "Generate", <RefreshCcw size={16} />],
    ["agent", "Agent", <Link2 size={16} />],
    ["assist", "Assist", <Upload size={16} />],
    ["export", "Export", <Download size={16} />],
    ["settings", "Settings", <Settings size={16} />],
    ["health", "Health", <Activity size={16} />],
  ];
  return (
    <nav className="mobileNav" aria-label="Mobile navigation">
      {items.map(([key, label, icon, count]) => (
        <button
          key={key}
          data-testid={`mobile-nav-${key}`}
          className={page === key ? "active" : ""}
          onClick={() => openPage(key)}
        >
          {icon}<span>{label}</span>{count != null && <b>{count}</b>}
        </button>
      ))}
    </nav>
  );
}

function Sidebar({ jobs, openQuestions, facts, openPage, page, settings }) {
  const reprocessCount = jobs.filter((job) => ["NEEDS_INFO", "QA", "GENERATING", "PARSED", "DISCOVERED"].includes(job.status)).length;
  const displayName = settings.candidateName || "Configure Profile";
  const displayLocation = settings.candidateLocation || "Local profile";
  const displayEmail = settings.candidateEmail || "Add email in Settings";
  const initial = displayName.trim().slice(0, 1).toUpperCase() || "J";
  return (
    <aside className="sideRail">
      <button
        className="brandRow navButton"
        data-testid="sidebar-brand-jobs"
        onClick={() => openPage("jobs")}
      >
        <div className="briefcaseMark"><Briefcase size={22} /></div>
        <strong>JobFiller</strong>
      </button>
      <nav className="sideNav">
        <button
          className={page === "jobs" ? "active" : ""}
          data-testid="nav-jobs"
          onClick={() => openPage("jobs")}
        >
          <Briefcase size={18} /> Jobs <span className="countBadge blue">{jobs.length}</span>
        </button>
        <button
          className={page === "questions" ? "active" : ""}
          data-testid="nav-questions"
          onClick={() => openPage("questions")}
        >
          <HelpCircle size={18} /> Questions <span className="countBadge orange">{openQuestions.length}</span>
        </button>
        <button
          className={page === "tomorrow" ? "active" : ""}
          data-testid="nav-tomorrow"
          onClick={() => openPage("tomorrow")}
        >
          <CalendarCheck2 size={18} /> Tomorrow Checklist
        </button>
        <button
          className={page === "facts" ? "active" : ""}
          data-testid="nav-facts"
          onClick={() => openPage("facts")}
        >
          <UserRound size={18} /> Profile Facts <span className="countBadge green">{facts.length}</span>
        </button>
        <button
          className={page === "runs" ? "active" : ""}
          data-testid="nav-runs"
          onClick={() => openPage("runs")}
        >
          <FileText size={18} /> Runs & Logs
        </button>
      </nav>
      <div className="navGroup">TOOLS</div>
      <nav className="sideNav">
        <button
          className={page === "reprocess" ? "active" : ""}
          data-testid="nav-reprocess"
          onClick={() => openPage("reprocess")}
        >
          <RefreshCcw size={18} /> Generate Queue <span className="countBadge purple">{reprocessCount}</span>
        </button>
        <button
          className={page === "assist" ? "active" : ""}
          data-testid="nav-assist"
          onClick={() => openPage("assist")}
        >
          <Upload size={18} /> Assist Upload
        </button>
        <button
          className={page === "agent" ? "active" : ""}
          data-testid="nav-agent"
          onClick={() => openPage("agent")}
        >
          <Link2 size={18} /> Agent Import / MCP
        </button>
        <button
          className={page === "export" ? "active" : ""}
          data-testid="nav-export"
          onClick={() => openPage("export")}
        >
          <FileText size={18} /> Export Workbook
        </button>
      </nav>
      <div className="navGroup">SYSTEM</div>
      <nav className="sideNav">
        <button
          className={page === "settings" ? "active" : ""}
          data-testid="nav-settings"
          onClick={() => openPage("settings")}
        >
          <Settings size={18} /> Settings
        </button>
        <button
          className={page === "health" ? "active" : ""}
          data-testid="nav-health"
          onClick={() => openPage("health")}
        >
          <Activity size={18} /> Model Health
        </button>
      </nav>
      <div className="profileCard">
        <div className="avatar">{initial}</div>
        <div>
          <strong>{displayName}</strong>
          <span>{displayLocation}</span>
          <small>{displayEmail}</small>
        </div>
        <hr />
        <p><Database size={14} /> DB: jobfiller.db</p>
        <p>Version: 0.1.0</p>
      </div>
    </aside>
  );
}

function CommandBar({ busy, url, setUrl, latestRun, modelHealth, onScan, onImport, importDisabledReason, openPage, userMenuOpen, setUserMenuOpen, settings }) {
  const scannerStatus = modelHealth?.scanner || (latestRun?.status === "RUNNING" ? "running" : "idle");
  const workerStatus = modelHealth?.worker || "idle";
  const llmStatus = String(modelHealth?.status || "checking");
  const displayName = settings.candidateName || "Profile";
  const initial = displayName.trim().slice(0, 1).toUpperCase() || "J";

  const statusClass = (value) => {
    if (!value) return "idle";
    const state = String(value).toLowerCase();
    if (state.includes("running")) return "running";
    if (state.includes("not reachable") || state.includes("offline") || state.includes("error")) return "error";
    return "idle";
  };

  return (
    <header className="commandBar">
      <button className="scanButton" onClick={onScan} disabled={busy} data-testid="scan-now">
        {busy ? <Loader2 className="spin" size={16} /> : <Play size={16} />} Scan Now
      </button>
      <label>Import URL</label>
      <div className="urlImport">
        <input
          data-testid="import-url-input"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Paste a job posting URL..."
        />
        <button
          data-testid="import-url-button"
          onClick={onImport}
          disabled={!url || busy || !!importDisabledReason}
          title={importDisabledReason || "Import job URL"}
        >
          Import
        </button>
      </div>
      <button
        data-testid="health-pill-scanner"
        className={`healthPill ${statusClass(scannerStatus)}`}
        onClick={() => openPage("runs")}
      >
        <i /> <strong>Scanner:</strong> <span>{String(scannerStatus)}</span>
      </button>
      <button
        data-testid="health-pill-worker"
        className={`healthPill ${statusClass(workerStatus)}`}
        onClick={() => openPage("reprocess")}
      >
        <i /> <strong>Worker:</strong> <span>{String(workerStatus)}</span>
      </button>
      <button
        data-testid="health-pill-llm"
        className={`healthPill ${statusClass(llmStatus)}`}
        onClick={() => openPage("health")}
      >
        <i /> <strong>Local LLM:</strong> <span>{llmStatus}</span>
      </button>
      <button
        className="plainIcon"
        data-testid="command-open-settings"
        aria-label="Open settings"
        title="Open settings"
        onClick={() => openPage("settings")}
      >
        <Settings size={19} />
      </button>
      <div className="topUserWrap">
        <button
          className="topUser"
          data-testid="top-user-menu"
          onClick={() => setUserMenuOpen(!userMenuOpen)}
        >
          <span>{initial}</span><strong>{displayName}</strong><ChevronDown size={14} />
        </button>
        {userMenuOpen && (
          <div className="userMenu">
            <strong>Remote-first mode</strong>
            <p>{settings.remoteFirst ? "Enabled" : "Disabled"}</p>
            <button data-testid="top-user-settings" onClick={() => { setUserMenuOpen(false); openPage("settings"); }}>Open Settings</button>
          </div>
        )}
      </div>
    </header>
  );
}

function profileReady(settings) {
  return Boolean(settings.candidateName && settings.candidateEmail && settings.candidateSummary);
}

function SetupPanel({ settings, modelHealth, openPage, onScan, busy }) {
  const ready = profileReady(settings);
  const source = settings.scanSource && settings.scanSource !== "all" ? settings.scanSource : "Chrome tabs + sample/manual imports";
  const llmState = modelHealth?.status || "checking";
  return (
    <section className="setupPanel" aria-label="JobFiller setup and scan status">
      <div>
        <span>Profile</span>
        <strong>{ready ? "Ready" : "Needs profile"}</strong>
      </div>
      <div>
        <span>Finder</span>
        <strong>{source}</strong>
      </div>
      <div>
        <span>Limit</span>
        <strong>{settings.scanLimit || 20} jobs</strong>
      </div>
      <div>
        <span>Keywords</span>
        <strong>{settings.scannerKeywords || "default"}</strong>
      </div>
      <div>
        <span>Local LLM</span>
        <strong>{String(llmState)}</strong>
      </div>
      <div className="setupActions">
        <button data-testid="setup-open-settings" onClick={() => openPage("settings")}><Settings size={14} /> Settings</button>
        <button data-testid="setup-open-agent" onClick={() => openPage("agent")}><Link2 size={14} /> Agent Import</button>
        <button data-testid="setup-scan-now" className="blueButton" disabled={busy} onClick={onScan}><Play size={14} /> Scan</button>
      </div>
    </section>
  );
}

function FilterBar({ filters, setFilters, statuses, sources, locationOpen, setLocationOpen, toggleLocation, advancedOpen, setAdvancedOpen }) {
  return (
    <section className="filterBar">
      <label className="searchBox">
        <Search size={16} />
        <input
          data-testid="jobs-search"
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          placeholder="Search jobs..."
        />
      </label>
      <select
        data-testid="jobs-filter-status"
        value={filters.status}
        onChange={(e) => setFilters({ ...filters, status: e.target.value })}
      >
        <option value="all">All Statuses</option>
        {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
      </select>
      <select
        data-testid="jobs-filter-source"
        value={filters.source}
        onChange={(e) => setFilters({ ...filters, source: e.target.value })}
      >
        <option value="all">All Sources</option>
        {sources.map((source) => <option key={source} value={source}>{source}</option>)}
      </select>
      <div className="locationControl">
        <button
          type="button"
          data-testid="jobs-location-toggle"
          onClick={() => setLocationOpen(!locationOpen)}
        >
          <MapPin size={15} /> {filters.locations.length ? `${filters.locations.length} Locations` : "All Locations"} <ChevronDown size={14} />
        </button>
        {locationOpen && <LocationPanel filters={filters} setFilters={setFilters} toggleLocation={toggleLocation} close={() => setLocationOpen(false)} />}
      </div>
      <select
        data-testid="jobs-filter-work-model"
        value={filters.workModel}
        onChange={(e) => setFilters({ ...filters, workModel: e.target.value })}
      >
        <option value="all">All Work Models</option>
        <option value="Remote">Remote</option>
        <option value="Hybrid">Hybrid</option>
        <option value="onsite">Onsite</option>
        <option value="Onsite">Onsite</option>
      </select>
      <select
        className="sortSelect"
        data-testid="jobs-sort"
        value={filters.sort}
        onChange={(e) => setFilters({ ...filters, sort: e.target.value })}
      >
        <option value="newest">Sort: Newest</option>
        <option value="oldest">Sort: Oldest</option>
        <option value="fit">Sort: Highest Fit</option>
        <option value="fit-low">Sort: Lowest Fit</option>
        <option value="grade">Sort: Highest Grade</option>
        <option value="grade-low">Sort: Lowest Grade</option>
        <option value="ready">Sort: Highest Readiness</option>
        <option value="recently-updated">Sort: Recently Updated</option>
        <option value="needs-info">Sort: Needs Info First</option>
        <option value="company">Sort: Company</option>
        <option value="status">Sort: Status</option>
      </select>
      <button
        className={advancedOpen ? "iconButton active" : "iconButton"}
        data-testid="jobs-advanced-toggle"
        type="button"
        aria-label="Advanced job filters"
        aria-expanded={advancedOpen}
        title="Advanced job filters"
        onClick={() => setAdvancedOpen(!advancedOpen)}
      >
        <SlidersHorizontal size={16} />
      </button>
    </section>
  );
}

function AdvancedFilters({ filters, setFilters, settings, setSettings }) {
  function setRemoteFirst(checked) {
    const next = { ...settings, remoteFirst: checked };
    setSettings(next);
    localStorage.setItem("jobfiller-settings", JSON.stringify(next));
  }

  return (
    <section className="advancedFilters">
      <label>
        <input
          data-testid="advanced-remote-first"
          type="checkbox"
          checked={settings.remoteFirst}
          onChange={(e) => setRemoteFirst(e.target.checked)}
        />
        Remote-first ranking
      </label>
      <label>
        <input
          data-testid="advanced-remote-only"
          type="checkbox"
          checked={filters.remoteOnly}
          onChange={(e) => setFilters({ ...filters, remoteOnly: e.target.checked })}
        />
        Remote-only table filter
      </label>
      <button
        data-testid="advanced-clear-filters"
        onClick={() => setFilters({ ...filters, search: "", status: "all", source: "all", workModel: "all", locations: [], customLocation: "", remoteOnly: false })}
      >
        Clear filters
      </button>
    </section>
  );
}

function LocationPanel({ filters, setFilters, toggleLocation, close }) {
  return (
    <div className="locationPanel">
      <div className="locationHead">
        <strong>Location Preferences</strong>
        <button className="plainIcon" data-testid="location-panel-close" aria-label="Close location preferences" title="Close location preferences" onClick={close}><X size={16} /></button>
      </div>
      <input
        data-testid="location-custom"
        value={filters.customLocation}
        onChange={(e) => setFilters({ ...filters, customLocation: e.target.value })}
        placeholder="Custom city, region, timezone, or office..."
      />
      <label className="checkLine">
        <input
          data-testid="location-remote-only"
          type="checkbox"
          checked={filters.remoteOnly}
          onChange={(e) => setFilters({ ...filters, remoteOnly: e.target.checked })}
        />
        Remote-only applications
      </label>
      <div className="locationGroups">
        {LOCATION_GROUPS.map((group) => (
          <div key={group.title}>
            <h4>{group.title}</h4>
            <div className="locationChips">
              {group.items.map((item) => (
                <button
                  key={item}
                  data-testid={locationChipTestId(group.title, item)}
                  className={filters.locations.includes(item) ? "selected" : ""}
                  onClick={() => toggleLocation(item)}
                  type="button"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="locationActions">
        <button
          type="button"
          data-testid="location-clear"
          onClick={() => setFilters({ ...filters, locations: [], customLocation: "", remoteOnly: false })}
        >
          Clear all
        </button>
        <button type="button" className="blueButton" data-testid="location-apply" onClick={close}>Apply</button>
      </div>
    </div>
  );
}

function Logo({ company, small = false }) {
  const logo = logoFor(company);
  return <span className={`companyLogo ${small ? "small" : ""}`} style={logo.style}>{logo.label}</span>;
}

function JobsTable({
  jobs,
  total,
  filteredTotal,
  selectedId,
  setSelectedId,
  selectedIds,
  toggleSelected,
  selectAll,
  pageNumber,
  setPageNumber,
  maxPage,
  rowsPerPage,
  setRowsPerPage,
  runAction,
  latestRun,
  onOpenArtifactFolder,
  busy,
  filters,
  settings,
}) {
  const sortLabel = {
    newest: "Newest first",
    oldest: "Oldest first",
    fit: "Highest fit",
    "fit-low": "Lowest fit",
    grade: "Highest grade",
    "grade-low": "Lowest grade",
    ready: "Highest readiness",
    "recently-updated": "Recently updated",
    "needs-info": "Needs info first",
    company: "Company",
    status: "Status",
  }[filters?.sort || "newest"] || "Custom sort";
  return (
    <section className="jobsSurface">
      <div className="listMeta">
        <strong>{total} jobs</strong>
        <span><ArrowUpDown size={14} /> {sortLabel} · {settings?.remoteFirst ? "remote-first ranking" : "standard ranking"}</span>
        <span>Last run: {latestRun ? `${latestRun.kind} · ${fmtDate(latestRun.started_at)}` : "not run yet"}</span>
        {selectedIds.size > 0 && (
          <button
            data-testid="jobs-reprocess-selected"
            onClick={() => runAction(async () => Promise.all(Array.from(selectedIds).map((id) => api.generateArtifacts(id))), `Generated ${selectedIds.size} selected job pack files.`)}
          >
            Generate packets ({selectedIds.size})
          </button>
        )}
      </div>
      <div className="jobsTable" role="table" aria-label="Jobs table">
        <div role="rowgroup">
        <div className="jobGrid tableHeader" role="row">
          <span role="columnheader">
            <input
              data-testid="jobs-select-all"
              aria-label="Select all visible jobs"
              type="checkbox"
              checked={jobs.length > 0 && jobs.every((job) => selectedIds.has(job.id))}
              onChange={selectAll}
            />
          </span>
          <span role="columnheader">Posted <ArrowDown size={14} /></span>
          <span role="columnheader">Company</span>
          <span role="columnheader">Role</span>
          <span role="columnheader">Location / Model</span>
          <span role="columnheader">Status</span>
          <span role="columnheader">Fit</span>
          <span role="columnheader">Grade</span>
          <span role="columnheader">Ready</span>
          <span role="columnheader">Artifacts</span>
        </div>
        </div>
        <div role="rowgroup">
        {jobs.map((job) => {
          const hasArtifact = Boolean(job.latest_artifact_id);
          const hasResume = Boolean(job.latest_resume_pdf_path);
          const hasLatex = Boolean(job.latest_artifact_id) && Boolean(job.latest_cover_letter_path || job.latest_resume_pdf_path);
          const applyUrl = safeExternalUrl(job.apply_url);
          return (
            <div
              key={job.id}
              data-testid={`job-row-${job.id}`}
              className={`jobGrid jobLine ${selectedId === job.id ? "selected" : ""}`}
              role="row"
              aria-selected={selectedId === job.id}
              tabIndex={0}
              onClick={() => setSelectedId(job.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedId(job.id);
                }
              }}
            >
              <span role="cell">
                <input
                  data-testid={`jobs-row-select-${job.id}`}
                  aria-label={`Select ${job.company} ${job.title}`}
                  type="checkbox"
                  checked={selectedIds.has(job.id)}
                  onChange={(event) => { event.stopPropagation(); toggleSelected(job.id); }}
                  onClick={(event) => event.stopPropagation()}
                />
              </span>
              <span role="cell">{job.posting_age_text || fmtDate(job.posted_at)}</span>
              <strong role="cell"><Logo company={job.company} /> {job.company}</strong>
              <span className="roleCell" role="cell">
                <button
                  className="roleLink"
                  data-testid={`jobs-role-${job.id}`}
                  onClick={(event) => { event.stopPropagation(); setSelectedId(job.id); }}
                >
                  {job.title}
                </button>
                {applyUrl ? (
                  <a
                    href={applyUrl}
                    target="_blank"
                    rel="noreferrer"
                    data-testid={`jobs-role-open-${job.id}`}
                    onClick={(event) => event.stopPropagation()}
                    title={`Open ${job.company} posting URL`}
                    aria-label={`Open ${job.company} posting URL`}
                  >
                    <ExternalLink size={14} />
                  </a>
                ) : (
                  <span className="artifactActionPlaceholder" title="No posting link" />
                )}
              </span>
              <span role="cell"><b>{job.location}</b><small>{job.work_model}</small></span>
              <span role="cell" className={statusClass(job.status)}>{job.status}</span>
              <span role="cell" className="fitText">{job.fit_score}%</span>
              <span role="cell" className={gradeClass(scoreGrade(job))}>{scoreGrade(job)}</span>
              <span role="cell" className={readiness(job) && readiness(job) < 70 ? "readyLow" : "readyText"}>{readiness(job) ? `${readiness(job)}%` : "--"}</span>
              <span className="artifactBits" role="cell">
                {hasResume ? <a href={api.artifactUrl(`/api/artifacts/${job.latest_artifact_id}/resume`)} target="_blank" rel="noreferrer" aria-label={`Open ${job.company} resume PDF`} title={`Open ${job.company} resume PDF`} data-testid={`jobs-artifact-resume-${job.id}`}><FileText size={15} /></a> : <span className="artifactActionPlaceholder" title="No resume generated yet"><FileText size={15} /></span>}
                {job.artifact_count || 0}
                {hasLatex ? <a href={api.artifactUrl(`/api/artifacts/${job.latest_artifact_id}/latex`)} target="_blank" rel="noreferrer" aria-label={`Open ${job.company} resume TeX`} title={`Open ${job.company} resume TeX`} data-testid={`jobs-artifact-latex-${job.id}`}><FileCode2 size={15} /></a> : <span className="artifactActionPlaceholder" title="No LaTeX generated yet"><FileCode2 size={15} /></span>}
                {hasArtifact ? (
                  <button
                    className="plainIcon"
                    disabled={busy}
                    aria-label={`Open artifact folder for ${job.company}`}
                    title={`Open artifact folder for ${job.company}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      onOpenArtifactFolder(job.latest_artifact_id);
                    }}
                    data-testid={`jobs-open-folder-${job.id}`}
                  >
                    <FolderOpen size={15} />
                  </button>
                ) : <span className="artifactActionPlaceholder" title="No artifact folder yet"><FolderOpen size={15} /></span>}
              </span>
            </div>
          );
        })}
        </div>
        {!jobs.length && <div className="noRows">No jobs match the current filters. Clear location/status filters or import a new job URL.</div>}
      </div>
      <div className="pager">
        <button
          data-testid="jobs-page-prev"
          disabled={pageNumber <= 1}
          onClick={() => setPageNumber(Math.max(1, pageNumber - 1))}
        >
          &lt;
        </button>
        {[1, 2, 3].filter((n) => n <= maxPage).map((n) => <button key={n} data-testid={`jobs-page-${n}`} className={pageNumber === n ? "active" : ""} onClick={() => setPageNumber(n)}>{n}</button>)}
        {maxPage > 4 && <span>...</span>}
        {maxPage > 3 && <button data-testid="jobs-page-last" className={pageNumber === maxPage ? "active" : ""} onClick={() => setPageNumber(maxPage)}>{maxPage}</button>}
        <button
          data-testid="jobs-page-next"
          disabled={pageNumber >= maxPage}
          onClick={() => setPageNumber(Math.min(maxPage, pageNumber + 1))}
        >
          &gt;
        </button>
        <select
          data-testid="jobs-page-size"
          value={rowsPerPage}
          onChange={(event) => setRowsPerPage(Number(event.target.value))}
        >
          <option value="10">10 / page</option>
          <option value="20">20 / page</option>
          <option value="50">50 / page</option>
        </select>
        <strong>{filteredTotal ? `${(pageNumber - 1) * rowsPerPage + 1}-${Math.min(pageNumber * rowsPerPage, filteredTotal)} of ${filteredTotal}` : "0 of 0"}</strong>
      </div>
    </section>
  );
}

function QuestionQueue({ questions, answers, setAnswers, runAction, selectJob, openPage, questionSort, setQuestionSort }) {
  const labelBySort = {
    impact: "Highest Impact",
    "impact-low": "Lowest Impact",
    recent: "Most Recent",
    oldest: "Oldest",
    status: "Status",
  };
  return (
    <section className="questionSurface">
      <div className="sectionHeader">
        <h2>Blocking Questions Queue <span>{questions.length}</span></h2>
        <div>
          <label htmlFor="dashboard-question-sort" style={{ marginRight: "8px", color: "#64748b", fontSize: "12px" }}>Sort:</label>
          <select
            data-testid="dashboard-question-sort"
            id="dashboard-question-sort"
            value={questionSort}
            onChange={(event) => setQuestionSort(event.target.value)}
          >
            <option value="impact">Highest Impact</option>
            <option value="impact-low">Lowest Impact</option>
            <option value="recent">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="status">Status</option>
          </select>
          <button data-testid="question-open-list" onClick={() => openPage("questions")}><ArrowUpDown size={14} /> {labelBySort[questionSort] || "Questions"}</button>
        </div>
      </div>
      <QuestionTable questions={questions.slice(0, 3)} answers={answers} setAnswers={setAnswers} runAction={runAction} selectJob={selectJob} />
      <button className="viewAll" data-testid="question-view-all" onClick={() => openPage("questions")}>View all questions <ArrowDown size={14} /></button>
    </section>
  );
}

function impactFor(tag) {
  if (tag.includes("kubernetes")) return "Medium";
  if (tag.includes("healthcare") || tag.includes("metrics")) return "Medium";
  return "High";
}

function QuestionTable({ questions, answers, setAnswers, runAction, selectJob }) {
  const impactLabel = (tag, fallbackImpact) => {
    if (!fallbackImpact) return impactFor(tag);
    return fallbackImpact;
  };
  return (
    <div className="questionTable" role="table" aria-label="Blocking questions table">
      <div role="rowgroup">
      <div className="questionGrid qHeader" role="row"><span role="columnheader">Impact</span><span role="columnheader">Job</span><span role="columnheader">Question</span><span role="columnheader">Tags</span><span role="columnheader">Asked</span><span role="columnheader">Your Answer</span><span role="columnheader">Actions</span></div>
      </div>
      <div role="rowgroup">
      {questions.map((q) => (
        <div className="questionGrid qLine" key={q.id} role="row">
          <span role="cell" className={`impact ${(impactLabel(q.tag, q.impact) || "").toLowerCase()}`}>
            {impactLabel(q.tag, q.impact)}
          </span>
          <span role="cell" className="qJob"><Logo company={q.company} small /><strong>{q.company}</strong><small>{q.title}</small></span>
        <span role="cell">{q.question_text}</span>
        <span role="cell" className="tagList">{q.tag.split("_").map((tag) => <b key={tag}>{tag}</b>)}</span>
        <span role="cell">{timeAgo(q.created_at)}</span>
          <span role="cell"><input data-testid={`question-answer-${q.id}`} aria-label={`Answer ${q.company} ${q.tag} question`} value={answers[q.id] || ""} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} placeholder="Type your answer here..." /></span>
          <span role="cell" className="qActions">
            <button className="blueButton" data-testid={`question-save-${q.id}`} onClick={() => runAction(() => api.answer(q.id, answers[q.id] || ""), "Saved answer, updated reusable facts, and reprocessed affected jobs.")} disabled={!answers[q.id]} title={!answers[q.id] ? "Type an answer before saving." : "Save answer"}><Save size={14} /> Save</button>
            <button data-testid={`question-skip-${q.id}`} onClick={() => runAction(() => api.skipQuestion(q.id), "Question skipped.")}><SkipForward size={14} /> Skip</button>
            <button data-testid={`question-open-${q.id}`} aria-label={`Open context for ${q.company} question`} title={`Open context for ${q.company} question`} onClick={() => selectJob(q.job_id)}><ExternalLink size={14} /></button>
          </span>
        </div>
      ))}
      </div>
      {!questions.length && <div className="noRows">No questions in this view.</div>}
    </div>
  );
}

function JobInspector({ detail, activeTab, setActiveTab, busy, runAction, close, setReportOpen, noteDraft, setNoteDraft, onOpenArtifactFolder, setNotice }) {
  if (!detail?.job) return <aside className="inspector"><div className="emptyState">Select a job</div></aside>;
  const job = detail.job;
  const post = detail.post || {};
  const artifact = detail.artifact || {};
  const grade = detail.grade || {};
  const applyUrl = safeExternalUrl(job.apply_url);
  const requirementChips = String(job.key_requirements || job.keywords || "").split(/[;,]/).map((item) => item.trim()).filter(Boolean).slice(0, 8);
  const ready = readiness(job) || (grade.ready_to_send ? 92 : 55);
  return (
    <aside className="inspector">
      <div className="inspectorTitle">
        <h1>
          {job.title}{" "}
          {applyUrl && (
            <a data-testid={`inspector-apply-${job.id}`} href={applyUrl} target="_blank" rel="noreferrer" title="Open apply page">
              <Link2 size={16} />
            </a>
          )}
        </h1>
        <button className="plainIcon" data-testid="inspector-close" aria-label="Close job detail panel" title="Close job detail panel" onClick={close}><X size={18} /></button>
      </div>
      <div className="updatedLine"><span className={statusClass(job.status)}>{job.status}</span><span>Last updated: {fmtDate(job.updated_at)}</span></div>
      <div className="companyBlock">
        <Logo company={job.company} />
        <div><strong>{job.company}</strong><span>{job.role_family || "Software"} · {job.source}</span></div>
        <p>{job.location}<br />{job.work_model}</p>
      </div>
      <section className="summaryBlock"><h3>Job Summary</h3><p>{post.summary || `Tailored application packet for ${job.title} at ${job.company}. Focus on ${job.keywords || job.key_requirements}.`}</p></section>
      <section className="summaryBlock"><h3>Key Requirements</h3><div className="requirementChips">{requirementChips.map((chip) => <span key={chip}>{chip}</span>)}</div></section>
      <section className="summaryBlock"><h3>Compensation</h3><p>{post.compensation || "Not listed · verify on company application page"}</p></section>
      <section className="summaryBlock"><h3>Materials</h3><p>{job.materials || "None listed"}</p></section>
      <section className="summaryBlock"><h3>Manual Questions</h3><p>{job.manual_questions || "No additional manual questions."}</p></section>
      <div className="tabs" role="tablist" aria-label="Job detail tabs">
        {["artifacts", "grade", "questions", "notes"].map((tab) => (
          <button
            data-testid={`inspector-tab-${tab}`}
            key={tab}
            role="tab"
            type="button"
            aria-selected={activeTab === tab}
            className={activeTab === tab ? "active" : ""}
            onClick={() => setActiveTab(tab)}
          >
            {tab === "grade" ? "Local LLM Grade" : tab[0].toUpperCase() + tab.slice(1)}
            {tab === "questions" ? ` (${job.open_questions})` : ""}
          </button>
        ))}
      </div>
      {activeTab === "artifacts" && <ArtifactsPanel artifact={artifact} job={job} busy={busy} runAction={runAction} onOpenArtifactFolder={onOpenArtifactFolder} />}
      {activeTab === "grade" && <GradePanel grade={grade} ready={ready} setReportOpen={setReportOpen} />}
      {activeTab === "questions" && <InspectorQuestions questions={detail.questions || []} />}
      {activeTab === "notes" && <NotesPanel job={job} noteDraft={noteDraft} setNoteDraft={setNoteDraft} runAction={runAction} />}
    </aside>
  );
}

function ArtifactsPanel({ artifact, job, busy, runAction, onOpenArtifactFolder }) {
  const [editor, setEditor] = useState(null);
  const artifactTime = artifact.created_at ? fmtDate(artifact.created_at) : "not generated yet";
  const hasResume = Boolean(artifact.resume_pdf_url);
  const hasCoverLetter = Boolean(artifact.cover_letter_url);
  const hasLatex = Boolean(artifact.resume_tex_path);
  const applyUrl = safeExternalUrl(job.apply_url);

  async function openEditor(kind, title) {
    if (!artifact.id) return;
    await runAction(async () => {
      const result = await api.artifactContent(artifact.id, kind);
      setEditor({ kind, title, content: result.content, path: result.path });
    });
  }

  async function saveEditor() {
    if (!editor || !artifact.id) return;
    await runAction(
      () => api.updateArtifactContent(artifact.id, { kind: editor.kind, content: editor.content }),
      "Saved artifact edit as a new revision.",
    );
    setEditor(null);
  }

  return (
    <div className="artifactPanel">
      <ArtifactCard icon={<FileText size={20} />} title="Resume (Tailored)" name={artifact.resume_pdf_path?.split(/[\\/]/).pop() || `candidate-resume-${job.company.toLowerCase().replace(/\W+/g, "-")}.pdf`} meta={`Rev: ${artifact.revision || 0} · ${artifactTime} · ${artifact.compile_status || "pending compile"}`} latest={Boolean(artifact.resume_pdf_url)} actions={[
        hasResume
          ? <a key="download" data-testid={`artifact-resume-download-${job.id}`} href={api.artifactUrl(artifact.resume_pdf_url)} download aria-label={`Download resume PDF for ${job.company}`} title={`Download resume PDF for ${job.company}`}><Download size={16} /></a>
          : <button key="download-disabled" className="artifactActionPlaceholder" disabled title="Resume PDF not ready"><Download size={16} /></button>,
        hasResume
          ? <a key="open" data-testid={`artifact-resume-open-${job.id}`} href={api.artifactUrl(artifact.resume_pdf_url)} target="_blank" rel="noreferrer" aria-label={`Open resume PDF for ${job.company}`} title={`Open resume PDF for ${job.company}`}><ExternalLink size={16} /></a>
          : <button key="open-disabled" className="artifactActionPlaceholder" disabled title="Resume PDF not ready"><ExternalLink size={16} /></button>,
        hasLatex
          ? <a key="tex" data-testid={`artifact-resume-tex-${job.id}`} href={api.artifactUrl(`/api/artifacts/${artifact.id}/latex`)} target="_blank" rel="noreferrer" aria-label={`Open resume TeX for ${job.company}`} title={`Open resume TeX for ${job.company}`}>TEX</a>
          : <button key="tex-disabled" className="artifactActionPlaceholder" disabled title="LaTeX not ready">TEX</button>,
        artifact.id
          ? <button key="open-folder-resume" data-testid={`artifact-resume-folder-${job.id}`} onClick={() => onOpenArtifactFolder(artifact.id)} disabled={busy} aria-label="Open artifact folder"><FolderOpen size={16} /></button>
          : <button key="open-folder-disabled" className="artifactActionPlaceholder" disabled aria-label="No artifact folder"><FolderOpen size={16} /></button>,
        artifact.id && hasResume
          ? <button key="regrade-resume" data-testid={`artifact-resume-regrade-${job.id}`} onClick={() => runAction(() => api.gradeArtifact(artifact.id), "Local LLM regrade completed.")} disabled={busy}>Regrade</button>
          : <button key="regrade-disabled" className="artifactActionPlaceholder" disabled>Regrade</button>,
        artifact.id
          ? <button key="edit-tex" data-testid={`artifact-resume-edit-${job.id}`} aria-label="Edit resume LaTeX" onClick={() => openEditor("latex", "Edit Resume LaTeX")} disabled={busy}><Pencil size={16} /></button>
          : <button key="edit-tex-disabled" className="artifactActionPlaceholder" disabled>Edit</button>,
      ]} />
      <ArtifactCard icon={<FileText size={20} />} title="Cover Letter" name={artifact.cover_letter_path?.split(/[\\/]/).pop() || "cover-letter.md"} meta={`Rev: ${artifact.revision || 0} · ${artifactTime} · Markdown`} latest={Boolean(artifact.cover_letter_url)} actions={[
        hasCoverLetter
          ? <a key="download" data-testid={`artifact-cover-download-${job.id}`} href={api.artifactUrl(artifact.cover_letter_url)} download aria-label={`Download cover letter for ${job.company}`} title={`Download cover letter for ${job.company}`}><Download size={16} /></a>
          : <button key="download-disabled" className="artifactActionPlaceholder" disabled title="Cover letter not ready"><Download size={16} /></button>,
        hasCoverLetter
          ? <a key="open" data-testid={`artifact-cover-open-${job.id}`} href={api.artifactUrl(artifact.cover_letter_url)} target="_blank" rel="noreferrer" aria-label={`Open cover letter for ${job.company}`} title={`Open cover letter for ${job.company}`}><ExternalLink size={16} /></a>
          : <button key="open-disabled" className="artifactActionPlaceholder" disabled title="Cover letter not ready"><ExternalLink size={16} /></button>,
        artifact.id
          ? <button key="open-folder-cover" data-testid={`artifact-cover-folder-${job.id}`} onClick={() => onOpenArtifactFolder(artifact.id)} disabled={busy} aria-label="Open artifact folder"><FolderOpen size={16} /></button>
          : <button key="open-folder-cover-disabled" className="artifactActionPlaceholder" disabled aria-label="No artifact folder"><FolderOpen size={16} /></button>,
        artifact.id
          ? <button key="edit" data-testid={`artifact-cover-edit-${job.id}`} aria-label="Edit cover letter" onClick={() => openEditor("cover-letter", "Edit Cover Letter")} disabled={busy}><Pencil size={16} /></button>
          : <button key="edit-disabled" className="artifactActionPlaceholder" disabled>Edit</button>,
      ]} />
      <div className="detailActions">
        <button data-testid={`artifact-reprocess-${job.id}`} onClick={() => runAction(() => api.generateArtifacts(job.id), "Generated resume and cover letter for selected job.")} disabled={busy}><RefreshCcw size={15} /> {artifact.id ? "Regenerate resume + cover letter" : "Generate resume + cover letter"}</button>
        <button data-testid={`artifact-assist-resume-${job.id}`} onClick={() => runAction(() => api.assistUpload(job.id, "resume"), "Upload helper launched.")} disabled={!hasResume || busy}><Upload size={15} /> Assist Upload</button>
        <button data-testid={`artifact-assist-cover-${job.id}`} onClick={() => runAction(() => api.assistUpload(job.id, "cover-letter"), "Cover-letter upload helper launched.")} disabled={!hasCoverLetter || busy}><Upload size={15} /> Cover Letter</button>
        {applyUrl && <a data-testid={`artifact-apply-${job.id}`} href={applyUrl} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Apply URL</a>}
      </div>
      {editor && (
        <ArtifactEditorModal
          editor={editor}
          setEditor={setEditor}
          saveEditor={saveEditor}
          close={() => setEditor(null)}
          busy={busy}
        />
      )}
    </div>
  );
}

function ArtifactCard({ icon, title, name, meta, latest, actions }) {
  return <div className="artifactCard"><div className="artifactIcon">{icon}</div><div><strong>{title} {latest && <span>Latest</span>}</strong><p>{name}</p><small>{meta}</small></div><div className="artifactActions">{actions}</div></div>;
}

function ArtifactEditorModal({ editor, setEditor, saveEditor, close, busy }) {
  return (
    <div className="modalBackdrop">
      <div className="modal artifactEditorModal">
        <div className="modalHead">
          <div>
            <h2>{editor.title}</h2>
            <p>{editor.path}</p>
          </div>
          <button className="plainIcon" data-testid="artifact-editor-close" aria-label="Close artifact editor" title="Close artifact editor" onClick={close}><X size={16} /></button>
        </div>
        <textarea
          data-testid="artifact-editor-textarea"
          value={editor.content}
          onChange={(event) => setEditor({ ...editor, content: event.target.value })}
          spellCheck="false"
        />
        <div className="modalActions">
          <button data-testid="artifact-editor-cancel" onClick={close}>Cancel</button>
          <button data-testid="save-artifact-editor" className="blueButton" onClick={saveEditor} disabled={busy || !editor.content.trim()}><Save size={14} /> Save New Revision</button>
        </div>
      </div>
    </div>
  );
}

function GradePanel({ grade, ready, compact = false, setReportOpen }) {
  const risks = grade.risks || [];
  const score = grade.overall_grade || "-";
  const backendScores = grade.scores || {};
  const scoreRows = [
    ["Role Fit", backendScores.role_fit],
    ["Tailoring", backendScores.tailoring],
    ["Strength", backendScores.technical_strength],
    ["Formatting", backendScores.formatting],
    ["ATS Readability", backendScores.ats_readability],
  ].map(([label, value]) => {
    const numeric = Number(value);
    const display = Number.isFinite(numeric)
      ? Math.round(numeric <= 1 ? numeric * 100 : numeric)
      : null;
    return [label, display];
  });
  return (
    <section className={compact ? "gradePanel compact" : "gradePanel"}>
      <h3>Local LLM Grade (Resume)</h3>
      <div className="gradeContent">
        <div className="gradeCircle"><strong>{score}</strong><span>Overall Score</span></div>
        <div className="scoreRows">
          {scoreRows.map(([label, value]) => (
            <p key={label}><span>{label}</span><b>{value == null ? "-" : `${value}/100`}</b></p>
          ))}
        </div>
        <div className="readinessBox"><span>Readiness</span><strong>{ready}%</strong><b>{ready >= 80 ? "High" : "Needs Info"}</b><button data-testid="grade-open-report" onClick={() => setReportOpen(true)}>View Full Report</button></div>
      </div>
      {!compact && risks.length > 0 && <div className="riskList">{risks.slice(0, 2).map((risk, index) => <p key={index}>{risk}</p>)}</div>}
    </section>
  );
}

function InspectorQuestions({ questions }) {
  return <div className="inspectorList">{questions.length ? questions.map((question) => <p key={question.id}><strong>{question.tag}</strong>{question.question_text}</p>) : <p>No questions for this job.</p>}</div>;
}

function NotesPanel({ job, noteDraft, setNoteDraft, runAction }) {
  return (
    <div className="inspectorList">
      <textarea value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} placeholder="Add manual form fields, recruiter context, follow-up timing, or application notes." />
      <button className="blueButton" data-testid="notes-save" onClick={() => runAction(() => api.patchJob(job.id, { notes: noteDraft }), "Saved job notes.")}><Save size={14} /> Save Notes</button>
    </div>
  );
}

function TomorrowChecklistPage({ tomorrowChecklist, setNotice }) {
  const rows = tomorrowChecklist || [];
  const readyCount = rows.filter((row) => row.ready_to_send).length;

  function copyList() {
    const lines = rows
      .map((row) => [row.company, row.title, safeExternalUrl(row.apply_url)].filter(Boolean).join(" - "))
      .filter(Boolean)
      .join("\n");
    const copyText = lines || "No checklist items.";
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(copyText).catch(() => {});
    }
    if (setNotice) setNotice(`Copied ${rows.length} item${rows.length === 1 ? "" : "s"} to clipboard.`);
  }

  return (
    <>
      <PageHeader title="Tomorrow Checklist">
        <button className="blueButton" onClick={copyList} data-testid="tomorrow-copy-list"><CalendarCheck2 size={14} /> Copy Apply List</button>
        <span>{readyCount}/{rows.length} ready artifacts</span>
      </PageHeader>
      <div className="checklistSurface">
        {rows.length ? (
          rows.map((row) => {
            const applyUrl = safeExternalUrl(row.apply_url);
            return (
            <div className="checklistCard" key={row.job_id}>
              <div className="checklistMetaHeader">
                <div>
                  <strong>{row.apply_order}. {row.company}</strong>
                  <p>{row.title}</p>
                </div>
                <span className={statusClass(row.status)}>{row.status}</span>
              </div>
              <div className="checklistMeta">
                <p><b>Location:</b> {row.location || "Not listed"} / {row.work_model || "Not listed"}</p>
                <p><b>Posted:</b> {row.posting_age_text || (row.posted_at ? "Posted" : "Unknown")}</p>
                <p><b>Fit / Grade:</b> {row.fit_score} / {row.grade || "-"}</p>
                <p><b>Ready:</b> {row.ready_to_send ? "Yes" : "No"}</p>
              </div>
              <p><b>Action:</b> Open apply page, attach the tailored resume and cover letter, then verify materials and manual notes.</p>
              <div className="checklistMetaPaths">
                {applyUrl && <a href={applyUrl} target="_blank" rel="noreferrer">Apply</a>}
                {row.resume_pdf_path && <p><b>Resume:</b> {row.resume_pdf_path}</p>}
                {row.cover_letter_path && <p><b>Cover Letter:</b> {row.cover_letter_path}</p>}
                {row.resume_tex_path && <p><b>Resume TeX:</b> {row.resume_tex_path}</p>}
              </div>
              <p><b>Materials Needed:</b> {row.materials || "No materials listed"}</p>
              <p><b>Manual Checks:</b> {row.manual_questions || "No extra manual checks."}</p>
            </div>
            );
          })
        ) : (
          <div className="noRows">No jobs ready for the tomorrow queue yet.</div>
        )}
      </div>
    </>
  );
}

function UtilityPage(props) {
  const pageMap = {
    questions: <QuestionsPage {...props} />,
    tomorrow: <TomorrowChecklistPage {...props} />,
    facts: <FactsPage {...props} />,
    runs: <RunsPage {...props} />,
    reprocess: <ReprocessPage {...props} />,
    agent: <AgentImportPage {...props} />,
    assist: <AssistUploadPage {...props} />,
    export: <ExportPage {...props} />,
    settings: <SettingsPage {...props} />,
    health: <ModelHealthPage {...props} />,
  };
  return <section className="utilityPage">{pageMap[props.page] || pageMap.questions}</section>;
}

function AgentImportPage({ modelHealth, setNotice }) {
  const examplePayload = JSON.stringify(
    {
      source: "codex-or-claude-code",
      process: false,
      jobs: [
        {
          url: "https://example.com/jobs/product-analyst",
          company: "Example Company",
          title: "Entry Level Role",
          location: "Remote",
          work_model: "Remote",
          key_requirements: "Requirements from the posting",
          keywords: "Role keywords from the posting",
          posting_age_text: "2 hours ago",
        },
      ],
    },
    null,
    2,
  );
  function copyPayload() {
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(examplePayload).catch(() => {});
    }
    setNotice?.("Copied MCP export payload shape.");
  }
  return (
    <>
      <PageHeader title="Agent Import / MCP">
        <button className="blueButton" data-testid="agent-copy-payload" onClick={copyPayload}><Link2 size={14} /> Copy Payload</button>
      </PageHeader>
      <div className="splitPage">
        <div className="cardList">
          <div className="infoCard">
            <strong>Codex</strong>
            <p>Project config: .codex/config.toml</p>
            <p>Tool: export_jobs_to_jobfiller</p>
          </div>
          <div className="infoCard">
            <strong>Claude Code</strong>
            <p>Project config: .mcp.json</p>
            <p>Runtime file: outputs/jobfiller-runtime.json</p>
          </div>
          <div className="infoCard">
            <strong>Current Worker</strong>
            <p>Scanner: {modelHealth?.scanner || "unknown"}</p>
            <p>Queue depth: {modelHealth?.queue_depth ?? "unknown"}</p>
          </div>
        </div>
        <pre className="detailJson">{examplePayload}</pre>
      </div>
    </>
  );
}

function PageHeader({ title, children }) {
  return <div className="utilityHeader"><h1>{title}</h1><div>{children}</div></div>;
}

function QuestionsPage({
  questions,
  answers,
  setAnswers,
  runAction,
  setSelectedId,
  setActiveTab,
  openPage,
  questionSort,
  setQuestionSort,
  questionTag,
  setQuestionTag,
  questionTags = [],
}) {
  const [status, setStatus] = useState("OPEN");
  const [search, setSearch] = useState("");
  const query = search.toLowerCase();
  const rows = sortQuestionsByImpact(
    questions.filter(
      (q) =>
        (status === "all" || q.status === status) &&
        (questionTag === "all" || q.tag === questionTag) &&
        (!query || `${q.company} ${q.title} ${q.tag} ${q.question_text}`.toLowerCase().includes(query)),
    ),
    questionSort,
  );
  return (
    <>
      <PageHeader title="Questions">
        <input
          data-testid="questions-search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search questions..."
        />
        <select data-testid="questions-status-filter" value={status} onChange={(e) => setStatus(e.target.value)}><option value="OPEN">Open</option><option value="ANSWERED">Answered</option><option value="SKIPPED">Skipped</option><option value="all">All</option></select>
        <select data-testid="questions-tag-filter" value={questionTag} onChange={(e) => setQuestionTag(e.target.value)}>
          <option value="all">All Tags</option>
          {questionTags.map((tag) => <option key={tag} value={tag}>{tag}</option>)}
        </select>
        <select data-testid="questions-sort" value={questionSort} onChange={(e) => setQuestionSort(e.target.value)}>
          <option value="impact">Highest Impact</option>
          <option value="impact-low">Lowest Impact</option>
          <option value="recent">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="status">Status</option>
        </select>
      </PageHeader>
      <QuestionTable
        questions={rows}
        answers={answers}
        setAnswers={setAnswers}
        runAction={runAction}
        selectJob={(id) => {
          setActiveTab("questions");
          setSelectedId(id);
          openPage("jobs");
        }}
      />
    </>
  );
}

function FactsPage({ facts, factForm, setFactForm, editingFactId, setEditingFactId, saveFact, runAction }) {
  return (
    <>
      <PageHeader title="Profile Facts"><button className="blueButton" data-testid="fact-save" onClick={saveFact} disabled={!factForm.tag.trim() || !factForm.answer.trim()} title={!factForm.tag.trim() || !factForm.answer.trim() ? "Enter a fact tag and answer before saving." : "Save profile fact"}><Plus size={14} /> {editingFactId ? "Update Fact" : "Add Fact"}</button></PageHeader>
      <div className="formGrid">
        <input data-testid="fact-tag-input" value={factForm.tag} onChange={(e) => setFactForm({ ...factForm, tag: e.target.value })} placeholder="fact tag, e.g. remote_preference" />
        <input data-testid="fact-question-input" value={factForm.question_text} onChange={(e) => setFactForm({ ...factForm, question_text: e.target.value })} placeholder="source question" />
        <input data-testid="fact-confidence-input" value={factForm.confidence} onChange={(e) => setFactForm({ ...factForm, confidence: e.target.value })} placeholder="confidence" />
        <textarea data-testid="fact-answer-input" value={factForm.answer} onChange={(e) => setFactForm({ ...factForm, answer: e.target.value })} placeholder="truthful reusable fact" />
      </div>
      <div className="cardList">
        {facts.map((fact) => <div className="infoCard" key={fact.id}><strong>{fact.tag}</strong><p>{fact.answer}</p><span>Confidence {fact.confidence}</span><div><button data-testid={`fact-edit-${fact.id}`} onClick={() => { setEditingFactId(fact.id); setFactForm(fact); }}><Pencil size={14} /> Edit</button><button data-testid={`fact-delete-${fact.id}`} onClick={() => runAction(() => api.deleteFact(fact.id), "Deleted profile fact.")}><Trash2 size={14} /> Delete</button></div></div>)}
      </div>
    </>
  );
}

function RunsPage({ runs, runDetail, setRunDetail, runAction }) {
  return (
    <>
      <PageHeader title="Runs & Logs"><span>Latest 50 processing events</span></PageHeader>
      <div className="splitPage">
        <div className="cardList">{runs.map((run) => <button className="infoCard" data-testid={`run-row-${run.id}`} key={run.id} onClick={() => runAction(async () => setRunDetail(await api.run(run.id)))}><strong>{run.kind}</strong><span className={statusClass(run.status)}>{run.status}</span><p>{run.message}</p><small>{fmtDate(run.started_at)}</small></button>)}</div>
        <pre className="detailJson">{JSON.stringify(runDetail || runs[0] || {}, null, 2)}</pre>
      </div>
    </>
  );
}

function ReprocessPage({ jobs, selectedIds, setSelectedIds, reprocessSelected, busy }) {
  const queue = jobs.filter((job) => ["NEEDS_INFO", "QA", "GENERATING", "PARSED", "DISCOVERED"].includes(job.status));
  return (
    <>
      <PageHeader title="Generate Queue"><button className="blueButton" data-testid="reprocess-selected" disabled={!selectedIds.size || busy} title={!selectedIds.size ? "Select at least one job to generate." : "Generate selected application packets"} onClick={() => reprocessSelected([])}><RefreshCcw size={14} /> Generate Selected</button></PageHeader>
      <div className="cardList">{queue.map((job) => <label className="infoCard checkCard" key={job.id}><input data-testid={`reprocess-job-${job.id}`} type="checkbox" checked={selectedIds.has(job.id)} onChange={() => { const next = new Set(selectedIds); next.has(job.id) ? next.delete(job.id) : next.add(job.id); setSelectedIds(next); }} /><strong>{job.company}</strong><p>{job.title}</p><span className={statusClass(job.status)}>{job.status}</span></label>)}</div>
    </>
  );
}

function AssistUploadPage({ uploadFiles, setUploadFiles, parseUploadedFiles, selectedId, jobs, runAction }) {
  const selected = jobs.find((job) => job.id === selectedId);
  return (
    <>
      <PageHeader title="Assist Upload"><button className="blueButton" data-testid="assist-parse-files" disabled={!uploadFiles.length} title={!uploadFiles.length ? "Choose one or more local files to parse." : "Parse selected files into profile facts"} onClick={parseUploadedFiles}><Upload size={14} /> Parse Selected Files</button></PageHeader>
      <div className="infoCard">
        <input data-testid="assist-file-input" type="file" multiple onChange={(event) => setUploadFiles(Array.from(event.target.files || []))} />
        <p>Upload resumes, cover letters, transcripts, certifications, work samples, or project descriptions. Text-like files are parsed locally into reusable profile facts; binary files are tracked as local evidence reminders.</p>
        <button data-testid="assist-launch-helper" disabled={!selected} title={!selected ? "Select a job before launching the upload helper." : "Launch upload helper for selected job"} onClick={() => selected && runAction(() => api.assistUpload(selected.id, "resume"), "Upload helper launched for selected job.")}>Launch helper for selected job</button>
      </div>
    </>
  );
}

function ExportPage({ exportAll, exportInfo, modelHealth }) {
  const exportReady = {
    xlsx: Boolean(modelHealth?.artifact_exports?.workbook_exists),
    json: Boolean(modelHealth?.artifact_exports?.json_export_exists),
    csv: Boolean(modelHealth?.artifact_exports?.csv_export_exists),
  };
  return (
    <>
      <PageHeader title="Export Workbook"><button className="blueButton" data-testid="export-workbook" onClick={exportAll}><Download size={14} /> Export XLSX / JSON / CSV</button></PageHeader>
      <div className="cardList">
        {exportReady.xlsx ? (
          <a className="infoCard" data-testid="export-link-xlsx" href={api.artifactUrl("/api/workbook/latest")} download><strong>XLSX Workbook</strong><p>Full application tracking workbook.</p></a>
        ) : (
          <button className="infoCard disabledAction" disabled>Export once to generate XLSX workbook</button>
        )}
        {exportReady.json ? (
          <a className="infoCard" data-testid="export-link-json" href={api.artifactUrl("/api/export/latest.json")} download><strong>JSON Export</strong><p>Machine-readable jobs, artifacts, and questions.</p></a>
        ) : (
          <button className="infoCard disabledAction" disabled>Export once to generate JSON export</button>
        )}
        {exportReady.csv ? (
          <a className="infoCard" data-testid="export-link-csv" href={api.artifactUrl("/api/export/latest.csv")} download><strong>CSV Export</strong><p>Spreadsheet-friendly job rows.</p></a>
        ) : (
          <button className="infoCard disabledAction" disabled>Export once to generate CSV export</button>
        )}
      </div>
      {exportInfo && <pre className="detailJson">{JSON.stringify(exportInfo, null, 2)}</pre>}
    </>
  );
}

function SettingsPage({ settings, setSettings, setNotice, setError }) {
  const [draft, setDraft] = useState(settings);
  const [localError, setLocalError] = useState("");
  useEffect(() => {
    setDraft(settings);
  }, [settings]);
  async function saveSettings() {
    const parsedProfile = parseCandidateProfileJson(draft.candidateProfileJson);
    if (!parsedProfile.ok) {
      setLocalError(parsedProfile.error);
      setError?.(parsedProfile.error);
      return;
    }
    try {
      setLocalError("");
      await api.updateSettings(settingsToServer(draft, parsedProfile.value));
      localStorage.setItem("jobfiller-settings", JSON.stringify(draft));
      setSettings(draft);
      setNotice?.("Saved settings.");
    } catch (error) {
      const message = error?.message || "Could not save settings.";
      setLocalError(message);
      setError?.(message);
    }
  }
  const profileJson = parseCandidateProfileJson(draft.candidateProfileJson);
  return (
    <>
      <PageHeader title="Settings"><button className="blueButton" data-testid="settings-save" onClick={saveSettings} disabled={!profileJson.ok}><Save size={14} /> Save Settings</button></PageHeader>
      {(localError || !profileJson.ok) && <div className="errorBanner">{localError || profileJson.error}</div>}
      <div className="formGrid settingsGrid">
        <label>Candidate name
          <input data-testid="settings-candidate-name" value={draft.candidateName} onChange={(e) => setDraft({ ...draft, candidateName: e.target.value })} />
        </label>
        <label>Candidate email
          <input data-testid="settings-candidate-email" value={draft.candidateEmail} onChange={(e) => setDraft({ ...draft, candidateEmail: e.target.value })} />
        </label>
        <label>Candidate location
          <input data-testid="settings-candidate-location" value={draft.candidateLocation} onChange={(e) => setDraft({ ...draft, candidateLocation: e.target.value })} />
        </label>
        <label>Candidate summary
          <textarea data-testid="settings-candidate-summary" value={draft.candidateSummary} onChange={(e) => setDraft({ ...draft, candidateSummary: e.target.value })} />
        </label>
        <label><input data-testid="settings-remote-first" type="checkbox" checked={draft.remoteFirst} onChange={(e) => setDraft({ ...draft, remoteFirst: e.target.checked })} /> Remote-first job ranking and scan preferences</label>
        <label>Preferred locations
          <input data-testid="settings-preferred-locations" value={draft.preferredLocations} onChange={(e) => setDraft({ ...draft, preferredLocations: e.target.value })} />
        </label>
        <label>Scanner source
          <select data-testid="settings-scan-source" value={draft.scanSource || "all"} onChange={(e) => setDraft({ ...draft, scanSource: e.target.value })}>
            <option value="all">All</option>
            <option value="chrome">Chrome tabs</option>
            <option value="seed">Sample jobs</option>
          </select>
        </label>
        <label>Scan limit
          <input
            data-testid="settings-scan-limit"
            type="number"
            min={1}
            max={100}
            value={draft.scanLimit}
            onChange={(e) => setDraft({ ...draft, scanLimit: Number(e.target.value || 0) })}
          />
        </label>
        <label>Scanner keywords
          <textarea data-testid="settings-scanner-keywords" value={draft.scannerKeywords} onChange={(e) => setDraft({ ...draft, scannerKeywords: e.target.value })} />
        </label>
        <label>Ollama URL
          <input data-testid="settings-ollama-url" value={draft.ollamaUrl} onChange={(e) => setDraft({ ...draft, ollamaUrl: e.target.value })} />
        </label>
        <label>Ollama model
          <input data-testid="settings-ollama-model" value={draft.ollamaModel} onChange={(e) => setDraft({ ...draft, ollamaModel: e.target.value })} placeholder="e.g. local-model:latest" />
        </label>
        <label>Full candidate profile JSON
          <textarea data-testid="settings-candidate-profile-json" value={draft.candidateProfileJson} onChange={(e) => setDraft({ ...draft, candidateProfileJson: e.target.value })} />
        </label>
      </div>
    </>
  );
}

function ModelHealthPage({ modelHealth, runAction }) {
  const entries = Object.entries(modelHealth || {});
  return (
    <>
      <PageHeader title="Model Health"><button className="blueButton" data-testid="model-health-refresh" onClick={() => runAction(api.modelHealth, "Model health refreshed.")}><Activity size={14} /> Test Local LLM</button></PageHeader>
      <div className="healthGrid">
        {entries.map(([key, value]) => (
          <div className="infoCard" key={key}>
            <strong>{key}</strong>
            {typeof value === "object" && value !== null ? (
              <pre className="detailJson miniJson">{JSON.stringify(value, null, 2)}</pre>
            ) : (
              <p>{String(value)}</p>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

function ReportModal({ detail, close }) {
  const grade = detail?.grade || {};
  return (
    <div className="modalBackdrop">
      <div className="modal">
        <div className="modalHead"><h2>Full Local LLM Report</h2><button className="plainIcon" data-testid="report-modal-close" aria-label="Close full Local LLM report" title="Close full Local LLM report" onClick={close}><X size={16} /></button></div>
        <pre>{JSON.stringify({ job: detail?.job, grade, questions: detail?.questions }, null, 2)}</pre>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
