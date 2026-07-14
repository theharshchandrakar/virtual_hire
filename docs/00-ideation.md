# 00 — Ideation

**Purpose:** Establish why this project exists and what "working" looks like before any scope or architecture is defined.

**Depends on:** Nothing — this is the root document.
**Feeds into:** [01-problem-space-and-scope.md](01-problem-space-and-scope.md) (turns this framing into precise in/out-of-scope boundaries).

---

## Working name

**Sift** — used throughout this documentation set as the project codename.

## Problem framing

Small and mid-sized HR teams (roughly 5–200 open requisitions/year) run resume collection and interview feedback through a patchwork of email inboxes, shared spreadsheets, and Slack/Teams threads. This happens for one of two reasons: they've outgrown ad hoc tools but can't justify the cost and implementation overhead of a full Applicant Tracking System (ATS), or they already have an ATS but its resume parsing and interview feedback capture are weak enough that teams route around it with spreadsheets anyway.

The pain is concrete and recurring:

- Resumes arrive as email attachments, LinkedIn exports, and referral forwards with no consistent structure, so nobody can search "who has Kubernetes experience" across the pipeline.
- Interview feedback lives in interviewers' heads, private notes apps, or gets typed into a Slack message that scrolls away. Hiring decisions get made on partial, unretrievable input.
- HR generalists spend hours doing manual work a system should do: matching a resume to the right requisition, chasing interviewers for scorecards, compiling feedback into a summary for the hiring manager.
- Nobody feels this more directly than the HR generalist and recruiter, who are accountable for pipeline hygiene but have no tool built for the job.

## Primary users and their jobs-to-be-done

| User | Distinct job-to-be-done |
|---|---|
| HR generalist | "Get every resume into one searchable, structured place, tied to the right requisition, without manual re-entry." |
| Recruiter | "See the full pipeline for a requisition at a glance — who's applied, where they are in the process, what's blocking a decision." |
| Hiring manager | "Get a fast, trustworthy summary of a candidate — resume plus what interviewers actually said — without digging through threads." |
| Candidate | "Submit my resume once, know it was received, and not have my data mishandled or resubmitted endlessly." |
| Interviewer (subset of hiring manager / HR role) | "Record structured feedback quickly, right after the interview, without hunting for the right form or thread." |

These are deliberately different jobs. A tool that serves the recruiter's pipeline view but ignores the interviewer's need for a two-minute feedback form will fail in practice, even if the data model is correct.

## Core value proposition

Sift gives HR teams one place where a resume becomes a structured, searchable candidate record the moment it arrives, stays connected to the requisition it's for, and accumulates interview feedback as structured scorecards instead of scattered notes — so that by the time a hiring decision is needed, the full picture already exists instead of having to be reconstructed from email and memory.

## Non-goals (stated early, revisited in scope doc)

These are deliberate exclusions, not omissions to fix later:

- **Not a full ATS replacement.** No offer management, e-signature, onboarding, or payroll/HRIS integration in v1.
- **Not a sourcing or job-board tool.** Sift collects resumes that arrive through it; it does not go find candidates.
- **Not an automated hiring-decision engine.** Sift structures and surfaces information; it does not rank, score, or recommend which candidate to hire.
- **Not a video interview platform.** No recording, transcription, or video analysis in v1.
- **Not a general-purpose HRIS.** Employee records post-hire are out of scope; Sift's data model ends at "hired" or "rejected."

## Success criteria — 6 months post-launch

| Signal | Target | Why it matters |
|---|---|---|
| % of resumes entering the system without manual re-keying | ≥ 90% | Proves ingestion actually replaces email/spreadsheet workflows, not just supplements them. |
| Median time from interview completion to scorecard submission | < 24 hours | Proves the feedback capture is low-friction enough to use immediately, not backfilled. |
| % of hiring decisions made with a complete scorecard set attached | ≥ 80% | Proves decisions are backed by retrievable structured data, the core value prop. |
| HR generalist time spent per requisition on manual coordination (self-reported) | Reduced by ≥ 30% vs. pre-Sift baseline | Direct measure of the labor pain this was built to remove. |
| Candidate complaints about data handling / resubmission friction | Near zero | Proxy for whether the consent and submission flow is trustworthy, not just functional. |

## Open Questions

- Do we validate the "email/spreadsheet patchwork" problem framing against a specific pilot organization before locking scope, or proceed on the general pattern described here?
- Is the target org size band (5–200 requisitions/year) correct, or should v1 aim narrower (e.g., 5–50) to keep the first build tight?
- Should candidate-side success be measured at all in v1, given candidates are a secondary user with a thin interface?
