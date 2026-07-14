# 02 — Assumptions (System Epistemology)

**Purpose:** Make explicit what must be true about users, data, and workflows for the design in the following documents to hold — and flag what we don't yet know.

**Depends on:** [01-problem-space-and-scope.md](01-problem-space-and-scope.md) (scope defines which assumptions are even relevant).
**Feeds into:** [03-ontology.md](03-ontology.md) (entity definitions rely on these assumptions, especially around org structure and data shape) and [08-privacy-and-compliance.md](08-privacy-and-compliance.md) (data assumptions drive compliance posture).

---

## How to read this document

Each assumption has a **confidence level** (how sure we are it holds) and a **break condition** (what in the design fails if it turns out false). Low-confidence, high-impact assumptions are the ones to validate first, before building anything that depends on them.

## Assumptions about organizations and users

| # | Assumption | Confidence | What breaks if wrong |
|---|---|---|---|
| A1 | Each organization using Sift is a single legal/operational entity — no need to model parent/subsidiary org hierarchies in v1. | Medium | Multi-tenancy model ([06-architecture.md](06-architecture.md)) assumes a flat `organization_id` boundary; hierarchical orgs would need shared-visibility rules across the tenant boundary, a bigger change. |
| A2 | An HR user belongs to exactly one organization (no consultants/agencies working across multiple client orgs in one login). | High | Auth and RLS design in [06-architecture.md](06-architecture.md) assumes single-org membership; multi-org membership would require a role/context-switch model. |
| A3 | Organizations have a small, relatively flat set of roles: HR generalist, recruiter, hiring manager, interviewer — no deep custom permission hierarchies in v1. | Medium | Permissions model in [05-data-model.md](05-data-model.md) is a fixed enum, not a configurable RBAC system; wrong assumption means permission logic needs rework before GA with larger orgs. |
| A4 | Organizations run one hiring pipeline shape (the fixed state machine in [04-invariants.md](04-invariants.md)) — they don't need materially different stages per department. | Medium | Directly listed in the Scope Creep Watchlist; if wrong, "custom pipeline stages" moves from v2/v3 candidate to a v1 blocker. |

## Assumptions about resumes and candidate data

| # | Assumption | Confidence | What breaks if wrong |
|---|---|---|---|
| A5 | Resumes arrive primarily as PDF or DOCX files, in English, under 10MB. | High | Parsing pipeline ([06-architecture.md](06-architecture.md)) is built around document-text-extraction assumptions; other formats (images of resumes, other languages) require OCR and multi-language NLP, not assumed in v1 cost/latency budgets. |
| A6 | A resume is authored by and represents exactly one person (no group/team resumes, no recruiter-submitted "candidate slates" as a single document). | High | Invariant "a Resume belongs to exactly one Candidate" ([04-invariants.md](04-invariants.md)) depends on this; violated by agency bulk-submission documents. |
| A7 | Structured fields we extract (name, contact info, work history, education, skills) are present in most resumes in *some* recognizable form, even if formatting varies. | Medium | Parsing/analysis quality assumption; if resumes are highly unstructured (e.g., infographic resumes), extraction accuracy drops and the "structured record" value prop weakens. |
| A8 | A candidate, within one organization, is uniquely identifiable by email address for the purpose of detecting duplicate applications. | Medium | Deduplication logic in application intake assumes this; candidates using multiple email addresses will create duplicate candidate records — flagged as accepted v1 limitation, not silently wrong data. |
| A9 | Candidates do not need persistent login accounts in v1 — magic-link/email-token access is sufficient for status visibility and consent actions. | High | Auth architecture assumes no candidate password/session system; if candidates need self-service history across orgs, this assumption fails and a candidate identity system becomes necessary (explicitly out of scope per [01](01-problem-space-and-scope.md)). |

## Assumptions about interview data

This is the area we are most deliberately narrowing, so it's stated explicitly:

| # | Assumption | Confidence | What breaks if wrong |
|---|---|---|---|
| A10 | Interview feedback in v1 is **structured scorecards**: a fixed or semi-fixed set of rating fields (e.g., 1–5 scale per competency) plus free-text notes. It is **not** audio/video, and it is **not** a raw transcript. | High (by design decision, not by discovery) | This is a scope decision restated as an assumption — see Scope Creep Watchlist in [01](01-problem-space-and-scope.md). If orgs need transcript-level detail, that's a v2+ conversation, not a v1 gap to silently fill. |
| A11 | Scorecard competencies/rating fields can be defined per job requisition (or a sane default set), and don't need to be freeform per interviewer. | Medium | Data model ([05-data-model.md](05-data-model.md)) assumes scorecard fields are structured and queryable, not arbitrary key-value pairs; freeform-per-interviewer would break aggregation/summarization. |
| A12 | One interview maps to one scorecard, submitted by one interviewer (panel interviews are modeled as multiple Interview records, one per interviewer, not one shared record). | Medium | Ontology ([03-ontology.md](03-ontology.md)) cardinality assumption; if panels need a single shared scorecard, the Interview↔Scorecard relationship needs to change from 1:1 to 1:many with a consolidation step. |
| A13 | Interview feedback is expected to be submitted within days of the interview, not weeks — "recency" isn't separately modeled as a data quality signal in v1. | Low | Affects whether we need staleness indicators in the analysis layer; if feedback routinely lags, the "24-hour median" success metric in [00-ideation.md](00-ideation.md) is unrealistic and analysis output may present stale data as current. |

## Assumptions about volume and scale

| # | Assumption | Confidence | What breaks if wrong |
|---|---|---|---|
| A14 | Target organizations process on the order of 10–500 applications per requisition, and 5–200 open requisitions per year. | Medium | Sizing assumptions for synchronous vs. async processing ([06-architecture.md](06-architecture.md)) and hosting choices ([07-technical-stack.md](07-technical-stack.md)); an order-of-magnitude-larger org (10,000+ applications/req) would need different search/indexing infrastructure. |
| A15 | Resume parsing and analysis do not need to complete in real time (sub-second); a latency of seconds to low minutes, processed asynchronously, is acceptable to users. | High | Justifies the async queue architecture in [06](06-architecture.md); if users expect instant structured results on upload, the UX and infra both need rework. |

## Things we do NOT yet know and must validate

These are not assumptions with a confidence level — they are open unknowns that the above assumptions are built on top of, and should be validated with real pilot organizations before further investment:

- Whether the fixed application pipeline (A4) actually matches how target organizations think about their hiring stages, or whether every org wants at least light customization.
- What fraction of real-world resumes are non-PDF/DOCX or non-English, which determines whether A5 needs to be revisited before GA rather than after.
- Whether candidates who apply to multiple organizations on Sift find it acceptable that their data is not linked/shared (A1-adjacent design decision in [03-ontology.md](03-ontology.md)) or whether they expect "apply once, reuse everywhere" behavior.
- Whether hiring managers trust a structured summarization of scorecards enough to act on it, or whether they'll insist on reading raw scorecard text regardless — this determines how much investment the analysis layer in [06-architecture.md](06-architecture.md) deserves in v1 vs. later.
- Real-world scorecard competency field needs across different job families (engineering vs. sales vs. operations) — A11 assumes a "sane default set" exists, which hasn't been validated against multiple job families.

## Open Questions

- Should we run a structured pilot (2–3 design-partner organizations) specifically to validate A4, A7, and A11 before finalizing the data model, or proceed on best-guess defaults and adjust post-launch?
- Is there a minimum viable multi-language support bar (e.g., resume text extraction working regardless of language, even if parsing/analysis is English-only) we should build into v1 to avoid a costly retrofit?
