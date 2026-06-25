import type { ModelHealthService } from "../../types/domain";

export const modelHealthServices: ModelHealthService[] = [
  { id: "system", service: "System API", status: "Healthy", latency: "82ms", lastCheck: "Now", version: "0.2.0", errors: 0, checks: ["Session token valid", "Database reachable", "Artifact folder writable"] },
  { id: "ollama", service: "Local LLM", status: "Online", latency: "3.8s", lastCheck: "Now", version: "llama-local", errors: 0, checks: ["Endpoint reachable", "Model loaded", "Prompt round-trip ok"] },
  { id: "finder", service: "Finder", status: "Healthy", latency: "410ms", lastCheck: "2 min ago", version: "browser", errors: 0, checks: ["Source configs valid", "URL import ready"] },
  { id: "mcp", service: "MCP Servers", status: "Warning", latency: "1.2s", lastCheck: "8 min ago", version: "3 servers", errors: 2, checks: ["Codex connected", "Email auth warning", "LinkedIn browser idle"] },
  { id: "exports", service: "Workbook Export", status: "Healthy", latency: "92ms", lastCheck: "Today", version: "xlsx/json/csv", errors: 0, checks: ["XLSX writer ready", "CSV writer ready"] },
];
