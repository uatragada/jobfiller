import type { RunLog } from "../../types/domain";

export const runs: RunLog[] = [
  { id: "run_2814", started: "8:22 AM", type: "Import", target: "Stripe", status: "Succeeded", steps: 6, duration: "18s", model: "Local LLM", cost: "$0.00", artifacts: 4, logs: ["Fetched job page", "Extracted requirements", "Generated fit analysis", "Saved artifacts"] },
  { id: "run_2813", started: "8:18 AM", type: "Scan", target: "Indeed feed", status: "Running", steps: 3, duration: "42s", model: "Finder", cost: "$0.00", artifacts: 12, logs: ["Scanning source", "Deduplicating URLs", "Waiting for parser"] },
  { id: "run_2812", started: "7:58 AM", type: "Generate", target: "OpenAI packet", status: "Succeeded", steps: 8, duration: "51s", model: "Ollama", cost: "$0.00", artifacts: 3, logs: ["Prompt assembled", "Resume generated", "Cover letter generated", "Grade complete"] },
  { id: "run_2811", started: "7:41 AM", type: "Generate", target: "Linear QA packet", status: "Failed", steps: 4, duration: "27s", model: "Ollama", cost: "$0.00", artifacts: 1, logs: ["Prompt assembled", "Model timeout", "Retry policy: manual"] },
  { id: "run_2810", started: "Yesterday", type: "Export", target: "Workbook", status: "Succeeded", steps: 5, duration: "9s", model: "System", cost: "$0.00", artifacts: 3, logs: ["Collected rows", "Wrote XLSX", "Wrote JSON", "Wrote CSV"] },
];
