import type { ProfileFact } from "../../types/domain";

export const profileFacts: ProfileFact[] = [
  { id: 301, category: "Identity", field: "Preferred Role", value: "Backend or full-stack engineering roles with product ownership.", confidence: 95, source: "Profile", usedIn: "42 jobs", verified: true, updated: "Today", conflicts: [] },
  { id: 302, category: "Experience", field: "FastAPI", value: "Built production-style APIs with tests, validation, and background workflows.", confidence: 92, source: "Resume", usedIn: "37 jobs", verified: true, updated: "Today", conflicts: [] },
  { id: 303, category: "Projects", field: "Document AI", value: "Created document extraction workflows with evidence capture and QA loops.", confidence: 88, source: "Portfolio", usedIn: "21 jobs", verified: true, updated: "Yesterday", conflicts: [] },
  { id: 304, category: "Skills", field: "React", value: "Built dense operational dashboards with accessible controls and browser QA.", confidence: 84, source: "Project notes", usedIn: "18 jobs", verified: false, updated: "Yesterday", conflicts: ["frontend_depth"] },
  { id: 305, category: "Education", field: "Degree", value: "Computer science and applied AI coursework.", confidence: 78, source: "Resume", usedIn: "9 jobs", verified: false, updated: "Jun 22", conflicts: [] },
  { id: 306, category: "Preferences", field: "Location", value: "Remote-first; hybrid is acceptable for strong roles.", confidence: 98, source: "Settings", usedIn: "64 jobs", verified: true, updated: "Today", conflicts: [] },
  { id: 307, category: "Reusable Answers", field: "Why Backend", value: "I like turning ambiguous workflows into reliable systems with clear contracts.", confidence: 90, source: "Question bank", usedIn: "12 answers", verified: true, updated: "Jun 21", conflicts: [] },
];
