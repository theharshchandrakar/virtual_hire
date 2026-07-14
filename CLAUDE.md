# CLAUDE.md

This file logs every prompt given to Claude in this project, along with a summary of the response generated. It is appended to, not rewritten, as the project progresses.

---

## 2026-07-13 — Initial documentation set

**Prompt:**
> You are setting up foundational documentation for a new project: a Resume Collector & Interview Analyzer platform for HR teams across organizations. Before any code is written, generate a complete documentation set in a /docs directory at the project root. [Full spec requested 10 numbered docs (00-ideation through 09-roadmap) plus a docs/README.md index, each with a "Depends on / Feeds into" note, Mermaid diagrams where useful, tables over prose lists, and an "Open Questions" section — covering ideation, scope, assumptions, ontology, invariants, data model, architecture, technical stack, privacy/compliance, and roadmap. Also requested this CLAUDE.md prompt log.]

**Response summary:**
Created `/docs` with 10 numbered documents plus `docs/README.md`, forming a connected documentation chain (each doc's "Depends on / Feeds into" note links to its neighbors):

- **00-ideation.md** — problem framing (HR teams' fragmented resume/interview-feedback workflow), five distinct user JTBDs, non-goals, and six-month success metrics.
- **01-problem-space-and-scope.md** — precise problem statement, in/out-of-scope table, a Scope Creep Watchlist (AI ranking, full ATS replacement, video analysis, sourcing, etc., each with a reactivation condition), and a bounded-context Mermaid diagram.
- **02-assumptions.md** — 15 numbered assumptions across org structure, resume formats, interview data shape, and volume, each with a confidence level and break condition, plus an explicit unvalidated-unknowns list.
- **03-ontology.md** — core entities (Organization, HRUser, JobRequisition, Candidate, Resume, Application, Interview, Scorecard), identity/lifecycle for each, an ER diagram, and what's deliberately not first-class (Offer, Employee, Interviewer-as-entity, etc.).
- **04-invariants.md** — 9 system invariants (cross-org PII isolation, scorecard immutability post-submission, resume-to-candidate ownership, etc.) each with enforcement mechanism and test approach, plus the Application status state diagram.
- **05-data-model.md** — full Postgres schema (9 tables) translating the ontology, with an invariant-enforcement-layer summary table and schema-level ER diagram.
- **06-architecture.md** — component flowchart, an end-to-end sequence diagram (resume submission → lazy on-demand analysis), a sync/async boundary table, and a defense-in-depth multi-tenancy design (app layer + Postgres RLS + namespaced object storage).
- **07-technical-stack.md** — concrete stack (TypeScript/NestJS/Next.js, PostgreSQL, Redis+BullMQ, S3, hosted Claude API for parsing/analysis, managed auth, AWS Fargate/RDS) with a rationale and rejected alternative per layer.
- **08-privacy-and-compliance.md** — PII inventory, retention table, a deletion/anonymization flow diagram implementing the scorecard-immutability-compatible right-to-be-forgotten approach, org-scoped consent flow, and a regimes table (GDPR, India DPDP, US state laws, EEOC recordkeeping) with explicit **[NEEDS LEGAL REVIEW]** flags.
- **09-roadmap.md** — v1/v2/v3 phase table mapped to the scope doc, exit criteria between phases, and a Gantt timeline.
- **docs/README.md** — reading-order index with one-line summaries and a Mermaid dependency graph of all 10 docs.

All Mermaid diagrams (flowchart, sequence, ER, state, Gantt) were written and are syntactically valid. Every document ends with an Open Questions section flagging genuinely unresolved decisions rather than restating settled content.

No code was written in this session — documentation only, as requested.
