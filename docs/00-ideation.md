# 00 — Ideation

**Purpose:** Establish why this project exists and what "working" looks like before any scope or architecture is defined.

**Depends on:** Nothing — this is the root document.
**Feeds into:** [01-problem-space-and-scope.md](01-problem-space-and-scope.md) (turns this framing into precise in/out-of-scope boundaries).

> **Revision note (2026-07-16):** Sift's product surface expanded from one AI-assisted capability (resume search) to three parallel scored-assessment services — Resume Analyzer, Interview Live Proctoring, and Interview Transcript + Assignment Reviewer — each running through a deterministic scoring engine and a large-model verdict step. This is a materially bigger product than the one this document originally described, not an incremental add. It directly reverses the "not a video interview platform" non-goal below (candidates and interviewers should read that reversal as deliberate, not a scope-discipline lapse) — see [CHANGELOG.md](../CHANGELOG.md) for the full pivot record and [08-privacy-and-compliance.md](08-privacy-and-compliance.md) for why that reversal carries real legal weight the rest of this document set treats seriously.

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

## Three scored-assessment services

Beyond the structured record described above, Sift now offers three parallel AI-assisted assessment services, each covering a different artifact in the hiring pipeline and each producing a **verdict** — a deterministic score breakdown plus a large-model-generated narrative explanation, never a bare number:

| Service | Assesses | Produces |
|---|---|---|
| **Resume Analyzer** | The parsed resume against a requisition's requirements | A fit verdict (`pass` / `review` / `fail`) with a narrative rationale, extending the existing resume-analysis pipeline in [06-architecture.md](06-architecture.md) rather than replacing it |
| **Interview Live Proctoring** | Audio/video signal from a live interview call (via an external video platform integration, not a Sift-hosted call — see [06-architecture.md](06-architecture.md)) | An integrity verdict flagging behavioral/biometric anomalies (multiple people in frame, face not detected, voice mismatch, etc.), generated **after** the interview, never blocking or intervening in it live — see I15 in [04-invariants.md](04-invariants.md) |
| **Interview Transcript + Assignment Reviewer** | The interview transcript and, where a take-home assignment exists, the candidate's submission | A competency verdict against the interview/assignment rubric |

All three share one architectural pattern, detailed in [06-architecture.md](06-architecture.md): a deterministic scoring engine computes rule-based sub-scores first, and a large (200–300B-parameter class) Verdict/Judge model — the fourth agent in the existing LLM crew — reviews the scoring engine's output plus any relevant crew-agent output and writes the final verdict narrative. The judge never scores from a blank slate; it explains and contextualizes what the deterministic layer already computed. This mirrors, and is a direct evolution of, the "human always makes the call, AI never gates a decision" posture the rest of this document already commits to below — a verdict is advisory input to an HR user's decision, not the decision itself.

## Core value proposition

Sift gives HR teams one place where a resume becomes a structured, searchable candidate record the moment it arrives, stays connected to the requisition it's for, accumulates interview feedback as structured scorecards instead of scattered notes, and is assessed — resume, live interview integrity, and transcript/assignment competency alike — through a consistent, explainable, deterministic-first-then-judged scoring pipeline, so that by the time a hiring decision is needed, the full picture already exists instead of having to be reconstructed from email, memory, and gut feel.

## Non-goals (stated early, revisited in scope doc)

These are deliberate exclusions, not omissions to fix later:

- **Not a full ATS replacement.** No offer management, e-signature, onboarding, or payroll/HRIS integration in v1.
- **Not a sourcing or job-board tool.** Sift collects resumes that arrive through it; it does not go find candidates.
- **Not an automated hiring-decision engine.** Sift structures, scores, and surfaces information — including letting HR users *ask* for candidates matching a query via retrieval-augmented search, and including the three verdict services above — but no verdict, search result, or match output autonomously gates or auto-advances a pipeline stage without human review. A `fail` verdict is a flag for a human to look at, not a rejection.
- **Not a video conferencing platform.** Sift never hosts, transmits, or mixes the live interview call itself — see the "Not a video interview platform" reversal note above. It only ingests signals/recordings from an external platform the organization already uses, after the fact or via that platform's own webhook/bot integration.
- **Not a real-time intervention system.** Proctoring analysis is asynchronous and advisory; it never pauses, warns, or ends a live interview, and never auto-disqualifies a candidate — see I15 in [04-invariants.md](04-invariants.md).
- **Not a general-purpose HRIS.** Employee records post-hire are out of scope; Sift's data model ends at "hired" or "rejected."

## Success criteria — 6 months post-launch

| Signal | Target | Why it matters |
|---|---|---|
| % of resumes entering the system without manual re-keying | ≥ 90% | Proves ingestion actually replaces email/spreadsheet workflows, not just supplements them. |
| Median time from interview completion to scorecard submission | < 24 hours | Proves the feedback capture is low-friction enough to use immediately, not backfilled. |
| % of hiring decisions made with a complete scorecard set attached | ≥ 80% | Proves decisions are backed by retrievable structured data, the core value prop. |
| HR generalist time spent per requisition on manual coordination (self-reported) | Reduced by ≥ 30% vs. pre-Sift baseline | Direct measure of the labor pain this was built to remove. |
| Candidate complaints about data handling / resubmission friction | Near zero | Proxy for whether the consent and submission flow is trustworthy, not just functional. |
| % of resume searches (RAG-based) where the recruiter acts on a returned candidate (views, advances, or contacts) | ≥ 50% | Proves semantic search/match output is trusted and useful, not ignored noise. |
| % of verdicts (across all 3 services) where the HR user's eventual pipeline decision agrees with the verdict's `pass`/`review`/`fail` label | Directionally tracked, no hard target yet | A verdict that's routinely overridden either means the scoring rubric is wrong or HR users don't trust it — either way it's a signal to investigate, not a pass/fail gate on the feature itself (an override is not a failure of the tool). |
| Legal sign-off obtained for interview proctoring in every jurisdiction where it's enabled, before it's enabled there | 100%, no exceptions | Given the biometric-data/consent stakes documented in [08-privacy-and-compliance.md](08-privacy-and-compliance.md), this is a launch gate, not a trailing metric. |

## Open Questions

- Do we validate the "email/spreadsheet patchwork" problem framing against a specific pilot organization before locking scope, or proceed on the general pattern described here?
- Is the target org size band (5–200 requisitions/year) correct, or should v1 aim narrower (e.g., 5–50) to keep the first build tight?
- Should candidate-side success be measured at all in v1, given candidates are a secondary user with a thin interface?
- **New in this revision:** should interview proctoring ship org-by-org, gated on that organization's jurisdiction clearing legal review, rather than as a platform-wide v1 feature turned on for everyone at once — see the phased rollout question in [09-roadmap.md](09-roadmap.md).
- **New in this revision:** what does "success" look like for the proctoring service specifically, given it's explicitly not meant to change any hiring outcome by itself — is a low false-positive rate (verdicts HR users don't dismiss as noise) the right proxy, absent a hiring-outcome metric to tie it to?
