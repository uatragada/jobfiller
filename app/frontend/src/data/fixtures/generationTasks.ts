import type { GenerationTask } from "../../types/domain";

export const generationTasks: GenerationTask[] = [
  { id: 401, priority: "P1", task: "Fit Analysis", company: "Stripe", role: "Senior Backend Engineer", model: "Local LLM", status: "Needs Review", tokens: 1840, created: "8:22 AM", ready: true },
  { id: 402, priority: "P1", task: "Cover Letter", company: "OpenAI", role: "Software Engineer, Full Stack", model: "Local LLM", status: "Queued", tokens: 0, created: "8:30 AM", ready: false },
  { id: 403, priority: "P2", task: "Interview Prep", company: "Anthropic", role: "ML Engineer", model: "Cloud LLM", status: "Running", tokens: 920, created: "8:34 AM", ready: false },
  { id: 404, priority: "P2", task: "Answer Draft", company: "Linear", role: "QA Engineer", model: "Local LLM", status: "Queued", tokens: 0, created: "Yesterday", ready: false },
  { id: 405, priority: "P3", task: "Follow-up Email", company: "Notion", role: "Product Manager", model: "Local LLM", status: "Completed", tokens: 640, created: "Jun 23", ready: true },
];
