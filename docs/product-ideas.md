# JobFiller Product Ideas

This is a brainstorm, not a committed roadmap. The goal is to keep useful
outside signals close to the project while preserving JobFiller's current
boundary: prepare application materials locally, keep the human in review, and
never submit applications automatically.

Last research pass: June 24, 2026.

## Signals From The Market

- Autofill is now table stakes. Public job-search tools emphasize one-click or
  browser-extension autofill, application tracking, tailored resumes, tailored
  cover letters, and generated screening-question answers.
- The strongest user pull is not pure automation; it is less repetition with
  higher-quality output. Users complain when tools spray applications at
  irrelevant roles or generate generic materials.
- Trust is becoming a differentiator. Job scams, fake recruiters, fake company
  pages, and suspicious text-message recruiting are common enough that users may
  value scam checks as much as speed.
- Users are tired of scattered workflow state: job boards, resumes, cover
  letters, email replies, notes, interview prep, and follow-up tasks often live
  in separate tools.
- AI-heavy hiring processes create anxiety for candidates. Users may want help
  preparing for AI interviews, documenting disclosure, and deciding whether a
  hiring process is worth continuing.

Representative references:

- [Simplify Copilot](https://simplify.jobs/copilot): autofill, tailored
  resumes/cover letters, and automatic application tracking.
- [JobWizard](https://jobwizard.ai/): autofill, custom question answers, cover
  letters, match scores, referral finder, and Gmail reply tracking.
- [Teal autofill](https://www.tealhq.com/tools/autofill-job-applications):
  application autofill and tailored responses to open-ended questions.
- [FTC job-scam guidance](https://consumer.ftc.gov/articles/job-scams): fake
  jobs often seek money, personal information, or both.
- [Greenhouse 2026 Candidate AI Interview Report](https://www.greenhouse.com/blog/2026-candidate-ai-interview-report):
  AI interviews are mainstream, but candidate trust and transparency lag behind
  adoption.

## Candidate Feature Ideas

### Application Intake

- Browser import assistant: capture the current job page, apply URL, visible
  application questions, salary, location, recruiter name, and source board into
  the existing import contract.
- Duplicate and stale-posting detection: warn when a job has already been
  imported, appears on multiple boards, or has signals of being reposted without
  meaningful changes.
- Source confidence badge: show whether the posting was found on the employer
  domain, an ATS domain, a job board, a recruiter message, or an unverified
  source.
- Fit-reason panel: explain why a role was imported or skipped using concrete
  requirements, location/work-model match, and candidate preferences.

### Material Quality

- Resume variant library: keep a small set of approved base resumes, such as
  backend, data, finance, and general software, instead of generating every
  packet from one profile.
- Evidence-backed bullet suggestions: suggest edits only when they map to
  existing candidate facts, source resume lines, or user-approved profile facts.
- Generic-language linting: flag vague AI-ish wording, unsupported metrics, and
  phrases that appear across too many generated letters.
- Delta review: before export, show what changed from the base resume or last
  generated packet.
- Question memory: remember user-approved answers for recurring questions like
  work authorization, relocation, compensation expectations, and sponsorship,
  while keeping uncertain answers queued for review.

### Workflow Streamlining

- Single next-action queue: one view that answers "what should I do next?"
  across missing facts, packet review, upload-ready files, follow-ups, and
  interview prep.
- Batch triage mode: quickly accept, reject, or defer imported jobs before any
  expensive artifact generation.
- Saved preference packs: reusable search/import settings for roles such as
  backend engineer, financial analyst, or local hybrid roles.
- Application packet checklist: per job, show resume, cover letter, custom
  answers, upload status, review status, and next follow-up date.
- Follow-up reminders: generate optional tasks for recruiter outreach, thank-you
  notes, and response checks after a configurable number of days.
- Gmail reply/status sync: detect likely recruiter replies and update job status
  without requiring users to manually reconcile email and dashboard state.
- Calendar/interview prep handoff: if an interview appears in email or manual
  notes, create a prep packet with job summary, company notes, resume claims to
  defend, and questions to ask.

### Safety And Trust

- Scam-risk checklist: flag requests for payment, non-corporate email domains,
  off-platform chat pressure, suspicious urgency, vague company identity, or
  apply URLs that do not match the employer/ATS domain.
- Sensitive-data guardrails: warn before exporting or uploading SSN, bank
  details, passport data, driver's-license images, or other high-risk personal
  information.
- Public-link verification: check that job and apply URLs are public HTTPS pages
  and avoid credentialed, private, or redirect-heavy links.
- Human-submit boundary UI: keep final submit as a manual step, and make the
  boundary visible wherever upload or autofill helper flows are documented.
- Provenance log: record which source page, resume file, profile facts, and user
  decisions produced each generated artifact.

### Outcome Learning

- Outcome dashboard: track views such as imported, applied, rejected, interview,
  offer, no response, withdrawn, and scam/unsafe.
- Source effectiveness: compare callback rates by source, role family, work
  model, location, and resume variant.
- Time cost tracking: estimate where time is going: discovery, triage, missing
  facts, packet generation, upload, and follow-up.
- Feedback loop from outcomes: when a role converts or fails, let the user mark
  why so future imports and packets can improve without inventing facts.

## Streamlining Opportunities In Current Docs

- Put the safest default flow first everywhere: import jobs, review/triage, fill
  missing facts, generate packets, manually review, then manually apply.
- Keep agent-facing docs focused on importing structured jobs. Put browser
  upload/file-dialog helpers in their own section so they do not blur into
  "auto-submit" behavior.
- Add a short "when to stop and ask the user" rule to prompts: compensation,
  sponsorship, relocation, disability, veteran status, demographic questions,
  writing prompts, and anything requiring a personal judgment should stay manual.
- Add examples of good and bad generated answers. Good answers should be short,
  concrete, source-backed, and editable; bad answers should look generic,
  unsupported, or overconfident.
- Use one shared vocabulary across docs: imported job, triage, missing fact,
  application packet, artifact, upload helper, manual submit, follow-up.

## Possible Documentation Additions

- `docs/safety-and-trust.md`: scam-risk checklist, personal-data guardrails, and
  the human-submit boundary.
- `docs/user-workflow.md`: the main end-user flow from discovery through
  follow-up, separate from MCP integration details.
- `docs/material-quality.md`: rules for grounded resume/cover-letter generation,
  answer reuse, and generic-language checks.
- `docs/status-model.md`: recommended job statuses, outcome tracking, and what
  changes them.

## Near-Term Product Bets

1. Safety-first import triage: source confidence, duplicate detection, scam-risk
   flags, and batch accept/reject before artifact generation.
2. Grounded material review: resume deltas, provenance, generic-language linting,
   and user-approved answer memory.
3. One next-action queue: missing facts, ready packets, upload/manual apply
   handoffs, follow-ups, and interview prep in one place.
4. Email-aware status updates: Gmail/recruiter reply detection that updates
   status while keeping user review in control.
