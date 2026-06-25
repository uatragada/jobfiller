import React, { useEffect, useMemo, useState } from "react";
import { AppShell } from "./layout/AppShell.jsx";
import { routeFromLocation, normalizeRoute, pathForRoute } from "./router/routes.jsx";
import { useJobFillerState } from "./state/useJobFillerState.jsx";
import { JobsPage } from "./pages/JobsPage.jsx";
import { EmailAlertsPage } from "./pages/EmailAlertsPage.jsx";
import { QuestionsPage } from "./pages/QuestionsPage.jsx";
import { ApplyQueuePage } from "./pages/ApplyQueuePage.jsx";
import { ProfileFactsPage } from "./pages/ProfileFactsPage.jsx";
import { RunsLogsPage } from "./pages/RunsLogsPage.jsx";
import { GenerateQueuePage } from "./pages/GenerateQueuePage.jsx";
import { AssistUploadPage } from "./pages/AssistUploadPage.jsx";
import { AgentImportMcpPage } from "./pages/AgentImportMcpPage.jsx";
import { ExportWorkbookPage } from "./pages/ExportWorkbookPage.jsx";
import { SettingsPage } from "./pages/SettingsPage.jsx";
import { ModelHealthPage } from "./pages/ModelHealthPage.jsx";

const pageComponents = {
  jobs: JobsPage,
  "email-alerts": EmailAlertsPage,
  questions: QuestionsPage,
  "apply-queue": ApplyQueuePage,
  "profile-facts": ProfileFactsPage,
  "runs-logs": RunsLogsPage,
  "generate-queue": GenerateQueuePage,
  "assist-upload": AssistUploadPage,
  "agent-import-mcp": AgentImportMcpPage,
  "export-workbook": ExportWorkbookPage,
  settings: SettingsPage,
  "model-health": ModelHealthPage,
};

export function App() {
  const store = useJobFillerState();
  const [activeRoute, setActiveRoute] = useState(() => routeFromLocation(window.location));
  const [topSearch, setTopSearch] = useState("");
  const [importUrl, setImportUrl] = useState("");
  const ActivePage = pageComponents[activeRoute] || JobsPage;

  useEffect(() => {
    const syncRoute = () => setActiveRoute(routeFromLocation(window.location));
    window.addEventListener("popstate", syncRoute);
    window.addEventListener("hashchange", syncRoute);
    if (window.location.pathname === "/" && !window.location.hash) {
      window.history.replaceState({ route: "jobs" }, "", pathForRoute("jobs"));
    }
    return () => {
      window.removeEventListener("popstate", syncRoute);
      window.removeEventListener("hashchange", syncRoute);
    };
  }, []);

  const counts = useMemo(
    () => ({
      jobs: store.jobs.length,
      "email-alerts": store.emailAlerts.length,
      questions: store.questions.filter((question) => question.status !== "Approved").length,
      "apply-queue": store.applications.length,
      "profile-facts": store.profileFacts.length,
      "generate-queue": store.generationTasks.filter((task) => task.status !== "Completed").length,
    }),
    [store.jobs.length, store.emailAlerts.length, store.questions, store.applications.length, store.profileFacts.length, store.generationTasks],
  );

  function navigate(route) {
    const normalized = normalizeRoute(route);
    setActiveRoute(normalized);
    const nextPath = pathForRoute(normalized);
    if (window.location.pathname !== nextPath) {
      window.history.pushState({ route: normalized }, "", nextPath);
    }
  }

  function handleTopSearch(value) {
    setTopSearch(value);
    store.actions.setFilter("jobs", "search", value);
    if (activeRoute !== "jobs") navigate("jobs");
  }

  async function handleImport() {
    if (!importUrl.trim()) {
      store.toast("Paste a URL before importing.", "warning");
      return;
    }
    await store.actions.importJobUrl(importUrl.trim());
    setImportUrl("");
    navigate("jobs");
  }

  async function handleScan() {
    try {
      const result = await store.actions.triggerScan({
        limit: store.settings.finderLimit,
      });
      if (result?.codex_prompt_path) {
        store.toast(`Codex scan request ready: ${result.codex_prompt_path}`);
      }
      navigate("runs-logs");
    } catch (error) {
      store.toast(`Scan could not start: ${error?.message || "backend unavailable"}`, "warning");
      navigate("agent-import-mcp");
    }
  }

  return (
    <AppShell
      activeRoute={activeRoute}
      onNavigate={navigate}
      counts={counts}
      settings={store.settings}
      topSearch={topSearch}
      onTopSearch={handleTopSearch}
      importUrl={importUrl}
      onImportUrl={setImportUrl}
      onImport={handleImport}
      onScan={handleScan}
      liveStatus={store.liveStatus}
      onRefresh={store.actions.refreshData}
      loading={store.loadingAction}
      toasts={store.toasts}
      dismissToast={store.actions.dismissToast}
      modal={store.modal}
      closeModal={() => store.actions.setModal(null)}
      confirmModal={(modal) => store.toast(`${modal?.title || "Action"} confirmed.`)}
    >
      <ActivePage store={store} onNavigate={navigate} />
    </AppShell>
  );
}
