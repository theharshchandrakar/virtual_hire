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

## Assumptions about RAG search and the LLM crew

| # | Assumption | Confidence | What breaks if wrong |
|---|---|---|---|
| A16 | Resume text can be chunked and embedded such that semantic similarity search returns meaningfully relevant results for queries like "candidates with Kubernetes experience" — i.e., off-the-shelf embedding models capture enough domain signal without per-org fine-tuning. | Medium | Core premise of the RAG search feature in [06-architecture.md](06-architecture.md); if embeddings underperform on resume-style text, search quality degrades and the feature reduces to keyword search, undermining the "semantic" value proposition. |
| A17 | A multi-step LLM crew (extraction → summarization → reasoning agents, each possibly a different model) completing in tens of seconds is an acceptable latency for the on-demand analysis and search-with-rationale flows. | Medium | Extends A15; if orchestrating multiple sequential model calls pushes latency past what HR users tolerate for an interactive search, the crew pipeline needs parallelization or a faster/smaller default path. |
| A18 | HR-initiated semantic search queries are low-volume/interactive (a recruiter typing a handful of queries per session), not batch/bulk scoring of an entire candidate pool on a schedule. | Medium | Sizing assumption for vector index query load and LLM crew cost; if usage becomes bulk/scheduled, this starts to resemble the autonomous-ranking pattern explicitly excluded in [01-problem-space-and-scope.md](01-problem-space-and-scope.md) and needs a policy decision, not just a scaling fix. |
| A19 | A single shared embedding model and a fixed small set of LLMs (per task, see [07-technical-stack.md](07-technical-stack.md)) are sufficient for v1 — no need for per-organization model selection or fine-tuning. | High | If specific organizations need domain-tuned matching (e.g., highly specialized technical roles), v1's shared-model approach may underperform for them specifically; treated as an accepted v1 limitation, not a silent failure. |
| A20 | Sending resume text and scorecard content to a third-party hosted LLM/embedding provider (for parsing, embedding, summarization, and reasoning) is acceptable to candidates and organizations under the consent flow in [08-privacy-and-compliance.md](08-privacy-and-compliance.md), subject to a standard data-processing agreement with that provider. | Medium | If an organization's compliance posture prohibits sending candidate PII to a third-party model provider (e.g., specific regulated industries or jurisdictions), the shared hosted-LLM architecture in [06-architecture.md](06-architecture.md)/[07-technical-stack.md](07-technical-stack.md) would need a self-hosted or region-pinned exception path — not planned for v1. |

## Assumptions about the verdict services (Resume Analyzer, Interview Proctoring, Transcript/Assignment Reviewer)

| # | Assumption | Confidence | What breaks if wrong |
|---|---|---|---|
| A21 | Target video platforms (Zoom/Google Meet/Teams) provide either a webhook/bot API or post-call recording+transcript access sufficient to ingest proctoring signal and transcripts without Sift hosting the call itself. | Medium | [06-architecture.md](06-architecture.md)'s proctoring/transcript ingestion design assumes this; if no viable integration exists for the platform(s) target orgs actually use, ingestion needs a different mechanism, narrowing which organizations can use these services at all. |
| A22 | Both the candidate and the interviewer/HR user must explicitly consent, per the applicable jurisdiction's requirements, before proctoring is enabled for a given interview — consent is never inferred from platform usage alone. | High (by design decision) | If consent can't practically be captured from both parties before the interview starts, proctoring cannot legally run for that interview — this is a hard gate, not a soft preference, per [08-privacy-and-compliance.md](08-privacy-and-compliance.md). |
| A23 | A rubric-based deterministic scoring engine (weighted criteria matching, threshold rules) can produce meaningful sub-scores for resume-vs-requisition fit, transcript competency coverage, and proctoring integrity signals without per-organization customization in v1. | Medium | If rubrics need heavy per-org tuning to be useful, the "engineering-authored rules, not a no-code builder" scope decision in [01-problem-space-and-scope.md](01-problem-space-and-scope.md) becomes a real bottleneck, not just a v1 simplification. |
| A24 | A single large (200–300B-parameter class) model, shared across all three services as the Verdict/Judge agent, produces adequate verdict quality without a specialized or fine-tuned model per service. | Medium | If verdict quality varies too much by service type, the "one shared judge" design in [06-architecture.md](06-architecture.md) may need to become per-service, complicating the crew definition and cost model. |
| A25 | OpenRouter, as a single unified LLM gateway, provides acceptable latency, availability, and cost for both the existing crew models and the new verdict model, without needing a direct-provider fallback in v1. | Medium | If OpenRouter introduces meaningful latency overhead or its own availability risk on top of the underlying provider's, the "one gateway, no fallback" simplification in [07-technical-stack.md](07-technical-stack.md) needs revisiting — this compounds the pre-existing open question about the crew having no fallback LLM provider at all. |
| A26 | Take-home assignments, where they exist, are submitted as a file, plain text, or a repository link — never code that Sift itself executes, runs tests against, or sandboxes. | High (by design decision) | Matches the Scope Creep Watchlist entry excluding auto-grading/code-execution sandboxing in [01-problem-space-and-scope.md](01-problem-space-and-scope.md); if orgs need executed/graded code review, this assumption fails and a materially different (and riskier) infra surface becomes necessary. |
| A27 | Interview transcripts are either provided directly by the video platform's own transcription feature or generated by a speech-to-text step Sift owns — never manually typed by an HR user. | Medium | If target video platforms don't reliably provide transcripts and building/buying STT is out of budget, transcript-based review either needs manual entry (undermining the automation value prop) or an additional third-party STT vendor not yet scoped in [07-technical-stack.md](07-technical-stack.md). |
| A28 | Proctoring analysis is meaningful when computed after the fact (batch, against the recording/webhook stream), not live/real-time — "live" in "Interview Live Proctoring" describes the interview, not the analysis latency. | High (by design decision, encoded as **I15** in [04-invariants.md](04-invariants.md)) | If HR teams specifically expect real-time flags surfaced *during* the interview, this framing needs revisiting, which reopens the "no real-time intervention" non-goal in [00-ideation.md](00-ideation.md) — a materially different and higher-risk product. |

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
- Whether general-purpose embedding models produce good enough semantic search results on real resume text across varied formats and job families (A16), or whether this needs resume-specific retrieval tuning (e.g., structured-field-weighted search rather than pure full-text embedding) before it's trustworthy enough for recruiters to rely on.
- Whether any target organization's compliance requirements block sending candidate data to a third-party hosted LLM/embedding provider at all (A20) — this should be validated with pilot organizations' legal/security teams before the RAG and LLM crew pipeline is treated as a default, not an opt-in.
- **New in this revision:** which video platform(s) target organizations actually standardize on, and whether that platform's API/webhook/bot support is sufficient for A21 to hold — unvalidated, and a precondition for building the proctoring/transcript ingestion path at all.
- **New in this revision:** whether a jurisdiction-by-jurisdiction legal review can realistically clear proctoring for any pilot organization within v1's timeline (A22), or whether this is a multi-quarter effort that should decouple proctoring's ship date from the other two verdict services — see the open sequencing question in [09-roadmap.md](09-roadmap.md).

## Open Questions

- Should we run a structured pilot (2–3 design-partner organizations) specifically to validate A4, A7, and A11 before finalizing the data model, or proceed on best-guess defaults and adjust post-launch?
- Is there a minimum viable multi-language support bar (e.g., resume text extraction working regardless of language, even if parsing/analysis is English-only) we should build into v1 to avoid a costly retrofit?
- **New in this revision:** should the scoring engine's deterministic rules (A23) be reviewed/approved by legal or compliance before launch, given they materially drive a verdict that influences hiring decisions — e.g., disparate-impact review of what the resume-fit rubric actually weights?
- **New in this revision:** is one shared Verdict/Judge model (A24) actually going to produce well-calibrated `pass`/`review`/`fail` thresholds across three very different assessment types (resume fit, interview integrity, competency review), or does calibration need to be validated and tuned per service before any verdict is shown to an HR user?
