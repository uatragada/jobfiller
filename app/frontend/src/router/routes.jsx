import {
  Activity,
  Briefcase01 as Briefcase,
  CalendarCheck02 as CalendarCheck,
  Download01 as Download,
  File02 as FileText,
  HelpCircle,
  Link02 as Link,
  Mail01 as Mail,
  RefreshCcw01 as RefreshCcw,
  Settings01 as Settings,
  Upload01 as Upload,
  User01 as User,
} from "@untitledui/icons";

export const routes = [
  { id: "jobs", path: "/jobs", label: "Jobs", icon: Briefcase, group: "main", legacy: ["jobs"] },
  { id: "email-alerts", path: "/email-alerts", label: "Email Alerts", icon: Mail, group: "main", legacy: ["alerts", "email", "application-events"] },
  { id: "questions", path: "/questions", label: "Questions", icon: HelpCircle, group: "main", legacy: ["questions"] },
  { id: "apply-queue", path: "/apply-queue", label: "Apply Queue", icon: CalendarCheck, group: "main", legacy: ["tomorrow", "apply"] },
  { id: "profile-facts", path: "/profile-facts", label: "Profile Facts", icon: User, group: "main", legacy: ["facts", "profile"] },
  { id: "runs-logs", path: "/runs-logs", label: "Runs & Logs", icon: FileText, group: "main", legacy: ["runs", "logs"] },
  { id: "generate-queue", path: "/generate-queue", label: "Auto Generate", icon: RefreshCcw, group: "tools", legacy: ["reprocess", "generate"] },
  { id: "assist-upload", path: "/assist-upload", label: "Assist Upload", icon: Upload, group: "tools", legacy: ["assist"] },
  { id: "agent-import-mcp", path: "/agent-import-mcp", label: "Agent Import / MCP", icon: Link, group: "tools", legacy: ["agent"] },
  { id: "export-workbook", path: "/export-workbook", label: "Export Workbook", icon: Download, group: "tools", legacy: ["export"] },
  { id: "settings", path: "/settings", label: "Settings", icon: Settings, group: "system", legacy: ["settings"] },
  { id: "model-health", path: "/model-health", label: "Model Health", icon: Activity, group: "system", legacy: ["health"] },
];

export const primaryRoutes = routes.filter((route) => !route.hidden);

const routeById = new Map(routes.map((route) => [route.id, route]));
const routeByPath = new Map(routes.map((route) => [route.path, route]));
const legacyMap = new Map(routes.flatMap((route) => [route.id, route.path.replace(/^\//, ""), ...(route.legacy || [])].map((key) => [key, route.id])));

export function normalizeRoute(value) {
  const raw = String(value || "").replace(/^#\/?/, "").replace(/^\//, "").replace(/\/$/, "");
  return routeById.has(raw) ? raw : legacyMap.get(raw) || "jobs";
}

export function routeFromLocation(location = window.location) {
  const hashRoute = location.hash ? normalizeRoute(location.hash) : "";
  if (hashRoute) return hashRoute;
  return normalizeRoute(location.pathname);
}

export function pathForRoute(id) {
  return routeById.get(normalizeRoute(id))?.path || "/jobs";
}

export function getRoute(id) {
  return routeById.get(normalizeRoute(id)) || routes[0];
}

export function routeForPath(path) {
  return routeByPath.get(path)?.id || normalizeRoute(path);
}
