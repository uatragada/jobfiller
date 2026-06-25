export type JobStatus = "New" | "Discovered" | "Review" | "Applied" | "Action Needed" | "Interview" | "Rejected" | "Ready" | "Needs Info" | "Submitted" | "Blocked";

export type Job = {
  id: number;
  posted: string;
  imported: string;
  company: string;
  role: string;
  location: string;
  workModel: string;
  employment: string;
  status: JobStatus;
  fit: number;
  grade: string;
  ready: boolean;
  files: number;
  source: string;
  sourceUrl: string;
  keywords: string[];
  notes: string;
  latestArtifactId?: number | null;
  latestResumePdfPath?: string;
  latestResumeTexPath?: string;
  latestCoverLetterPath?: string;
  artifactCount?: number;
  compileStatus?: string;
  manualQuestions?: string[];
  openQuestions?: number;
};

export type Question = {
  id: number;
  company: string;
  role: string;
  question: string;
  type: string;
  suggestedAnswer: string;
  status: "Unanswered" | "Needs Review" | "Approved" | "Attached";
  confidence: number;
  source: string;
  updated: string;
  factsUsed: string[];
  jobId?: number;
};

export type ApplicationQueueItem = {
  id: number;
  jobId?: number;
  priority: string;
  company: string;
  role: string;
  fit: number;
  packet: string;
  questions: string;
  status: "Discovered" | "Ready" | "Needs Info" | "Action Needed" | "Applying" | "Applied" | "Interview" | "Rejected" | "Submitted" | "Follow-up";
  due: string;
  owner: string;
  checklist: Record<string, boolean>;
};

export type ProfileFact = {
  id: number;
  category: string;
  field: string;
  value: string;
  confidence: number;
  source: string;
  usedIn: string;
  verified: boolean;
  updated: string;
  conflicts: string[];
};

export type RunLog = {
  id: string;
  started: string;
  type: string;
  target: string;
  status: "Succeeded" | "Running" | "Failed";
  steps: number;
  duration: string;
  model: string;
  cost: string;
  artifacts: number;
  logs: string[];
};

export type GenerationTask = {
  id: number;
  jobId?: number;
  priority: string;
  task: string;
  company: string;
  role: string;
  model: "Local LLM" | "Cloud LLM";
  status: "Blocked" | "Queued" | "Running" | "Needs Review" | "Completed" | "Cancelled" | "Failed";
  files?: number;
  tokens: number;
  created: string;
  ready: boolean;
  openQuestions?: number;
  latestArtifactId?: number | null;
};

export type UploadAsset = {
  id: number;
  filename: string;
  type: string;
  extractedFacts: number;
  status: "Uploaded" | "Extracting" | "Ready" | "Imported" | "Conflict";
  imported: string;
  summary: string;
};

export type IntegrationSource = {
  id: string;
  name: string;
  status: "Active" | "Idle" | "Error" | "Disabled";
  tools: number;
  lastSeen: string;
  auth: string;
  errors: number;
  recentCalls: string[];
};

export type WorkbookExport = {
  id: number;
  template: string;
  status: "Ready" | "Generated" | "Scheduled";
  rows: number;
  created: string;
  sheets: string[];
};

export type ModelHealthService = {
  id: string;
  service: string;
  status: "Healthy" | "Online" | "Warning" | "Error";
  latency: string;
  lastCheck: string;
  version: string;
  errors: number;
  checks: string[];
};

export type EmailAlert = {
  id: number;
  jobId: number;
  receivedAt: number;
  received: string;
  company: string;
  role: string;
  sender: string;
  subject: string;
  state: "Applied" | "Accepted" | "Action Needed" | "Interview" | "Rejected" | "Unknown";
  category: "Accepted" | "Applied" | "Action Needed" | "Interview" | "Rejection" | "Other";
  source: string;
  followUp: string;
  actionUrl: string;
  evidenceUrl: string;
};
