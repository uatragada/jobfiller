import type { UploadAsset } from "../../types/domain";

export const uploads: UploadAsset[] = [
  { id: 501, filename: "candidate-resume.pdf", type: "PDF", extractedFacts: 42, status: "Ready", imported: "8:10 AM", summary: "Parsed resume sections, skills, projects, and education evidence." },
  { id: 502, filename: "backend-projects.md", type: "Markdown", extractedFacts: 18, status: "Imported", imported: "Yesterday", summary: "Converted project notes into reusable backend and testing facts." },
  { id: 503, filename: "stripe-job.png", type: "Screenshot", extractedFacts: 9, status: "Conflict", imported: "Yesterday", summary: "Detected duplicate role requirements and one location conflict." },
  { id: 504, filename: "questions.csv", type: "CSV", extractedFacts: 12, status: "Uploaded", imported: "Jun 22", summary: "Waiting for extraction." },
];
