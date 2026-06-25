import type { IntegrationSource } from "../../types/domain";

export const integrations: IntegrationSource[] = [
  { id: "indeed", name: "Indeed", status: "Active", tools: 4, lastSeen: "2 min ago", auth: "Token", errors: 0, recentCalls: ["search_jobs", "fetch_job", "dedupe_url"] },
  { id: "linkedin", name: "LinkedIn", status: "Idle", tools: 2, lastSeen: "18 min ago", auth: "Browser", errors: 1, recentCalls: ["read_open_tabs", "assist_upload"] },
  { id: "company-pages", name: "Company Pages", status: "Active", tools: 5, lastSeen: "5 min ago", auth: "None", errors: 0, recentCalls: ["crawl_page", "extract_schema"] },
  { id: "greenhouse", name: "Greenhouse", status: "Active", tools: 3, lastSeen: "9 min ago", auth: "None", errors: 0, recentCalls: ["fetch_board", "normalize_posting"] },
  { id: "lever", name: "Lever", status: "Disabled", tools: 3, lastSeen: "Yesterday", auth: "None", errors: 0, recentCalls: ["fetch_board"] },
  { id: "manual-url", name: "Manual URL", status: "Active", tools: 1, lastSeen: "Now", auth: "None", errors: 0, recentCalls: ["import_url"] },
  { id: "email", name: "Email", status: "Error", tools: 2, lastSeen: "1 hour ago", auth: "OAuth", errors: 2, recentCalls: ["sync_status_email", "parse_followup"] },
];
