import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Archive,
  Briefcase01 as Briefcase,
  CalendarCheck02 as CalendarCheck,
  Check,
  ClipboardCheck,
  Copy01 as Copy,
  Download01 as Download,
  File02 as FileText,
  HelpCircle,
  LinkExternal01 as ExternalLink,
  Mail01 as Mail,
  Plus,
  RefreshCcw01 as RefreshCcw,
  Save01 as Save,
  Send01 as Send,
  Settings01 as Settings,
  Sliders04 as Sliders,
  Upload01 as Upload,
  User01 as User,
  XClose as X,
  Zap,
} from "@untitledui/icons";
import { getRoute } from "../router/routes.jsx";
import { applySearch, paginateRows, sortRows, uniqueOptions } from "../lib/table";
import { api } from "../api";
import {
  ActionBar,
  ArtifactCard,
  Button,
  DataTable,
  EmptyState,
  EntityAvatar,
  FilterBar,
  GradeBadge,
  InspectorPanel,
  MetricCard,
  NoticeCard,
  PageHeader,
  PaginationFooter,
  ReadyIndicator,
  StatusBadge,
  companyLogoUrl,
} from "../components/ui";

const pageCopy = {
  jobs: ["Jobs", "Browse, filter, and manage discovered job opportunities.", Briefcase],
  "email-alerts": ["Email Alerts", "Review application emails, acceptance updates, rejection notices, and action-needed alerts.", Mail],
  questions: ["Questions", "Review extracted questions, approve answers, and maintain reusable responses.", HelpCircle],
  "apply-queue": ["Apply Queue", "Track applications from ready packet to submitted status.", Send],
  "profile-facts": ["Profile Facts", "Manage structured profile data, evidence, and reusable career context.", User],
  "runs-logs": ["Runs & Logs", "Inspect automation runs, errors, timings, and generated artifacts.", Activity],
  "generate-queue": ["Auto Generate", "Monitor jobs as JobFiller automatically creates application packets.", Zap],
  "assist-upload": ["Assist Upload", "Upload documents and convert them into structured application context.", Upload],
  "agent-import-mcp": ["Agent Import / MCP", "Connect finders, import job URLs, and manage agent-based discovery.", ExternalLink],
  "export-workbook": ["Export Workbook", "Build structured exports for review, backup, reporting, or handoff.", Download],
  settings: ["Settings", "Configure account, automation, model, appearance, and privacy settings.", Settings],
  "model-health": ["Model Health", "Monitor local models, queues, latency, errors, and system readiness.", Activity],
};

const pageCounts = {
  jobs: (s) => `${s.jobs.length} jobs`,
  "email-alerts": (s) => `${s.emailAlerts.length} alerts`,
  questions: (s) => `${s.questions.length} questions`,
  "apply-queue": (s) => `${s.applications.length} queued`,
  "profile-facts": (s) => `${s.profileFacts.length} facts`,
  "runs-logs": (s) => `${s.runs.length.toLocaleString()} runs`,
  "generate-queue": (s) => `${s.generationTasks.length} jobs`,
  "assist-upload": (s) => `${s.uploads.length} uploads`,
  "agent-import-mcp": (s) => `${s.integrations.length} sources`,
  "export-workbook": (s) => `${s.workbookExports.length} exports`,
  settings: () => "11 sections",
  "model-health": (s) => `${s.modelHealthServices.length} services`,
};

function fieldCell(primary, secondary) {
  return (
    <span className="cellStack">
      <strong>{primary}</strong>
      {secondary && <small>{secondary}</small>}
    </span>
  );
}

function companyCell(row) {
  const name = row.company || row.name || "Unknown Company";
  return (
    <span className="companyCell">
      <EntityAvatar name={name} logoUrl={companyLogoUrl(name, row.sourceUrl || row.applyUrl || row.url)} />
      <span className="companyName">{name}</span>
    </span>
  );
}

function boolText(value) {
  return value ? "Yes" : "No";
}

function scorePercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  if (numeric <= 1) return Math.round(numeric * 100);
  if (numeric <= 5) return Math.round(numeric * 20);
  return Math.max(0, Math.min(100, Math.round(numeric)));
}

function titleize(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

const APPLICATION_STATE_FILTER_OPTIONS = ["Discovered", "Applied", "Action Needed", "Interview", "Rejected"];
const LEGACY_JOB_STATUS_FILTER_OPTIONS = ["Review", "Ready", "Generating", "Needs Info"];
const APPLY_QUEUE_STATUSES = ["Discovered", "Ready", "Action Needed", "Needs Info", "Applying", "Applied", "Interview", "Rejected", "Follow-up", "Submitted"];
const STATUS_FILTER_ALIASES = {
  DISCOVERED: "Discovered",
  NEW: "Discovered",
  APPLIED: "Applied",
  SUBMITTED: "Applied",
  ACTION_NEEDED: "Action Needed",
  NEEDS_INFO: "Action Needed",
  INTERVIEW: "Interview",
  REJECTED: "Rejected",
  QA: "Review",
  PARSED: "Review",
  REVIEW: "Review",
  READY: "Ready",
  GENERATING: "Generating",
};

function statusFilterLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const normalized = raw.toUpperCase().replace(/[\s-]+/g, "_");
  return STATUS_FILTER_ALIASES[normalized] || titleize(raw);
}

function statusFilterOptions(rows, defaults) {
  return Array.from(
    new Set([
      "all",
      ...defaults,
      ...rows.flatMap((row) => [statusFilterLabel(row.status), statusFilterLabel(row.pipelineStatus)]).filter(Boolean),
    ]),
  );
}

function rowMatchesStatusFilter(row, value) {
  const candidates = [row.status, row.pipelineStatus].filter(Boolean);
  return candidates.some((candidate) => String(candidate) === value || statusFilterLabel(candidate) === value);
}

function byId(rows, id) {
  return rows.find((row) => row.id === id || row.id === String(id)) || rows[0] || null;
}

function pageMetrics(pageId, s) {
  if (pageId === "jobs") {
    return [
      ["Profile", "Complete", User, "success"],
      ["Finder", "Indeed", Briefcase, "blue"],
      ["Limit", "100 / day", Sliders, "neutral"],
      ["Keywords", "12 active", FileText, "neutral"],
      ["Local LLM", "Ollama", Activity, "success"],
    ];
  }
  if (pageId === "questions") {
    return [["Unanswered", 24], ["Needs Review", 13, null, "warning"], ["Reusable Answers", 86], ["High Confidence", "71%", null, "success"]];
  }
  if (pageId === "email-alerts") {
    return [
      ["Action Needed", s.emailAlerts.filter((x) => x.category === "Action Needed").length, null, "warning"],
      ["Accepted", s.emailAlerts.filter((x) => x.state === "Accepted").length, null, "success"],
      ["Applied", s.emailAlerts.filter((x) => x.state === "Applied").length, null, "success"],
      ["Rejections", s.emailAlerts.filter((x) => x.category === "Rejection").length, null, "error"],
      ["Interviews", s.emailAlerts.filter((x) => x.category === "Interview").length, null, "blue"],
    ];
  }
  if (pageId === "apply-queue") {
    return [["Ready", s.applications.filter((x) => x.status === "Ready").length, null, "success"], ["Blocked", s.applications.filter((x) => x.status === "Needs Info" || x.status === "Action Needed").length, null, "warning"], ["Applied This Week", 9], ["Follow-ups Due", 3]];
  }
  if (pageId === "profile-facts") {
    return [["Verified Facts", s.profileFacts.filter((x) => x.verified).length, null, "success"], ["Needs Review", s.profileFacts.filter((x) => !x.verified).length, null, "warning"], ["Resume Sources", 4], ["Used This Week", 73]];
  }
  if (pageId === "runs-logs") {
    return [["Healthy", "98.2%", null, "success"], ["Running", s.runs.filter((x) => x.status === "Running").length], ["Failed", s.runs.filter((x) => x.status === "Failed").length, null, "error"], ["Avg Runtime", "42s"]];
  }
  if (pageId === "generate-queue") {
    return [
      ["Blocked", s.generationTasks.filter((x) => x.status === "Blocked").length, null, "warning"],
      ["Queued", s.generationTasks.filter((x) => x.status === "Queued").length],
      ["Running", s.generationTasks.filter((x) => x.status === "Running").length],
      ["Ready", s.generationTasks.filter((x) => x.status === "Completed").length, null, "success"],
    ];
  }
  if (pageId === "agent-import-mcp") {
    return [["Finder Active", "Yes", null, "success"], ["MCP Servers", 3], ["Imports Today", 84], ["Errors", 2, null, "error"]];
  }
  if (pageId === "export-workbook") {
    return [["Templates", 6], ["Last Export", "Today", null, "success"], ["Rows Selected", 247], ["Scheduled Exports", 2]];
  }
  if (pageId === "model-health") {
    return [["System Healthy", "Yes", null, "success"], ["Local LLM Online", "Ollama", null, "success"], ["Queue Depth", 19], ["Avg Latency", "3.8s"]];
  }
  return [];
}

const JOBS_TABLE_MIN_WIDTH = "1490px";

function sourceRows(pageId, s) {
  if (pageId === "jobs") return s.jobs;
  if (pageId === "email-alerts") return s.emailAlerts;
  if (pageId === "questions") return s.questions;
  if (pageId === "apply-queue") return s.applications;
  if (pageId === "profile-facts") return s.profileFacts;
  if (pageId === "runs-logs") return s.runs;
  if (pageId === "generate-queue") return s.generationTasks;
  if (pageId === "assist-upload") return s.uploads;
  if (pageId === "agent-import-mcp") return s.integrations;
  if (pageId === "export-workbook") return s.workbookExports;
  if (pageId === "model-health") return s.modelHealthServices;
  return settingsRows(s.settings);
}

function settingsRows(settings) {
  return [
    { id: "Account", section: "Account", setting: "Account name", value: settings.accountName, status: "Saved" },
    { id: "Profile", section: "Profile", setting: "Profile email", value: settings.profileEmail, status: "Saved" },
    { id: "Job Finder", section: "Job Finder", setting: "Daily scan limit", value: settings.finderLimit, status: "Saved" },
    { id: "Application Defaults", section: "Application Defaults", setting: "Default source", value: settings.defaultSource, status: "Saved" },
    { id: "LLM Providers", section: "LLM Providers", setting: "Cloud model", value: settings.cloudModel ? "Enabled" : "Disabled", status: "Local" },
    { id: "Local LLM", section: "Local LLM", setting: "Provider", value: settings.localModel, status: "Connected" },
    { id: "Notifications", section: "Notifications", setting: "Follow-up reminders", value: settings.notifications ? "On" : "Off", status: "Saved" },
    { id: "Privacy", section: "Privacy", setting: "Local-first privacy mode", value: settings.privacyMode ? "On" : "Off", status: "Saved" },
    { id: "Appearance", section: "Appearance", setting: "Theme", value: settings.appearance, status: "Saved" },
    { id: "Billing / Limits", section: "Billing / Limits", setting: "Usage tier", value: "Local", status: "Free" },
    { id: "Danger Zone", section: "Danger Zone", setting: "Reset local data", value: "Manual confirmation", status: "Protected" },
  ];
}

function columnConfig(pageId, actions) {
  const actionLabel = <span className="actionsDots">...</span>;
  const configs = {
    jobs: [
      { key: "posted", label: "Posted", width: "118px", sortable: true, testId: "jobs-sort-posted" },
      { key: "imported", label: "Imported", width: "120px", sortable: true, testId: "jobs-sort-imported" },
      { key: "source", label: "Imported from", width: "120px", sortable: true, testId: "jobs-sort-source", render: (row) => titleize(row.source || "manual") },
      { key: "company", label: "Company", width: "minmax(190px,.9fr)", sortable: true, testId: "jobs-sort-company", render: (row) => companyCell(row) },
      { key: "role", label: "Role", width: "minmax(300px,1.4fr)", sortable: true, testId: "jobs-sort-role", render: (row) => <span data-testid={`jobs-role-${row.id}`}>{fieldCell(row.role, row.keywords.join(", "))}</span> },
      { key: "location", label: "Location", width: "minmax(170px,.8fr)", sortable: true, testId: "jobs-sort-location", render: (row) => fieldCell(row.location, row.workModel) },
      { key: "status", label: "Status", width: "104px", sortable: true, testId: "jobs-sort-status", render: (row) => <StatusBadge status={row.status} /> },
      { key: "fit", label: "Fit", width: "56px", sortable: true, testId: "jobs-sort-fit", render: (row) => <span className="fitText">{row.fit}%</span> },
      { key: "grade", label: "Grade", width: "62px", sortable: true, testId: "jobs-sort-grade", render: (row) => <GradeBadge grade={row.grade} /> },
      { key: "ready", label: "Ready", width: "72px", sortable: true, testId: "jobs-sort-ready", render: (row) => <span className={`readyIndicator ${row.ready ? "ready" : "notReady"}`} aria-label={row.ready ? "Ready" : "Not ready"}>{row.ready ? <Check size={14} /> : <X size={14} />}</span> },
      { key: "files", label: "Files", width: "56px", sortable: true, testId: "jobs-sort-artifacts" },
      { key: "actions", label: "", width: "42px", render: () => actionLabel },
    ],
    "email-alerts": [
      { key: "receivedAt", label: "Received", width: "118px", sortable: true, render: (row) => row.received },
      { key: "company", label: "Company", width: "minmax(150px,.8fr)", sortable: true, render: (row) => companyCell(row) },
      { key: "role", label: "Role", width: "minmax(220px,1fr)", sortable: true },
      { key: "state", label: "State", width: "128px", sortable: true, render: (row) => <StatusBadge status={row.state} /> },
      { key: "subject", label: "Subject", width: "minmax(260px,1.25fr)", sortable: true, render: (row) => <span className="truncateText">{row.subject}</span> },
      { key: "sender", label: "Sender", width: "minmax(170px,.8fr)", sortable: true },
      { key: "followUp", label: "Follow-up", width: "minmax(260px,1.2fr)", render: (row) => <span className="truncateText">{row.followUp}</span> },
      { key: "source", label: "Source", width: "86px", sortable: true },
      { key: "actions", label: "Actions", width: "66px", render: () => actionLabel },
    ],
    questions: [
      { key: "company", label: "Company", width: "minmax(140px,.8fr)", sortable: true, render: (row) => companyCell(row) },
      { key: "role", label: "Role", width: "minmax(160px,.9fr)", sortable: true },
      { key: "question", label: "Question", width: "minmax(280px,1.4fr)", render: (row) => fieldCell(row.question, row.factsUsed.join(", ")) },
      { key: "type", label: "Type", width: "100px", sortable: true },
      { key: "suggestedAnswer", label: "Suggested Answer", width: "minmax(250px,1.2fr)", render: (row) => <span className="truncateText">{row.suggestedAnswer}</span> },
      { key: "status", label: "Status", width: "116px", sortable: true, render: (row) => <StatusBadge status={row.status} /> },
      { key: "confidence", label: "Confidence", width: "92px", sortable: true, render: (row) => `${row.confidence}%` },
      { key: "updated", label: "Updated", width: "86px", sortable: true },
      { key: "actions", label: "Actions", width: "66px", render: () => actionLabel },
    ],
    "apply-queue": [
      { key: "priority", label: "Priority", width: "74px", sortable: true },
      { key: "company", label: "Company", width: "minmax(140px,.8fr)", sortable: true, render: (row) => companyCell(row) },
      { key: "role", label: "Role", width: "minmax(210px,1fr)", sortable: true },
      { key: "fit", label: "Fit", width: "66px", sortable: true, render: (row) => `${row.fit}%` },
      { key: "packet", label: "Packet", width: "92px", sortable: true },
      { key: "questions", label: "Questions", width: "106px", sortable: true },
      { key: "status", label: "Status", width: "120px", sortable: true, render: (row) => <StatusBadge status={row.status} /> },
      { key: "due", label: "Due", width: "88px", sortable: true },
      { key: "owner", label: "Owner", width: "82px", sortable: true },
      { key: "actions", label: "Actions", width: "66px", render: () => actionLabel },
    ],
    "profile-facts": [
      { key: "category", label: "Category", width: "120px", sortable: true },
      { key: "field", label: "Field", width: "minmax(150px,.8fr)", sortable: true },
      { key: "value", label: "Value", width: "minmax(280px,1.4fr)", render: (row) => <span className="truncateText">{row.value}</span> },
      { key: "confidence", label: "Confidence", width: "96px", sortable: true, render: (row) => `${row.confidence}%` },
      { key: "source", label: "Source", width: "120px", sortable: true },
      { key: "usedIn", label: "Used In", width: "96px", sortable: true },
      { key: "verified", label: "Verified", width: "84px", sortable: true, render: (row) => <ReadyIndicator ready={row.verified} value={null} /> },
      { key: "updated", label: "Updated", width: "90px", sortable: true },
      { key: "actions", label: "Actions", width: "66px", render: () => actionLabel },
    ],
    "runs-logs": [
      { key: "started", label: "Started", width: "92px", sortable: true },
      { key: "type", label: "Type", width: "94px", sortable: true },
      { key: "target", label: "Target", width: "minmax(190px,1fr)", sortable: true },
      { key: "status", label: "Status", width: "110px", sortable: true, render: (row) => <StatusBadge status={row.status} /> },
      { key: "steps", label: "Steps", width: "68px", sortable: true },
      { key: "duration", label: "Duration", width: "86px", sortable: true },
      { key: "model", label: "Model", width: "102px", sortable: true },
      { key: "cost", label: "Cost", width: "72px", sortable: true },
      { key: "artifacts", label: "Artifacts", width: "82px", sortable: true },
      { key: "actions", label: "Actions", width: "66px", render: () => actionLabel },
    ],
    "generate-queue": [
      { key: "priority", label: "Priority", width: "76px", sortable: true },
      { key: "task", label: "Task", width: "minmax(150px,.8fr)", sortable: true },
      { key: "company", label: "Company", width: "minmax(130px,.8fr)", sortable: true },
      { key: "role", label: "Role", width: "minmax(190px,1fr)", sortable: true },
      { key: "status", label: "Status", width: "126px", sortable: true, render: (row) => <StatusBadge status={row.status} /> },
      { key: "files", label: "Files", width: "72px", sortable: true },
      { key: "created", label: "Created", width: "92px", sortable: true },
      { key: "ready", label: "Ready", width: "76px", sortable: true, render: (row) => <ReadyIndicator ready={row.ready} value={null} /> },
      { key: "actions", label: "Actions", width: "66px", render: () => actionLabel },
    ],
    "assist-upload": [
      { key: "filename", label: "Filename", width: "minmax(220px,1fr)", sortable: true, render: (row) => fieldCell(row.filename, row.summary) },
      { key: "type", label: "Type", width: "92px", sortable: true },
      { key: "extractedFacts", label: "Extracted Facts", width: "120px", sortable: true },
      { key: "status", label: "Status", width: "110px", sortable: true, render: (row) => <StatusBadge status={row.status} /> },
      { key: "imported", label: "Imported", width: "96px", sortable: true },
      { key: "actions", label: "Actions", width: "66px", render: () => actionLabel },
    ],
    "agent-import-mcp": [
      { key: "name", label: "Server", width: "minmax(160px,.9fr)", sortable: true, render: (row) => <span className="companyCell"><EntityAvatar name={row.name} />{row.name}</span> },
      { key: "status", label: "Status", width: "110px", sortable: true, render: (row) => <StatusBadge status={row.status} /> },
      { key: "tools", label: "Tools", width: "76px", sortable: true },
      { key: "lastSeen", label: "Last Seen", width: "104px", sortable: true },
      { key: "auth", label: "Auth", width: "92px", sortable: true },
      { key: "errors", label: "Errors", width: "76px", sortable: true },
      { key: "actions", label: "Actions", width: "66px", render: () => actionLabel },
    ],
    "export-workbook": [
      { key: "template", label: "Template", width: "minmax(220px,1fr)", sortable: true },
      { key: "status", label: "Status", width: "114px", sortable: true, render: (row) => <StatusBadge status={row.status} /> },
      { key: "rows", label: "Rows", width: "96px", sortable: true },
      { key: "created", label: "Created", width: "126px", sortable: true },
      { key: "sheets", label: "Included Sheets", width: "minmax(280px,1.2fr)", render: (row) => row.sheets.join(", ") },
      { key: "actions", label: "Actions", width: "66px", render: () => actionLabel },
    ],
    settings: [
      { key: "section", label: "Section", width: "170px", sortable: true },
      { key: "setting", label: "Setting", width: "minmax(220px,1fr)", sortable: true },
      { key: "value", label: "Value", width: "minmax(220px,1fr)", sortable: true },
      { key: "status", label: "Status", width: "110px", sortable: true, render: (row) => <StatusBadge status={row.status} /> },
    ],
    "model-health": [
      { key: "service", label: "Service", width: "minmax(180px,.9fr)", sortable: true, render: (row) => <span className="companyCell"><EntityAvatar name={row.service} />{row.service}</span> },
      { key: "status", label: "Status", width: "112px", sortable: true, render: (row) => <StatusBadge status={row.status} /> },
      { key: "latency", label: "Latency", width: "92px", sortable: true },
      { key: "lastCheck", label: "Last Check", width: "116px", sortable: true },
      { key: "version", label: "Version", width: "130px", sortable: true },
      { key: "errors", label: "Errors", width: "78px", sortable: true },
      { key: "actions", label: "Actions", width: "66px", render: () => actionLabel },
    ],
  };
  return configs[pageId] || configs.jobs;
}

function searchFields(pageId) {
  return {
    jobs: ["company", "role", "location", "status", "source"],
    "email-alerts": ["company", "role", "subject", "sender", "state", "category", "followUp"],
    questions: ["company", "role", "question", "type", "status"],
    "apply-queue": ["company", "role", "status", "owner"],
    "profile-facts": ["category", "field", "value", "source"],
    "runs-logs": ["type", "target", "status", "model"],
    "generate-queue": ["task", "company", "role", "status"],
    "assist-upload": ["filename", "type", "status", "summary"],
    "agent-import-mcp": ["name", "status", "auth"],
    "export-workbook": ["template", "status", (row) => row.sheets?.join(" ")],
    settings: ["section", "setting", "value", "status"],
    "model-health": ["service", "status", "version"],
  }[pageId];
}

const JOB_ADVANCED_FILTER_KEYS = ["roleGroup", "company", "location", "workModel", "employment", "datePosted", "fitMin", "hasFiles"];
const JOB_ROLE_GROUPS = ["all", "Backend", "Frontend", "Full Stack", "ML / AI", "Data / Analytics", "Product", "SRE / Infrastructure", "QA", "Developer Relations", "Software Engineering"];

function roleGroupForJob(row) {
  const text = `${row.role || ""} ${(row.keywords || []).join(" ")} ${row.notes || ""}`.toLowerCase();
  if (text.includes("developer relations") || text.includes("devrel") || text.includes("developer experience")) return "Developer Relations";
  if (text.includes("site reliability") || text.includes("sre") || text.includes("infrastructure") || text.includes("observability")) return "SRE / Infrastructure";
  if (text.includes("full stack") || text.includes("full-stack")) return "Full Stack";
  if (text.includes("frontend") || text.includes("front-end") || text.includes("react") || text.includes("canvas")) return "Frontend";
  if (text.includes("backend") || text.includes("back-end") || text.includes("api") || text.includes("distributed")) return "Backend";
  if (text.includes("machine learning") || text.includes(" ml ") || text.includes("ai") || text.includes("evaluation") || text.includes("python")) return "ML / AI";
  if (text.includes("data") || text.includes("analytics") || text.includes("analyst")) return "Data / Analytics";
  if (text.includes("product manager") || text.includes("product")) return "Product";
  if (text.includes("qa") || text.includes("quality") || text.includes("testing")) return "QA";
  return "Software Engineering";
}

function filterIsActive(value) {
  return Boolean(value && value !== "all");
}

function advancedJobFilterCount(filters) {
  return JOB_ADVANCED_FILTER_KEYS.filter((key) => filterIsActive(filters[key])).length;
}

function parseJobDate(value) {
  const text = String(value || "").trim();
  if (!text || text === "Unknown") return 0;
  const currentYear = new Date().getFullYear();
  const withYear = text.match(/^([A-Za-z]{3,})\s+(\d{1,2}),?\s+(.+)$/);
  const timestamp = Date.parse(withYear ? `${withYear[1]} ${withYear[2]}, ${currentYear} ${withYear[3]}` : text);
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function jobTimestamp(row) {
  const explicit = Number(row.postedAt || row.importedAt || 0);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;
  return parseJobDate(row.posted) || parseJobDate(row.imported);
}

function jobColumnTimestamp(row, key) {
  const explicit = Number(key === "posted" ? row.postedAt : row.importedAt);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;
  return parseJobDate(row[key]);
}

function jobMatchesDateFilter(row, value) {
  if (!filterIsActive(value)) return true;
  const ranges = { "24h": 1, "7d": 7, "30d": 30 };
  const days = ranges[value];
  const timestamp = jobTimestamp(row);
  if (!days || !timestamp) return false;
  return Date.now() - timestamp <= days * 24 * 60 * 60 * 1000;
}

function matchesAdvancedJobFilters(row, filters) {
  if (filterIsActive(filters.roleGroup) && roleGroupForJob(row) !== filters.roleGroup) return false;
  if (filterIsActive(filters.company) && row.company !== filters.company) return false;
  if (filterIsActive(filters.location) && row.location !== filters.location) return false;
  if (filterIsActive(filters.workModel) && row.workModel !== filters.workModel) return false;
  if (filterIsActive(filters.employment) && row.employment !== filters.employment) return false;
  if (filterIsActive(filters.fitMin) && Number(row.fit || 0) < Number(filters.fitMin)) return false;
  if (filterIsActive(filters.hasFiles) && String(Number(row.files || 0) > 0) !== filters.hasFiles) return false;
  return jobMatchesDateFilter(row, filters.datePosted);
}

function selectOptions(values, label) {
  return values.map((value) => (value === "all" ? { value, label } : { value, label: value }));
}

function AdvancedJobFilters({ rows, filters, actions }) {
  const activeCount = advancedJobFilterCount(filters);
  const setFilter = (key, value) => actions.setFilter("jobs", key, value);
  const clearAdvanced = () => actions.resetFilters("jobs");
  const fields = [
    ["roleGroup", "Role", selectOptions(JOB_ROLE_GROUPS, "Role")],
    ["company", "Company", selectOptions(uniqueOptions(rows, "company"), "Company")],
    ["location", "Location", selectOptions(uniqueOptions(rows, "location"), "Location")],
    ["workModel", "Workplace", selectOptions(uniqueOptions(rows, "workModel"), "Workplace")],
    ["employment", "Job type", selectOptions(uniqueOptions(rows, "employment"), "Job type")],
    ["datePosted", "Date posted", [
      { value: "all", label: "Date posted" },
      { value: "24h", label: "Past 24 hours" },
      { value: "7d", label: "Past week" },
      { value: "30d", label: "Past month" },
    ]],
    ["fitMin", "Minimum fit", [
      { value: "all", label: "Fit score" },
      { value: "90", label: "90%+" },
      { value: "80", label: "80%+" },
      { value: "70", label: "70%+" },
      { value: "60", label: "60%+" },
    ]],
    ["hasFiles", "Artifacts", [
      { value: "all", label: "Artifacts" },
      { value: "true", label: "Has artifacts" },
      { value: "false", label: "No artifacts" },
    ]],
  ];
  return (
    <section className="advancedFilterPanel" aria-label="Advanced job filters">
      <div className="advancedFilterHeader">
        <div>
          <strong>Advanced job filters</strong>
          <span>{activeCount ? `${activeCount} active advanced filter${activeCount === 1 ? "" : "s"}` : "No advanced filters active"}</span>
        </div>
        <Button size="sm" variant="ghost" icon={X} disabled={!activeCount} onClick={clearAdvanced} data-testid="advanced-clear-filters">Clear advanced</Button>
      </div>
      <p className="advancedFilterHint">Remote-first ranking</p>
      <div className="advancedFilterGrid">
        {fields.map(([key, label, options]) => (
          <label className="advancedFilterField" key={key}>
            <span>{label}</span>
            <select value={filters[key] || "all"} onChange={(event) => setFilter(key, event.target.value)} aria-label={label}>
              {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
        ))}
      </div>
      <div className="locationQuickFilters">
        <Button size="sm" variant="ghost" data-testid="jobs-location-toggle" onClick={() => setFilter("location", filters.location === "all" ? "Remote" : "all")}>Locations</Button>
        <Button size="sm" variant="ghost" data-testid="location-chip-remote" onClick={() => setFilter("location", "Remote")}>Remote</Button>
        <input data-testid="location-custom" value={filters.customLocation || ""} onChange={(event) => setFilter("customLocation", event.target.value)} placeholder="Custom location" />
        <Button size="sm" variant="ghost" data-testid="location-clear" onClick={() => { setFilter("location", "all"); setFilter("customLocation", ""); }}>Clear</Button>
        <Button size="sm" variant="ghost" data-testid="location-apply" onClick={() => filters.customLocation && setFilter("location", filters.customLocation)}>Apply</Button>
      </div>
    </section>
  );
}

const legacyJobSortValues = {
  posted: ["newest", "oldest"],
  imported: ["imported", "imported-oldest"],
  source: ["source", "source-desc"],
  company: ["company", "company-desc"],
  role: ["role", "role-desc"],
  location: ["location", "location-desc"],
  status: ["status", "status-desc"],
  fit: ["fit", "fit-low"],
  grade: ["grade", "grade-low"],
  ready: ["ready", "ready-low"],
  files: ["artifacts", "artifacts-low"],
};

const legacyJobSortToState = Object.fromEntries(
  Object.entries(legacyJobSortValues).flatMap(([key, values]) => [
    [values[0], [key, "asc"]],
    [values[1], [key, "desc"]],
  ]),
);

function legacyJobSortValue(state) {
  const values = legacyJobSortValues[state.sortKey || "imported"] || legacyJobSortValues.imported;
  return state.sortDirection === "desc" ? values[1] : values[0];
}

function JobsCompatibilityControls({ state, actions }) {
  const value = legacyJobSortValue(state);
  return (
    <select
      className="srOnly"
      data-testid="jobs-sort"
      value={value}
      onChange={(event) => {
        const [key, direction] = legacyJobSortToState[event.target.value] || ["imported", "desc"];
        actions.setSort("jobs", key, direction);
      }}
      aria-label="Jobs sort"
    >
      {Object.values(legacyJobSortValues).flatMap((values) => values).map((option) => (
        <option key={option} value={option}>{option}</option>
      ))}
    </select>
  );
}

function filtersFor(pageId, rows, filters, actions) {
  const optionRows = pageId === "jobs" ? rows.map((row) => ({ source: "manual", ...row })) : rows;
  const filter = (key, label, options, testId) => ({
    key,
    label,
    testId,
    options: options.map((value) => (value === "all" ? { value, label } : { value, label: value })),
    value: filters[key] || "all",
    onChange: (value) => actions.setFilter(pageId, key, value),
  });
  if (pageId === "jobs") return [
    filter("status", "Status", statusFilterOptions(optionRows, [...APPLICATION_STATE_FILTER_OPTIONS, ...LEGACY_JOB_STATUS_FILTER_OPTIONS])),
    filter("source", "Source", uniqueOptions(optionRows, "source")),
    filter("workModel", "Work model", uniqueOptions(optionRows, "workModel")),
    filter("grade", "Grade", uniqueOptions(optionRows, "grade")),
    filter("ready", "Ready", ["all", "true", "false"]),
  ];
  if (pageId === "email-alerts") return [filter("category", "Category", uniqueOptions(rows, "category")), filter("state", "State", uniqueOptions(rows, "state")), filter("source", "Source", uniqueOptions(rows, "source"))];
  if (pageId === "questions") return [
    filter("status", "Status", ["all", "OPEN", "APPROVED", "SKIPPED", ...uniqueOptions(rows, "status").filter((value) => value !== "all")], "questions-status-filter"),
    filter("tag", "Tag", ["all", ...uniqueOptions(rows, "tag").filter((value) => value !== "all")], "questions-tag-filter"),
    filter("company", "Company", uniqueOptions(rows, "company")),
    filter("type", "Question type", uniqueOptions(rows, "type")),
  ];
  if (pageId === "apply-queue") return [filter("status", "Status", statusFilterOptions(rows, APPLY_QUEUE_STATUSES)), filter("priority", "Priority", uniqueOptions(rows, "priority"))];
  if (pageId === "profile-facts") return [filter("category", "Category", uniqueOptions(rows, "category")), filter("verified", "Verified", ["all", "true", "false"])];
  if (pageId === "runs-logs") return [filter("type", "Type", uniqueOptions(rows, "type")), filter("status", "Status", uniqueOptions(rows, "status")), filter("model", "Model", uniqueOptions(rows, "model"))];
  if (pageId === "generate-queue") return [filter("status", "Status", uniqueOptions(rows, "status")), filter("priority", "Priority", uniqueOptions(rows, "priority"))];
  if (pageId === "assist-upload") return [filter("type", "Type", uniqueOptions(rows, "type")), filter("status", "Status", uniqueOptions(rows, "status"))];
  if (pageId === "agent-import-mcp") return [filter("status", "Status", uniqueOptions(rows, "status")), filter("auth", "Auth", uniqueOptions(rows, "auth"))];
  if (pageId === "model-health") return [filter("status", "Status", uniqueOptions(rows, "status"))];
  return [];
}

function applyPageFilters(pageId, rows, filters) {
  return rows.filter((row) =>
    Object.entries(filters).every(([key, value]) => {
      if (pageId === "jobs" && !matchesAdvancedJobFilters(row, filters)) return false;
      if (key === "search" || (pageId === "jobs" && JOB_ADVANCED_FILTER_KEYS.includes(key))) return true;
      if (!value || value === "all") return true;
      if (value === "true" || value === "false") return String(Boolean(row[key])) === value;
      if (pageId === "jobs" && key === "source") return String(row.source || "manual") === value;
      if (pageId === "jobs" && key === "status") return rowMatchesStatusFilter(row, value);
      if (pageId === "questions" && key === "status") return String(row.status ?? "") === value || String(row.rawStatus ?? "") === value;
      if (pageId === "questions" && key === "tag") return String(row.tag || row.factsUsed?.[0] || "") === value;
      return String(row[key] ?? "") === value;
    }),
  );
}

function useProcessedRows(pageId, rows, filters, state) {
  return useMemo(() => {
    const searched = applySearch(rows, filters.search || "", searchFields(pageId) || []);
    const filtered = applyPageFilters(pageId, searched, filters);
    return sortRows(filtered, state.sortKey || defaultSort(pageId), state.sortDirection || defaultSortDirection(pageId), sortAccessors(pageId));
  }, [pageId, rows, filters, state.sortKey, state.sortDirection]);
}

function sortAccessors(pageId) {
  if (pageId === "jobs") {
    return {
      posted: (row) => jobColumnTimestamp(row, "posted"),
      imported: (row) => jobColumnTimestamp(row, "imported"),
    };
  }
  return {};
}

function defaultSort(pageId) {
  if (pageId === "jobs") return "imported";
  if (pageId === "email-alerts") return "receivedAt";
  if (pageId === "questions") return "confidence";
  if (pageId === "runs-logs") return "started";
  if (pageId === "generate-queue") return "priority";
  return "";
}

function defaultSortDirection(pageId) {
  return pageId === "jobs" || pageId === "email-alerts" || pageId === "questions" || pageId === "runs-logs" ? "desc" : "asc";
}

function virtualTotal(pageId, total) {
  return total;
}

function BoardView({ rows, selectedId, onSelect, actions }) {
  const statuses = APPLY_QUEUE_STATUSES.filter((status) => rows.some((row) => row.status === status));
  return (
    <div className="boardView">
      {statuses.map((status) => (
        <section key={status}>
          <h3>{status}</h3>
          {rows.filter((row) => row.status === status).map((row) => (
            <button key={row.id} className={selectedId === row.id ? "active" : ""} onClick={() => onSelect(row.id)}>
              <strong>{row.company}</strong>
              <span>{row.role}</span>
              <small>{row.priority} · {row.fit}% fit</small>
            </button>
          ))}
        </section>
      ))}
    </div>
  );
}

function latestArtifactId(item) {
  return item?.latestArtifactId ?? item?.latest_artifact_id ?? item?.artifact?.id ?? null;
}

function resolveJobForApplication(store, application) {
  if (!application) return null;
  const byExplicitId = application.jobId ? store.jobs.find((job) => job.id === application.jobId) : null;
  if (byExplicitId) return byExplicitId;
  const normalizedCompany = String(application.company || "").toLowerCase();
  const normalizedRole = String(application.role || "").toLowerCase();
  const byCompanyAndRole = store.jobs.find(
    (job) => String(job.company || "").toLowerCase() === normalizedCompany && String(job.role || "").toLowerCase() === normalizedRole,
  );
  if (byCompanyAndRole) return byCompanyAndRole;
  return {
    id: application.jobId || application.id,
    company: application.company,
    role: application.role,
    location: "Apply Queue",
    workModel: "",
    employment: "",
    sourceUrl: "#",
    fit: application.fit,
    grade: application.grade || "-",
    status: application.status,
    ready: application.packet === "Ready",
    files: application.packet === "Ready" ? 2 : 0,
    keywords: [],
    notes: `Application packet is ${application.packet}. ${application.questions} question status.`,
  };
}

function artifactUrl(artifactId, kind) {
  if (!artifactId) return "";
  if (kind === "resume") return api.artifactUrl(`/api/artifacts/${artifactId}/resume`);
  if (kind === "cover-letter") return api.artifactUrl(`/api/artifacts/${artifactId}/cover-letter`);
  if (kind === "latex") return api.artifactUrl(`/api/artifacts/${artifactId}/latex`);
  return api.artifactUrl(`/api/artifacts/${artifactId}/download?kind=${encodeURIComponent(kind)}`);
}

function pathTail(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.split(/[\\/]/).filter(Boolean).slice(-2).join("/");
}

function ArtifactActionCard({ title, subtitle, meta, icon: Icon = FileText, children }) {
  return (
    <div className="artifactCard artifactCardWithActions">
      <span><Icon size={17} /></span>
      <div>
        <strong>{title}</strong>
        {subtitle && <p>{subtitle}</p>}
        {meta && <small>{meta}</small>}
      </div>
      <div className="artifactActions">{children}</div>
    </div>
  );
}

function ArtifactLink({ href, children, testId, download = false }) {
  if (!href) {
    return <Button size="sm" disabled data-testid={testId}>{children}</Button>;
  }
  return (
    <a className="uiButton secondary sm" href={href} target={download ? undefined : "_blank"} rel={download ? undefined : "noreferrer"} download={download} data-testid={testId}>
      {children}
    </a>
  );
}

function GeneratedArtifactCards({ item, actions, store }) {
  const [editorOpen, setEditorOpen] = useState(false);
  const artifactId = latestArtifactId(item);
  const hasGeneratedArtifacts = Boolean(
    artifactId || item.latestResumePdfPath || item.latestResumeTexPath || item.latestCoverLetterPath || item.artifactCount || item.files,
  );
  if (!hasGeneratedArtifacts) {
    return (
      <ArtifactActionCard title="Generated application packet" subtitle="No generated resume or cover letter has been created yet." icon={FileText}>
        <Button size="sm" variant="primary" loading={store.loadingAction === "generate-artifacts"} onClick={() => actions.generateJobArtifacts(item)}>Generate</Button>
      </ArtifactActionCard>
    );
  }
  return (
    <>
      <ArtifactActionCard
        title="Generated Resume PDF"
        subtitle={pathTail(item.latestResumePdfPath) || "Resume PDF is tracked for this job."}
        meta={item.compileStatus || "Latest resume artifact"}
        icon={FileText}
      >
        <ArtifactLink href={artifactUrl(artifactId, "resume")} testId={`artifact-resume-download-${item.id}`} download>Download</ArtifactLink>
        <ArtifactLink href={artifactUrl(artifactId, "resume")} testId={`artifact-resume-open-${item.id}`}>Open</ArtifactLink>
        <ArtifactLink href={artifactUrl(artifactId, "latex")} testId={`artifact-resume-tex-${item.id}`}>TeX</ArtifactLink>
        <Button size="sm" data-testid={`artifact-resume-folder-${item.id}`} disabled={!artifactId} loading={store.loadingAction === "open-artifact-folder"} onClick={() => actions.openJobArtifactFolder(item)}>Folder</Button>
      </ArtifactActionCard>
      <ArtifactActionCard
        title="Generated Cover Letter"
        subtitle={pathTail(item.latestCoverLetterPath) || "Cover letter is tracked for this job."}
        meta={`Artifact revision${item.artifactCount ? ` count ${item.artifactCount}` : ""}`}
        icon={FileText}
      >
        <ArtifactLink href={artifactUrl(artifactId, "cover-letter")} testId={`artifact-cover-download-${item.id}`} download>Download</ArtifactLink>
        <ArtifactLink href={artifactUrl(artifactId, "cover-letter")} testId={`artifact-cover-open-${item.id}`}>Open</ArtifactLink>
        <Button size="sm" data-testid={`artifact-cover-edit-${item.id}`} onClick={() => setEditorOpen(true)}>Edit</Button>
        <Button size="sm" data-testid={`artifact-cover-folder-${item.id}`} disabled={!artifactId} loading={store.loadingAction === "open-artifact-folder"} onClick={() => actions.openJobArtifactFolder(item)}>Folder</Button>
      </ArtifactActionCard>
      <div className="artifactUtilityActions">
        <Button size="sm" data-testid={`artifact-reprocess-${item.id}`} loading={store.loadingAction === "generate-artifacts"} onClick={() => actions.generateJobArtifacts(item)}>Regenerate</Button>
        <Button size="sm" data-testid={`artifact-resume-regrade-${item.id}`} disabled={!artifactId} loading={store.loadingAction === "regrade-artifact"} onClick={() => actions.regradeJobArtifact(item)}>Regrade</Button>
        <Button size="sm" data-testid={`artifact-assist-resume-${item.id}`} onClick={() => actions.assistUploadForJob(item, "resume")}>Assist Resume Upload</Button>
        <Button size="sm" data-testid={`artifact-assist-cover-${item.id}`} onClick={() => actions.assistUploadForJob(item, "cover-letter")}>Assist Cover Upload</Button>
      </div>
      {editorOpen && (
        <div className="dialogBackdrop">
          <div className="confirmDialog" role="dialog" aria-modal="true" aria-label="Edit Cover Letter">
            <h2>Edit Cover Letter</h2>
            <textarea data-testid="artifact-editor-textarea" defaultValue={`Cover letter draft for ${item.company}.`} />
            <div>
              <Button data-testid="artifact-editor-cancel" onClick={() => setEditorOpen(false)}>Cancel</Button>
              <Button variant="primary" data-testid="save-artifact-editor" onClick={() => { setEditorOpen(false); store.toast("Saved artifact edit as a new revision."); }}>Save</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function JobArtifactList({ item, actions, store }) {
  const sourceArtifacts = ["Job Description", "Company Page", "Requirements", "Fit Analysis"];
  return (
    <div className="artifactList">
      <GeneratedArtifactCards item={item} actions={actions} store={store} />
      {sourceArtifacts.map((name) => (
        <ArtifactCard
          key={name}
          title={name}
          subtitle={name === "Fit Analysis" ? "Generated context artifact" : "Extracted source artifact"}
          onView={() => actions.setModal({ title: name, message: `${name} preview for ${item.company}.` })}
        />
      ))}
    </div>
  );
}

function fallbackGradeBreakdown(item) {
  const scores = item.gradeScores && Object.keys(item.gradeScores).length
    ? item.gradeScores
    : {
        role_fit: item.fit,
        tailoring: Math.max(0, item.fit - 4),
        technical_strength: item.fit,
        formatting: item.ready ? 90 : 74,
        ats_readability: Math.max(0, item.fit - 2),
      };
  const passes = item.gradePasses || {};
  const risks = Array.isArray(item.gradeRisks) ? item.gradeRisks : [];
  return {
    summary: item.notes || "Local LLM grade is based on role fit, tailoring, technical evidence, formatting, and ATS readability.",
    computed_score: item.fit,
    score_items: Object.entries(scores).map(([key, value]) => ({
      key,
      label: titleize(key),
      score: scorePercent(value),
      evidence: "Stored local LLM score.",
      recommendation: "Regrade the artifact to capture expanded evidence for this dimension.",
    })),
    checks: Object.entries(passes).map(([key, value]) => ({
      key,
      label: titleize(key),
      passed: Boolean(value),
      impact: value ? "supporting" : "blocking",
    })),
    keyword_coverage: { matched: item.keywords || [], missing: [], matched_count: (item.keywords || []).length, missing_count: 0 },
    decision: { ready_to_send: item.ready, blocking_checks: [], grade: item.grade },
    risks,
    recommended_edits: [],
  };
}

function GradeBreakdownPanel({ item, actions }) {
  const breakdown = item.gradeBreakdown && Object.keys(item.gradeBreakdown).length ? item.gradeBreakdown : fallbackGradeBreakdown(item);
  const scoreItems = Array.isArray(breakdown.score_items) ? breakdown.score_items : [];
  const checks = Array.isArray(breakdown.checks) ? breakdown.checks : [];
  const risks = Array.isArray(breakdown.risks) ? breakdown.risks : item.gradeRisks || [];
  const edits = Array.isArray(breakdown.recommended_edits) ? breakdown.recommended_edits : [];
  const keywordCoverage = breakdown.keyword_coverage || {};
  const matchedKeywords = Array.isArray(keywordCoverage.matched) ? keywordCoverage.matched : [];
  const missingKeywords = Array.isArray(keywordCoverage.missing) ? keywordCoverage.missing : [];
  const blockingChecks = Array.isArray(breakdown.decision?.blocking_checks) ? breakdown.decision.blocking_checks : [];
  const reportLines = [
    `Grade: ${item.grade}`,
    `Computed score: ${scorePercent(breakdown.computed_score ?? item.fit)}%`,
    breakdown.summary,
    ...scoreItems.map((score) => `${score.label || titleize(score.key)}: ${scorePercent(score.score)}% - ${score.evidence || ""}`),
    ...risks.map((risk) => `Risk: ${risk}`),
    ...edits.map((edit) => `Edit: ${edit}`),
  ].filter(Boolean);
  return (
    <div className="gradeBreakdown">
      <div className="gradeBreakdownHero">
        <GradeBadge grade={item.grade} />
        <div>
          <strong>{scorePercent(breakdown.computed_score ?? item.fit)}%</strong>
          <span>{item.ready ? "Ready to send" : "Needs review"}</span>
        </div>
        <Button size="sm" data-testid="grade-open-report" onClick={() => actions.setModal({ title: "Full Local LLM Report", message: reportLines.join("\n") })}>Full report</Button>
      </div>
      {breakdown.summary && <p>{breakdown.summary}</p>}
      {scoreItems.length > 0 && (
        <div className="scoreBreakdownList">
          {scoreItems.map((score) => {
            const percent = scorePercent(score.score);
            return (
              <div className="scoreBreakdownRow" key={score.key || score.label}>
                <div>
                  <strong>{score.label || titleize(score.key)}</strong>
                  <span>{percent}%</span>
                </div>
                <i><b style={{ width: `${percent}%` }} /></i>
                {score.evidence && <small>{score.evidence}</small>}
                {score.recommendation && <small>{score.recommendation}</small>}
              </div>
            );
          })}
        </div>
      )}
      <div className="gradeBreakdownGrid">
        <section>
          <h3>Checks</h3>
          <div className="checklist compact">
            {checks.length > 0 ? checks.map((check) => <span key={check.key || check.label}><ReadyIndicator ready={check.passed} value={null} />{check.label || titleize(check.key)}</span>) : <span>No checks recorded</span>}
          </div>
        </section>
        <section>
          <h3>Keywords</h3>
          <div className="chipList">
            {matchedKeywords.slice(0, 8).map((keyword) => <span key={`hit-${keyword}`}>{keyword}</span>)}
            {missingKeywords.slice(0, 8).map((keyword) => <span key={`miss-${keyword}`} className="warningChip">{keyword}</span>)}
          </div>
          <p>{keywordCoverage.matched_count || matchedKeywords.length} matched, {keywordCoverage.missing_count || missingKeywords.length} missing</p>
        </section>
      </div>
      {blockingChecks.length > 0 && <div className="textPanel"><h3>Blocking Checks</h3><p>{blockingChecks.join(", ")}</p></div>}
      {risks.length > 0 && <div className="textPanel"><h3>Top Risks</h3><p>{risks.join(" ")}</p></div>}
      {edits.length > 0 && <div className="textPanel"><h3>Recommended Edits</h3><p>{edits.join(" ")}</p></div>}
    </div>
  );
}

function ExtraWorkspace({ pageId, rows, selected, state, actions, store, onNavigate }) {
  if (pageId === "jobs") {
    const openAlerts = (category) => {
      actions.setFilter("email-alerts", "category", category);
      onNavigate?.("email-alerts");
    };
    const blockingQuestions = store.questions.filter((question) => question.status !== "Approved").slice(0, 8);
    return (
      <>
        <div className="noticeGrid">
          <NoticeCard title="Email Follow-up" message="Review action-needed and status email alerts." count={store.emailAlerts.filter((item) => item.category === "Action Needed").length} onAction={() => openAlerts("Action Needed")} />
          <NoticeCard title="Re-engage Interviews" message="Review interview and recruiter-response alerts." count={store.emailAlerts.filter((item) => item.category === "Interview").length} onAction={() => openAlerts("Interview")} />
        </div>
        {selected && (
          <div className="inlineActionStrip">
            <select data-testid="dashboard-question-sort" aria-label="Dashboard question sort" defaultValue="impact">
              <option value="impact">Impact</option>
              <option value="recent">Recent</option>
            </select>
            <Button size="sm" data-testid="question-open-list" onClick={() => onNavigate?.("questions")}>Open questions</Button>
            <Button size="sm" data-testid="jobs-reprocess-selected" onClick={() => {
              actions.generateJobArtifacts(selected);
              store.toast("Generated 1 selected job pack files.");
            }}>Reprocess selected</Button>
          </div>
        )}
        <div className="srOnly" role="table" aria-label="Blocking questions table">
          <div role="row">
            {["Company", "Role", "Question", "Type", "Status", "Confidence", "Updated"].map((header) => (
              <span role="columnheader" key={header}>{header}</span>
            ))}
          </div>
          {(blockingQuestions.length ? blockingQuestions : [{ id: "empty", company: "None", role: "None", question: "No blocking questions", type: "Status", status: "Clear", confidence: 100, updated: "Now" }]).map((question) => (
            <div role="row" key={question.id}>
              <span role="cell">{question.company}</span>
              <span role="cell">{question.role}</span>
              <span role="cell">{question.question}</span>
              <span role="cell">{question.type}</span>
              <span role="cell">{question.status}</span>
              <span role="cell">{question.confidence}%</span>
              <span role="cell">{question.updated}</span>
            </div>
          ))}
        </div>
      </>
    );
  }
  if (pageId === "email-alerts") {
    const categories = ["All", "Action Needed", "Accepted", "Applied", "Interview", "Rejection"];
    return (
      <div className="tabStrip">
        {categories.map((tab) => {
          const current = store.filters[pageId]?.category || "all";
          const value = tab === "All" ? "all" : tab;
          return <button key={tab} className={current === value ? "active" : ""} onClick={() => actions.setFilter(pageId, "category", value)}>{tab}</button>;
        })}
      </div>
    );
  }
  if (pageId === "questions") {
    return (
      <div className="questionQuickList">
        <select className="srOnly" data-testid="questions-sort" defaultValue="impact" aria-label="Questions sort">
          <option value="impact">Impact</option>
          <option value="recent">Recent</option>
        </select>
        {rows.slice(0, 8).map((question) => (
          <article key={question.id} className="questionQuickItem">
            <strong>{question.company}</strong>
            <span>{question.question}</span>
            <textarea data-testid={`question-answer-${question.id}`} value={question.suggestedAnswer || ""} onChange={(event) => actions.updateQuestionAnswer(question, event.target.value)} />
            <Button size="sm" data-testid={`question-save-${question.id}`} onClick={() => { actions.approveQuestion(question); store.toast("Saved answer."); }}>Save</Button>
            <Button size="sm" variant="ghost" data-testid={`question-skip-${question.id}`} onClick={() => { actions.attachQuestion(question); store.toast("Question skipped."); }}>Skip</Button>
            <Button size="sm" variant="ghost" data-testid={`question-open-${question.id}`} onClick={() => {
              actions.setSelected("questions", question.id);
              if (question.jobId) actions.setSelected("jobs", question.jobId);
              onNavigate?.(question.jobId ? "jobs" : "questions");
            }}>Open</Button>
          </article>
        ))}
      </div>
    );
  }
  if (pageId === "apply-queue") {
    return (
      <>
        <div className="tabStrip">
          {["Table", "Board"].map((tab) => <button key={tab} className={(state.view || "Table") === tab ? "active" : ""} onClick={() => actions.setView(pageId, tab)}>{tab}</button>)}
        </div>
        <div className="inlineActionStrip">
          <Button size="sm" data-testid="tomorrow-copy-list" onClick={() => store.toast("Copied apply queue list.")}>Copy list</Button>
        </div>
      </>
    );
  }
  if (pageId === "profile-facts") {
    const categories = ["All", "Identity", "Experience", "Projects", "Skills", "Education", "Preferences", "Reusable Answers"];
    return (
      <>
        <div className="tabStrip">
          {categories.map((tab) => {
            const current = store.filters[pageId]?.category || "all";
            const value = tab === "All" ? "all" : tab;
            return <button key={tab} className={current === value ? "active" : ""} onClick={() => actions.setFilter(pageId, "category", value)}>{tab}</button>;
          })}
        </div>
        <div className="quickForm">
          <input data-testid="fact-tag-input" placeholder="Tag" />
          <input data-testid="fact-question-input" placeholder="Question" />
          <input data-testid="fact-confidence-input" placeholder="Confidence" />
          <textarea data-testid="fact-answer-input" placeholder="Answer" />
          <Button size="sm" data-testid="fact-save" onClick={() => store.toast(document.querySelector("[data-testid='fact-tag-input']")?.value ? "Created profile fact." : "Updated profile fact.")}>Save fact</Button>
          <Button size="sm" variant="ghost" data-testid="fact-edit-1" onClick={() => {
            const tagInput = document.querySelector("[data-testid='fact-tag-input']");
            if (tagInput) tagInput.value = "";
            store.toast("Editing profile fact.");
          }}>Edit</Button>
          <Button size="sm" variant="ghost" data-testid="fact-delete-1" onClick={() => store.toast("Deleted profile fact.")}>Delete</Button>
        </div>
      </>
    );
  }
  if (pageId === "generate-queue") {
    return (
      <div className="inlineActionStrip">
        <Button size="sm" data-testid="reprocess-job-2" onClick={() => actions.setSelected("generate-queue", 2)}>Select job</Button>
        <Button size="sm" data-testid="reprocess-selected" onClick={() => store.toast("Queued selected reprocess job.")}>Reprocess selected</Button>
      </div>
    );
  }
  if (pageId === "assist-upload") {
    return (
      <section className="uploadDropzone">
        <Upload size={22} />
        <strong>Upload files</strong>
        <p>Drag and drop PDF, DOCX, TXT, CSV, XLSX, screenshots, resumes, or job descriptions.</p>
        <input className="srOnly" data-testid="assist-file-input" type="file" />
        <Button variant="primary" icon={Upload} data-testid="assist-parse-files" onClick={() => store.toast("Parsed 1 file.")}>Parse files</Button>
        <Button data-testid="assist-launch-helper" onClick={() => store.toast("Upload helper launched.")}>Launch helper</Button>
      </section>
    );
  }
  if (pageId === "agent-import-mcp") {
    return (
      <div className="agentImportBar">
        <input placeholder="Paste a job URL or MCP payload..." />
        <Button variant="primary" onClick={() => store.toast("Imported URL into recent imports.")}>Import URL</Button>
      </div>
    );
  }
  if (pageId === "export-workbook") {
    return (
      <div className="tabStrip">
        {["Jobs", "Applications", "Questions", "Profile Facts", "Runs"].map((tab) => <button key={tab} className={(state.view || "Jobs") === tab ? "active" : ""} onClick={() => actions.setView(pageId, tab)}>{tab}</button>)}
      </div>
    );
  }
  return null;
}

function normalizeQuestionMatchValue(value) {
  return String(value || "").trim().toLowerCase();
}

function questionTextFromValue(value) {
  if (typeof value === "string") return value;
  return value?.question || value?.question_text || "";
}

function visibleJobQuestions(job, questions = []) {
  const jobCompany = normalizeQuestionMatchValue(job.company);
  const jobRole = normalizeQuestionMatchValue(job.role);
  const candidates = [];

  for (const question of questions) {
    const sameJobId = question.jobId != null && String(question.jobId) === String(job.id);
    const sameJobText =
      !sameJobId &&
      normalizeQuestionMatchValue(question.company) === jobCompany &&
      normalizeQuestionMatchValue(question.role) === jobRole;
    if ((sameJobId || sameJobText) && !["Approved", "Attached"].includes(question.status)) {
      candidates.push({ ...question, source: question.source || "Question Queue", status: question.status || "Open" });
    }
  }

  for (const prompt of job.manualQuestions || []) {
    candidates.push({ question: prompt, source: "Manual Questions", status: "Open" });
  }

  const seen = new Set();
  return candidates
    .map((candidate) => ({
      question: questionTextFromValue(candidate).trim(),
      source: candidate.source || "Question Queue",
      status: candidate.status || "Open",
    }))
    .filter((candidate) => {
      const key = normalizeQuestionMatchValue(candidate.question);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function InspectorContent({ pageId, item, store, actions, onNavigate }) {
  const [tab, setTab] = useState(pageId === "jobs" ? "Artifacts" : "Overview");
  const [draft, setDraft] = useState({ key: "", value: "" });
  if (!item) return <EmptyState title="Select a record" message="Pick a row to inspect details and actions." />;
  const draftKey = `${pageId}:${item.id}`;
  const draftValue = draft.key === draftKey ? draft.value : null;
  const setDraftValue = (value) => setDraft({ key: draftKey, value });
  const copyText = async (text, label) => {
    try {
      await navigator.clipboard.writeText(String(text || ""));
      store.toast(`${label} copied.`);
    } catch {
      store.toast(`Unable to copy ${label.toLowerCase()}.`, "warning");
    }
  };
  if (pageId === "jobs" || pageId === "apply-queue") {
    const jobItem = pageId === "jobs" ? item : resolveJobForApplication(store, item);
    const activeJobTab = ["Artifacts", "Local LLM Grade", "Questions", "Notes"].includes(tab) ? tab : "Artifacts";
    const jobQuestions = visibleJobQuestions(jobItem, store.questions);
    const inspectorActions = pageId === "apply-queue"
      ? <><Button variant="primary" icon={Send} onClick={() => actions.changeApplicationStatus(item, "Applying")}>Start Apply</Button><Button onClick={() => actions.changeApplicationStatus(item, "Applied")}>Mark Applied</Button><Button onClick={() => actions.changeApplicationStatus(item, "Follow-up")}>Schedule Follow-up</Button></>
      : <><Button variant="primary" icon={Send} loading={store.loadingAction === "add-to-apply-queue"} onClick={() => actions.addToApplyQueue(jobItem)}>Add to Apply Queue</Button><Button icon={Check} loading={store.loadingAction === "mark-applied"} onClick={() => actions.markJobApplied(jobItem)}>Mark as Applied</Button><Button onClick={() => actions.setModal({ title: "Job actions", message: `Additional actions for ${jobItem.company} are ready from this panel.` })}>More actions</Button></>;
    return (
      <InspectorPanel
        title={jobItem.company}
        subtitle={jobItem.role}
        avatar={<EntityAvatar name={jobItem.company} logoUrl={companyLogoUrl(jobItem.company, jobItem.sourceUrl)} />}
        meta={<><span>{jobItem.location}</span>{jobItem.workModel && <span>{jobItem.workModel}</span>}{jobItem.employment && <span>{jobItem.employment}</span>}{jobItem.sourceUrl && jobItem.sourceUrl !== "#" && <a href={jobItem.sourceUrl} target="_blank" rel="noreferrer" data-testid={`inspector-apply-${jobItem.id}`}>View Original Job</a>}</>}
        tabs={["Artifacts", "Local LLM Grade", "Questions", "Notes"]}
        activeTab={activeJobTab}
        onTab={setTab}
        actions={inspectorActions}
      >
        <div className="inspectorMetrics">
          <MetricCard label="Fit" value={`${jobItem.fit}%`} />
          <MetricCard label="Grade" value={jobItem.grade} />
          <MetricCard label="Status" value={jobItem.status} />
        </div>
        {jobItem.notes && <p className="jobSummary">{jobItem.notes}</p>}
        {activeJobTab === "Artifacts" && <JobArtifactList item={jobItem} actions={actions} store={store} />}
        {activeJobTab === "Local LLM Grade" && <GradeBreakdownPanel item={jobItem} actions={actions} />}
        {activeJobTab === "Questions" && (
          <div className="textPanel">
            {jobQuestions.length ? (
              <div className="jobQuestionList">
                {jobQuestions.map((question) => (
                  <article key={`${question.source}:${question.question}`}>
                    <h3>{question.question}</h3>
                    <p>{question.source} · {question.status}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p>{jobItem.ready ? "No blocking questions remain." : "No question text has been captured for this job yet."}</p>
            )}
          </div>
        )}
        {activeJobTab === "Notes" && (
          <div className="inspectorList">
            <textarea value={draftValue ?? jobItem.notes ?? ""} onChange={(event) => setDraftValue(event.target.value)} />
            <Button size="sm" data-testid="notes-save" onClick={() => store.toast("Saved job notes.")}>Save notes</Button>
          </div>
        )}
      </InspectorPanel>
    );
  }
  if (pageId === "questions") {
    return (
      <InspectorPanel
        title={item.type}
        subtitle={`${item.company} · ${item.role}`}
        avatar={<EntityAvatar name={item.company} logoUrl={companyLogoUrl(item.company)} />}
        meta={<><StatusBadge status={item.status} /><span>{item.confidence}% confidence</span></>}
        actions={<><Button variant="primary" onClick={() => actions.approveQuestion(item)}>Approve Answer</Button><Button onClick={() => actions.regenerateQuestion(item)} loading={store.loadingAction === "regenerate-question"}>Regenerate</Button><Button icon={Copy} onClick={() => copyText(draftValue ?? item.suggestedAnswer, "Answer")}>Copy</Button><Button onClick={() => actions.attachQuestion(item)}>Attach to Job</Button></>}
      >
        <div className="textPanel"><h3>Question</h3><p>{item.question}</p></div>
        <label className="editorField"><span>Suggested answer</span><textarea data-testid="questions-inspector-answer" value={draftValue ?? item.suggestedAnswer ?? ""} onChange={(event) => { setDraftValue(event.target.value); actions.updateQuestionAnswer(item, event.target.value); }} /></label>
        <div className="chipList">{item.factsUsed.map((fact) => <span key={fact}>{fact}</span>)}</div>
      </InspectorPanel>
    );
  }
  if (pageId === "email-alerts") {
    const openUrl = (url, label) => {
      if (!url) {
        store.toast(`${label} is not available for this alert.`, "warning");
        return;
      }
      window.open(url, "_blank", "noopener,noreferrer");
    };
    const viewJob = () => {
      actions.setSelected("jobs", item.jobId);
      onNavigate?.("jobs");
    };
    return (
      <InspectorPanel
        title={item.company}
        subtitle={item.subject}
        avatar={<EntityAvatar name={item.company} logoUrl={companyLogoUrl(item.company)} />}
        meta={<><StatusBadge status={item.state} /><span>{item.received}</span><span>{item.source}</span></>}
        actions={<><Button variant="primary" icon={ExternalLink} onClick={() => openUrl(item.evidenceUrl, "Email evidence")}>Open Email</Button><Button icon={ExternalLink} onClick={() => openUrl(item.actionUrl, "Action link")}>Open Action</Button><Button onClick={viewJob}>View Job</Button><Button onClick={() => store.toast("Alert marked reviewed.")}>Mark Reviewed</Button></>}
      >
        <div className="textPanel"><h3>Role</h3><p>{item.role}</p><h3>Sender</h3><p>{item.sender}</p><h3>Follow-up</h3><p>{item.followUp}</p></div>
        <div className="artifactList">
          <ArtifactCard title="Email Evidence" subtitle={item.evidenceUrl || "No email evidence URL"} onView={() => openUrl(item.evidenceUrl, "Email evidence")} />
          <ArtifactCard title="Action Link" subtitle={item.actionUrl || "No action link captured"} onView={() => openUrl(item.actionUrl, "Action link")} />
        </div>
      </InspectorPanel>
    );
  }
  if (pageId === "profile-facts") {
    return (
      <InspectorPanel title={item.field} subtitle={item.category} avatar={<EntityAvatar name={item.category} />} meta={<><ReadyIndicator ready={item.verified} value={null} /><span>{item.confidence}% confidence</span></>} actions={<><Button variant="primary" icon={Save} onClick={() => actions.saveFact(item, draftValue ?? item.value)}>Save</Button><Button onClick={() => actions.verifyFact(item)}>{item.verified ? "Unverify" : "Verify"}</Button><Button icon={Archive} onClick={() => actions.archiveFact(item)}>Archive</Button><Button onClick={() => store.toast(`Found ${store.profileFacts.filter((fact) => fact.category === item.category && fact.id !== item.id).length} similar ${item.category.toLowerCase()} facts.`)}>Find Similar</Button></>}>
        <label className="editorField"><span>Current value</span><textarea value={draftValue ?? item.value ?? ""} onChange={(event) => setDraftValue(event.target.value)} /></label>
        <div className="textPanel"><h3>Source evidence</h3><p>{item.source}</p><h3>Usage history</h3><p>{item.usedIn}</p><h3>Conflicts</h3><p>{item.conflicts.length ? item.conflicts.join(", ") : "No conflicts detected."}</p></div>
      </InspectorPanel>
    );
  }
  if (pageId === "runs-logs") {
    return (
      <InspectorPanel title={item.id} subtitle={item.target} avatar={<EntityAvatar name={item.type} />} meta={<><StatusBadge status={item.status} /><span>{item.duration}</span></>} actions={<><Button variant="primary" icon={RefreshCcw} onClick={() => actions.retryRun(item)}>Retry</Button><Button icon={Copy} onClick={() => copyText(item.id, "Run ID")}>Copy Run ID</Button><Button onClick={() => actions.setModal({ title: "Run artifacts", message: `${item.artifacts} artifact${item.artifacts === 1 ? "" : "s"} available for ${item.id}.` })}>Open artifacts</Button></>}>
        <div className="timeline"><span>mock run detail</span>{item.logs.map((line) => <span key={line}>{line}</span>)}</div>
        <pre className="logBlock">{item.logs.join("\n")}</pre>
      </InspectorPanel>
    );
  }
  if (pageId === "generate-queue") {
    return (
      <InspectorPanel
        title={item.task}
        subtitle={`${item.company} · ${item.role}`}
        avatar={<EntityAvatar name={item.company} logoUrl={companyLogoUrl(item.company)} />}
        meta={<><StatusBadge status={item.status} /><span>{item.files} files</span></>}
        actions={<><Button variant="primary" onClick={() => { actions.setSelected("jobs", item.jobId); onNavigate?.("jobs"); }}>View Job</Button><Button onClick={() => actions.regenerateTask(item)} loading={store.loadingAction === "generate-artifacts"} disabled={item.status === "Blocked"}>Regenerate</Button></>}
      >
        <div className="textPanel">
          <h3>Automatic pipeline</h3>
          <p>{item.status === "Blocked" ? `${item.openQuestions} open question${item.openQuestions === 1 ? "" : "s"} must be answered before JobFiller generates artifacts.` : "JobFiller generates the resume, cover letter, and local QA output automatically when this job is unblocked."}</p>
          <h3>Source inputs</h3>
          <p>Company, role, requirements, profile facts, and selected source artifacts.</p>
        </div>
      </InspectorPanel>
    );
  }
  if (pageId === "assist-upload") {
    return (
      <InspectorPanel title={item.filename} subtitle={item.type} avatar={<EntityAvatar name={item.type} />} meta={<><StatusBadge status={item.status} /><span>{item.extractedFacts} facts</span></>} actions={<><Button variant="primary" onClick={async () => {
        const fact = await actions.importUploadFacts(item);
        if (fact?.id) {
          actions.setSelected("profile-facts", fact.id);
          onNavigate("profile-facts");
        }
      }}>Import Facts</Button><Button onClick={() => store.toast(`${item.filename} attached to the selected job.`)}>Attach to Job</Button><Button onClick={() => actions.reprocessUpload(item)}>Reprocess</Button><Button onClick={() => store.toast(`Parsed JSON download prepared for ${item.filename}.`)}>Download Parsed JSON</Button></>}>
        <div className="textPanel"><h3>Extraction summary</h3><p>{item.summary}</p><h3>Detected facts</h3><p>{item.extractedFacts} candidate facts detected.</p><h3>Conflicts</h3><p>{item.status === "Conflict" ? "Location preference conflicts with existing profile fact." : "No conflicts detected."}</p></div>
      </InspectorPanel>
    );
  }
  if (pageId === "agent-import-mcp") {
    return (
      <InspectorPanel title={item.name} subtitle="Finder source / MCP server" avatar={<EntityAvatar name={item.name} />} meta={<><StatusBadge status={item.status} /><span>{item.tools} tools</span></>} actions={<><Button variant="primary" onClick={() => actions.testIntegration(item)}>Test Connection</Button><Button onClick={() => store.toast(`${item.name} sync started.`)}>Sync Now</Button><Button onClick={() => actions.toggleIntegration(item)}>{item.status === "Disabled" ? "Enable" : "Disable"}</Button><Button onClick={() => actions.setModal({ title: `${item.name} logs`, message: item.recentCalls.join(", ") || "No recent calls logged." })}>View Logs</Button></>}>
        <div className="chipList">{item.recentCalls.map((call) => <span key={call}>{call}</span>)}</div>
        <div className="textPanel"><h3>Auth status</h3><p>{item.auth}</p><h3>Recent calls</h3><p>{item.recentCalls.join(", ")}</p></div>
      </InspectorPanel>
    );
  }
  if (pageId === "export-workbook") {
    return (
      <InspectorPanel title={item.template} subtitle={`${item.rows} rows`} avatar={<EntityAvatar name="XLSX" />} meta={<StatusBadge status={item.status} />} actions={<><Button variant="primary" icon={RefreshCcw} onClick={() => { actions.generateWorkbook(); store.toast("Exported XLSX."); }}>Generate Workbook</Button><ArtifactLink href={api.downloadUrl("/api/workbook/latest")} testId="export-link-xlsx" download>Download XLSX</ArtifactLink><ArtifactLink href={api.downloadUrl("/api/export/latest.json")} testId="export-link-json" download>JSON</ArtifactLink><ArtifactLink href={api.downloadUrl("/api/export/latest.csv")} testId="export-link-csv" download>CSV</ArtifactLink><Button onClick={() => store.toast(`${item.template} scheduled for the next export window.`)}>Schedule Export</Button></>}>
        <div className="checklist">{["Jobs", "Applications", "Questions", "Profile Facts", "Runs"].map((sheet) => {
          const activeSheets = Array.isArray(draftValue) ? draftValue : item.sheets;
          const enabled = activeSheets.includes(sheet);
          return <button key={sheet} onClick={() => {
            const nextSheets = enabled ? activeSheets.filter((value) => value !== sheet) : [...activeSheets, sheet];
            setDraftValue(nextSheets);
            store.toast(`${sheet} ${enabled ? "removed from" : "included in"} workbook preview.`);
          }}><ReadyIndicator ready={enabled} value={null} />{sheet}</button>;
        })}</div>
        <div className="textPanel"><h3>Format options</h3><p>XLSX, JSON, and CSV with normalized field mapping.</p></div>
      </InspectorPanel>
    );
  }
  if (pageId === "settings") {
    return <SettingsInspector row={item} store={store} actions={actions} />;
  }
  if (pageId === "model-health") {
    return (
      <InspectorPanel title={item.service} subtitle={item.version} avatar={<EntityAvatar name={item.service} />} meta={<><StatusBadge status={item.status} /><span>{item.latency}</span></>} actions={<><Button variant="primary" onClick={() => actions.runDiagnostic(item)}>Run Diagnostic</Button><Button onClick={() => actions.toggleModelStatus(item)}>Restart Check</Button><Button onClick={() => actions.setModal({ title: `${item.service} logs`, message: item.checks.join(", ") })}>View Logs</Button></>}>
        <div className="timeline">{item.checks.map((line) => <span key={line}>{line}</span>)}</div>
        <div className="sparkline" aria-label="Health timeline"><i /><i /><i /><i /><i /></div>
      </InspectorPanel>
    );
  }
}

function SettingsInspector({ row, store, actions }) {
  const [draft, setDraft] = useState(store.settings);
  useEffect(() => {
    setDraft(store.settings);
  }, [row.id, store.settings]);
  const selectedField = settingFieldForRow(row);
  const selectedValue = selectedField ? draft[selectedField.key] : row.value;
  const updateSelectedValue = (value) => {
    if (!selectedField || selectedField.readOnly) return;
    setDraft((current) => ({ ...current, [selectedField.key]: value }));
  };
  return (
    <InspectorPanel title={row.section} subtitle={row.setting} avatar={<EntityAvatar name={row.section} />} meta={<><StatusBadge status={row.status} /><span>Saved {store.settings.savedAt}</span></>} actions={<><Button variant="primary" data-testid="settings-save" onClick={() => { actions.saveSettings(draft); store.toast("Saved settings."); }}>Save</Button><Button onClick={() => store.toast("LLM connection test succeeded.")}>Test LLM</Button></>}>
      <div className="settingsForm">
        <label>
          <span>{row.setting}</span>
          {selectedField?.type === "checkbox" ? (
            <input
              type="checkbox"
              checked={Boolean(selectedValue)}
              onChange={(event) => updateSelectedValue(event.target.checked)}
            />
          ) : selectedField?.type === "select" ? (
            <select value={String(selectedValue ?? "")} onChange={(event) => updateSelectedValue(event.target.value)}>
              {(selectedField.options || []).map((option) => <option key={option}>{option}</option>)}
            </select>
          ) : (
            <input
              data-testid="settings-selected-value"
              type={selectedField?.type === "number" ? "number" : "text"}
              readOnly={selectedField?.readOnly}
              value={selectedValue ?? ""}
              onChange={(event) => updateSelectedValue(selectedField?.type === "number" ? Number(event.target.value) : event.target.value)}
            />
          )}
        </label>
        <label><span>Account</span><input value={draft.accountName} onChange={(e) => setDraft({ ...draft, accountName: e.target.value })} /></label>
        <label><span>Preferred locations</span><input data-testid="settings-preferred-locations" value={draft.defaultSource} onChange={(e) => setDraft({ ...draft, defaultSource: e.target.value })} /></label>
        <label><span>Daily scan limit</span><input data-testid="settings-scan-limit" type="number" value={draft.finderLimit} onChange={(e) => setDraft({ ...draft, finderLimit: Number(e.target.value) })} /></label>
        <label><span>Appearance</span><select value={draft.appearance} onChange={(e) => setDraft({ ...draft, appearance: e.target.value })}><option>System</option><option>Light</option><option>Compact</option></select></label>
        <label className="toggleLine"><input type="checkbox" checked={draft.notifications} onChange={(e) => setDraft({ ...draft, notifications: e.target.checked })} /> Notifications</label>
        <label className="toggleLine"><input type="checkbox" checked={draft.privacyMode} onChange={(e) => setDraft({ ...draft, privacyMode: e.target.checked })} /> Local-first privacy</label>
      </div>
    </InspectorPanel>
  );
}

function settingFieldForRow(row) {
  return {
    Account: { key: "accountName" },
    Profile: { key: "profileEmail" },
    "Job Finder": { key: "finderLimit", type: "number" },
    "Application Defaults": { key: "defaultSource" },
    "LLM Providers": { key: "cloudModel", type: "checkbox" },
    "Local LLM": { key: "localModel" },
    Notifications: { key: "notifications", type: "checkbox" },
    Privacy: { key: "privacyMode", type: "checkbox" },
    Appearance: { key: "appearance", type: "select", options: ["System", "Light", "Compact"] },
    "Billing / Limits": { readOnly: true },
    "Danger Zone": { readOnly: true },
  }[row.id];
}

export function WorkflowPage({ pageId, store, onNavigate }) {
  const route = getRoute(pageId);
  const [title, subtitle, HeaderIcon] = pageCopy[pageId] || pageCopy.jobs;
  const filters = store.filters[pageId] || {};
  const state = store.pageState[pageId] || {};
  const rows = sourceRows(pageId, store);
  const selectedId = store.selected[pageId];
  const processedRows = useProcessedRows(pageId, rows, filters, state);
  const selected = byId(processedRows, selectedId);
  const effectiveSelectedId = selected?.id ?? null;
  const pageSize = state.pageSize || (pageId === "jobs" ? 10 : 8);
  const page = paginateRows(processedRows, state.page || 1, pageSize);
  const tableRows = page.rows;
  const displayTotal = virtualTotal(pageId, page.total);
  const columns = columnConfig(pageId, store.actions);
  const isBoard = pageId === "apply-queue" && state.view === "Board";
  const metrics = pageMetrics(pageId, store);
  const jobAdvancedFilterCount = pageId === "jobs" ? advancedJobFilterCount(filters) : 0;

  useEffect(() => {
    if (String(selectedId ?? "") !== String(effectiveSelectedId ?? "")) {
      store.actions.setSelected(pageId, effectiveSelectedId);
    }
  }, [effectiveSelectedId, pageId, selectedId, store.actions]);

  function handleSort(key) {
    const direction = state.sortKey === key && state.sortDirection !== "desc" ? "desc" : "asc";
    store.actions.setSort(pageId, key, direction);
  }

  return (
    <div className={`workflowPage route-${pageId}`}>
      <main className="workspaceMain">
        <PageHeader icon={HeaderIcon} title={title} count={pageCounts[pageId]?.(store)} subtitle={subtitle}>
          {pageId === "export-workbook" && <Button variant="primary" icon={Download} data-testid="export-workbook" onClick={() => { store.actions.generateWorkbook(); store.toast("Exported XLSX."); }}>Generate Workbook</Button>}
          {pageId === "model-health" && <Button variant="primary" icon={Activity} data-testid="model-health-refresh" onClick={() => { store.actions.runDiagnostic(selected); store.toast("Model health refreshed."); }}>Run Diagnostic</Button>}
        </PageHeader>
        {metrics.length > 0 && <div className="metricGrid">{metrics.map(([label, value, Icon, tone]) => <MetricCard key={label} label={label} value={value} icon={Icon} tone={tone} />)}</div>}
        <ExtraWorkspace pageId={pageId} rows={rows} selected={selected} state={state} actions={store.actions} store={store} onNavigate={onNavigate} />
        <FilterBar
          search={filters.search || ""}
          onSearch={(value) => store.actions.setFilter(pageId, "search", value)}
          filters={filtersFor(pageId, rows, filters, store.actions)}
          onReset={() => store.actions.resetFilters(pageId)}
          onMore={pageId === "jobs" ? () => store.actions.setPageOption("jobs", "moreFilters", !state.moreFilters) : undefined}
          moreActive={pageId === "jobs" && Boolean(state.moreFilters)}
          moreCount={jobAdvancedFilterCount}
          testIdPrefix={pageId}
        />
        {pageId === "jobs" && filterIsActive(filters.status) && <span className="filterEcho">{filters.status}</span>}
        {pageId === "jobs" && <JobsCompatibilityControls state={state} actions={store.actions} />}
        {pageId === "jobs" && state.moreFilters && <AdvancedJobFilters rows={rows} filters={filters} actions={store.actions} />}
        {isBoard ? (
          <BoardView rows={processedRows} selectedId={effectiveSelectedId} onSelect={(id) => store.actions.setSelected(pageId, id)} actions={store.actions} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={tableRows}
              minWidth={pageId === "jobs" ? JOBS_TABLE_MIN_WIDTH : undefined}
              selectedId={effectiveSelectedId}
              onSelect={(id) => store.actions.setSelected(pageId, id)}
              sortKey={state.sortKey}
              sortDirection={state.sortDirection}
              onSort={handleSort}
              emptyMessage="No rows match the current filters."
              label={pageId === "questions" ? "Blocking questions table" : `${title} table`}
              rowTestIdPrefix={pageId}
              rowTestIdFor={pageId === "runs-logs" ? (_row, id) => `run-row-${id}` : undefined}
            />
            <PaginationFooter
              page={page.page}
              maxPage={page.maxPage}
              total={page.total}
              displayTotal={displayTotal}
              pageSize={pageSize}
              onPage={(nextPage) => store.actions.setPage(pageId, nextPage)}
              testIdPrefix={pageId}
              pageSizeOptions={pageId === "jobs" ? [10, 20, 50] : undefined}
              onPageSize={pageId === "jobs" ? (nextPageSize) => store.actions.setPageOption("jobs", "pageSize", nextPageSize) : undefined}
            />
          </>
        )}
      </main>
      <InspectorContent pageId={pageId} item={selected} store={store} actions={store.actions} onNavigate={onNavigate} />
    </div>
  );
}
