const truthyEnv = (value) => ["1", "true", "yes", "on"].includes(String(value || "").trim().toLowerCase());

const API_PORT_SCAN_ENABLED = truthyEnv(import.meta.env?.VITE_JOBFILLER_USE_API);

const DEFAULT_CANDIDATE_BASES = (() => {
  const envBase = typeof import.meta.env?.VITE_API_BASE === "string" ? import.meta.env.VITE_API_BASE.trim() : "";
  const windowBase =
    typeof window !== "undefined" && typeof window.__JOBFILLER_API_BASE === "string"
      ? window.__JOBFILLER_API_BASE.trim()
      : "";
  const queryBase = (() => {
    if (typeof window === "undefined") return "";
    const params = new URLSearchParams(window.location.search || "");
    return (params.get("api_base") || "").trim();
  })();
  const sameOriginBase =
    typeof window !== "undefined" && window.location?.origin
      ? `${window.location.origin}/api`
      : "";
  const host = typeof window !== "undefined" ? window.location.hostname : "127.0.0.1";
  const candidateHost = host && host !== "localhost" ? host : "127.0.0.1";
  const candidates = [];
  const normalizedEnvBase = envBase.replace(/\/$/, "");
  const normalizedWindowBase = windowBase.replace(/\/$/, "");
  const normalizedQueryBase = queryBase.replace(/\/$/, "");
  const normalizedSameOriginBase = sameOriginBase.replace(/\/$/, "");
  if (normalizedEnvBase.startsWith("http")) candidates.push(normalizedEnvBase);
  if (normalizedWindowBase.startsWith("http")) candidates.push(normalizedWindowBase);
  if (normalizedQueryBase.startsWith("http")) candidates.push(normalizedQueryBase);
  if (normalizedSameOriginBase.startsWith("http")) candidates.push(normalizedSameOriginBase);
  if (API_PORT_SCAN_ENABLED) {
    const fallbackPorts = Array.from({ length: 121 }, (_, i) => 8000 + i);
    for (const port of fallbackPorts) {
      candidates.push(`http://${candidateHost}:${port}/api`);
      if (candidateHost !== "127.0.0.1") {
        candidates.push(`http://127.0.0.1:${port}/api`);
      }
    }
  }

  const deduped = new Set();
  for (const candidate of candidates) {
    if (candidate) deduped.add(candidate);
  }
  return Array.from(deduped);
})();

let resolvedApiBase = null;
let resolvedApiBaseError = "";
let resolvingApiBasePromise = null;
let mutationToken = "";
let mutationTokenPromise = null;

function stripBase(base) {
  return base.endsWith("/") ? base.slice(0, -1) : base;
}

function apiRequestUrl(base, path) {
  const normalizedBase = stripBase(base);
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const sanitizedPath =
    normalizedBase.endsWith("/api") && normalizedPath.startsWith("/api") ? normalizedPath.slice(4) : normalizedPath;
  return `${normalizedBase}${sanitizedPath}`;
}

async function fetchJsonProbe(base, path, headers = {}) {
  const response = await fetch(apiRequestUrl(base, path), {
    headers: { "Content-Type": "application/json", ...headers },
  });
  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  const bodyText = (await response.clone().text()).trim();
  let payload = {};
  let isJson = contentType.includes("application/json");
  if (bodyText) {
    if (!isJson && (bodyText.startsWith("{") || bodyText.startsWith("["))) {
      isJson = true;
    }
    if (isJson) {
      payload = JSON.parse(bodyText);
    }
  }
  return { response, payload, isJson };
}

function isJsonObjectProbe(result) {
  return result.response.ok && result.isJson && typeof result.payload === "object" && result.payload !== null;
}

async function validateApiBase(candidate) {
  const health = await fetchJsonProbe(candidate, "/api/health");
  const session = await fetchJsonProbe(candidate, "/api/session");
  const token = isJsonObjectProbe(session) ? session.payload.mutation_token : "";
  if (!isJsonObjectProbe(health) || !isJsonObjectProbe(session) || !token) {
    const healthStatus = `${health.response.status} ${health.response.statusText}`.trim();
    const sessionStatus = `${session.response.status} ${session.response.statusText}`.trim();
    return {
      ok: false,
      reason: `health ${healthStatus || "non-JSON"} / session ${sessionStatus || "non-JSON"}`,
    };
  }
  const tokenHeaders = { "X-JobFiller-Token": String(token) };
  const [settings, modelHealth] = await Promise.all([
    fetchJsonProbe(candidate, "/api/settings", tokenHeaders),
    fetchJsonProbe(candidate, "/api/model-health", tokenHeaders),
  ]);
  if (isJsonObjectProbe(settings) && isJsonObjectProbe(modelHealth)) {
    mutationToken = String(token);
    return { ok: true };
  }
  const settingsStatus = `${settings.response.status} ${settings.response.statusText}`.trim();
  const modelHealthStatus = `${modelHealth.response.status} ${modelHealth.response.statusText}`.trim();
  return {
    ok: false,
    reason: `settings ${settingsStatus || "non-JSON"} / model-health ${modelHealthStatus || "non-JSON"}`,
  };
}

async function resolveApiBase() {
  if (resolvedApiBase) {
    return resolvedApiBase;
  }
  if (resolvingApiBasePromise) {
    return resolvingApiBasePromise;
  }
  resolvingApiBasePromise = resolveApiBaseInternal().finally(() => {
    resolvingApiBasePromise = null;
  });
  return resolvingApiBasePromise;
}

async function resolveApiBaseInternal() {
  const errors = [];
  for (const base of DEFAULT_CANDIDATE_BASES) {
    const candidate = stripBase(base);
    try {
      const validation = await validateApiBase(candidate);
      if (validation.ok) {
        resolvedApiBase = candidate;
        resolvedApiBaseError = "";
        return resolvedApiBase;
      }
      errors.push(`${candidate} -> ${validation.reason || "missing required API endpoints"}`);
    } catch (error) {
      errors.push(`${candidate} -> ${error?.message || "network error"}`);
    }
  }
  resolvedApiBaseError = errors.join(" | ");
  const preview = errors.slice(0, 4).join(" | ");
  throw new Error(
    `Unable to reach the JobFiller backend API. Start it with .\\Start-JobFiller.ps1, then retry. Checked ${errors.length} candidate base URL(s). ${preview}`,
  );
}

function isMutatingMethod(method) {
  return !["GET", "HEAD", "OPTIONS"].includes(String(method || "GET").toUpperCase());
}

function requestNeedsToken(path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return !normalizedPath.startsWith("/api/session") && !normalizedPath.startsWith("/api/health");
}

async function sessionToken() {
  if (mutationToken) {
    return mutationToken;
  }
  if (mutationTokenPromise) {
    return mutationTokenPromise;
  }
  mutationTokenPromise = (async () => {
    const base = await resolveApiBase();
    const result = await fetchJsonProbe(base, "/api/session");
    if (!isJsonObjectProbe(result) || !result.payload.mutation_token) {
      throw new Error("JobFiller backend did not return a local mutation token.");
    }
    mutationToken = String(result.payload.mutation_token);
    return mutationToken;
  })().finally(() => {
    mutationTokenPromise = null;
  });
  return mutationTokenPromise;
}

async function request(path, options = {}) {
  const method = options.method || "GET";
  const needsToken = requestNeedsToken(path) || isMutatingMethod(method);
  let response = null;
  let url = "";
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const base = await resolveApiBase();
    url = apiRequestUrl(base, path);
    const tokenHeaders = needsToken ? { "X-JobFiller-Token": await sessionToken() } : {};
    try {
      response = await fetch(url, {
        headers: { "Content-Type": "application/json", ...tokenHeaders, ...(options.headers || {}) },
        ...options,
      });
    } catch (error) {
      if (attempt === 0) {
        resolvedApiBase = null;
        mutationToken = "";
        continue;
      }
      throw error;
    }
    if (response.status === 403 && needsToken && attempt === 0) {
      mutationToken = "";
      continue;
    }
    break;
  }
  if (!response) {
    throw new Error(`Unable to reach the JobFiller backend API for ${path}.`);
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  if (!contentType.includes("application/json")) {
    const body = (await response.clone().text()).slice(0, 120);
    if (body.trim().startsWith("<!doctype")) {
      throw new Error(
        `Expected JSON from ${url} but received HTML. This usually means the API base is wrong. Tried base(s): ${resolvedApiBaseError || resolvedApiBase}`,
      );
    }
    throw new Error(`Expected JSON from ${url} but got ${contentType || "unknown"} response content.`);
  }
  try {
    return await response.json();
  } catch (error) {
    const body = (await response.clone().text()).slice(0, 120);
    throw new Error(`Invalid JSON from ${url}: ${(error && error.message) || "parse error"}; body preview: ${body}`);
  }
}

export const api = {
  artifactUrl: (path) => apiRequestUrl(resolvedApiBase || "/api", path),
  downloadUrl: (path) => apiRequestUrl(resolvedApiBase || "/api", path),
  jobs: (sort = "newest", remoteFirst = true) =>
    request(`/api/jobs?sort=${encodeURIComponent(sort)}&remote_first=${remoteFirst ? "true" : "false"}`),
  job: (id) => request(`/api/jobs/${id}`),
  jobArtifacts: (id) => request(`/api/jobs/${id}/artifacts`),
  jobQuestions: (id, status = "OPEN") => request(`/api/jobs/${id}/questions?status=${status}`),
  scan: (payload = {}) => request("/api/scans", { method: "POST", body: JSON.stringify(payload) }),
  importJob: (payload) => request("/api/jobs/import", { method: "POST", body: JSON.stringify(payload) }),
  patchJob: (id, payload) => request(`/api/jobs/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteJob: (id) => request(`/api/jobs/${id}`, { method: "DELETE" }),
  reprocess: (id) => request(`/api/jobs/${id}/reprocess`, { method: "POST" }),
  generateArtifacts: (id) => request(`/api/jobs/${id}/artifacts/generate`, { method: "POST" }),
  questions: (status = "OPEN", sort = "impact", tag = "all") => request(`/api/questions?status=${status}&sort=${sort}&tag=${encodeURIComponent(tag)}`),
  answer: (id, answer) => request(`/api/questions/${id}/answer`, { method: "POST", body: JSON.stringify({ answer }) }),
  skipQuestion: (id) => request(`/api/questions/${id}/skip`, { method: "POST" }),
  facts: () => request("/api/profile-facts"),
  createFact: (payload) => request("/api/profile-facts", { method: "POST", body: JSON.stringify(payload) }),
  updateFact: (id, payload) => request(`/api/profile-facts/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteFact: (id) => request(`/api/profile-facts/${id}`, { method: "DELETE" }),
  runs: () => request("/api/runs"),
  run: (id) => request(`/api/runs/${id}`),
  modelHealth: () => request("/api/model-health"),
  settings: () => request("/api/settings"),
  updateSettings: (settings) => request("/api/settings", { method: "PUT", body: JSON.stringify({ settings }) }),
  bulkImport: (payload) => request("/api/imports/bulk", { method: "POST", body: JSON.stringify(payload) }),
  syncApplicationEmails: (payload) => request("/api/email-sync/applications", { method: "POST", body: JSON.stringify(payload) }),
  applicationEvents: (limit = 50) => request(`/api/application-events?limit=${encodeURIComponent(limit)}`),
  exportWorkbook: () => request("/api/workbook/export", { method: "POST" }),
  exportBundle: () => request("/api/export/workbook", { method: "POST" }),
  exportDownload: (exportId) => apiRequestUrl(resolvedApiBase || "/api", `/api/export/${encodeURIComponent(exportId)}/download`),
  artifactContent: (id, kind = "cover-letter") => request(`/api/artifacts/${id}/content?kind=${encodeURIComponent(kind)}`),
  updateArtifactContent: (id, payload) => request(`/api/artifacts/${id}/content`, { method: "PATCH", body: JSON.stringify(payload) }),
  gradeArtifact: (id) => request(`/api/artifacts/${id}/grade`, { method: "POST" }),
  openArtifactFolder: (id) => request(`/api/artifacts/${id}/open-folder`, { method: "POST" }),
  openArtifactFolderAlias: (id) => request(`/api/artifacts/${id}/open`),
  artifactDownload: (id, kind = "resume") => request(`/api/artifacts/${id}/download?kind=${encodeURIComponent(kind)}`),
  tomorrowChecklist: () => request("/api/checklist/apply-queue"),
  assistUpload: (id, kind = "resume") =>
    request(`/api/jobs/${id}/assist-upload?kind=${kind}&confirm=review-before-submit`, { method: "POST" }),
};
