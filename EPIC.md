# Sift Backend — v1 Epics

**Purpose:** Break the backend work required for the v1 release (per [docs/09-roadmap.md](docs/09-roadmap.md)) into epics, sequenced by dependency, each traceable back to the ontology/invariants/architecture/stack docs it implements.

**Baseline (as of 2026-07-15):** The repo is scaffold-only. `app/{core,db,models,schemas,api/routes,services,workers,crew}` exist as empty packages (one `__init__.py` each); `app/main.py` has a real FastAPI instance with a `/health` route and nothing else. No models, no migrations, no endpoints, no workers, no crew agents. Every epic below starts from that empty state.

**Scope:** Backend only (FastAPI API + Celery workers + CrewAI crew + DB schema). Frontend, calendar integration, ATS export, and everything on the [Scope Creep Watchlist](docs/01-problem-space-and-scope.md) are excluded, matching the v1 "does NOT ship" row in [09-roadmap.md](docs/09-roadmap.md).

> **Revision note (2026-07-15):** the vector store moved from pgvector-inside-Postgres to a dedicated Qdrant instance (one collection per Organization). This changes E1 (no longer owns vector schema), E3 (now provisions the Qdrant collection at org-creation time), E7 (now targets Qdrant instead of a Postgres table), E10 (queries Qdrant instead of Postgres ANN), E12 (deletion now spans two systems), E13 (the I2/I11 test suite now proves Qdrant collection isolation, not RLS-on-a-vector-table), and E14 (Qdrant added to readiness checks). See [docs/06-architecture.md](docs/06-architecture.md) for the full reasoning and [CHANGELOG.md](CHANGELOG.md) for when this changed. This mirrors the corresponding rewrite of the Jira epic/stories in the `VHIRE` project.

> **Revision note (2026-07-16):** Sift's scope expanded to three parallel scored-assessment services (Resume Analyzer, Interview Live Proctoring, Interview Transcript + Assignment Reviewer), all routed through a shared deterministic Scoring Engine and a new Verdict/Judge crew agent, with **all** LLM crew model access (not just the new agent) now going through **OpenRouter** instead of direct Anthropic API calls. Seven new epics were added (**E15–E21**); **E6, E9, E10, E12, E13, E14** were revised in place. **E1 and E2 are unaffected and already implemented as of this revision** — nothing below invalidates that work; the new tables in E15 are purely additive to E1's schema. Full reasoning lives in [docs/00-ideation.md](docs/00-ideation.md) (product framing), [docs/06-architecture.md](docs/06-architecture.md) (components/flows), [docs/07-technical-stack.md](docs/07-technical-stack.md) (OpenRouter, and several deliberately-still-open vendor decisions), and [docs/08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md) (the biometric-data section, which drives E21's gating). See [CHANGELOG.md](CHANGELOG.md) for the full pivot record.

---

## Epic dependency graph

```mermaid
flowchart TD
    E1[E1 Foundational Data Layer & Migrations]
    E2[E2 Auth & Multi-Tenant Request Context]
    E3[E3 Org / HR User / Requisition Management API]
    E4[E4 Candidate & Resume Ingestion]
    E5[E5 Async Task Queue Infrastructure]
    E6[E6 Resume Parsing - Extraction Agent]
    E7[E7 Vector Store Provisioning & Embedding Pipeline - Qdrant]
    E8[E8 Application Pipeline, Interviews & Scorecards]
    E9[E9 LLM Crew - Summarization]
    E10[E10 RAG Search & Match Reasoning]
    E11[E11 Notifications]
    E12[E12 Privacy, Consent & Deletion]
    E13[E13 Multi-Tenancy Test Suite & Release Gating]
    E14[E14 Observability & Deployment Readiness]
    E15[E15 Extended Data Model - Verdicts, Transcripts, Proctoring, Assignments]
    E16[E16 Scoring Engine]
    E17[E17 Verdict/Judge Agent & OpenRouter Gateway]
    E18[E18 Resume Analyzer Verdict]
    E19[E19 Transcript Ingestion & Assignment Submission API]
    E20[E20 Transcript + Assignment Reviewer Verdict]
    E21[E21 Interview Live Proctoring - gated on legal review]

    E1 --> E2
    E2 --> E3
    E3 --> E4
    E1 --> E5
    E4 --> E5
    E5 --> E6
    E6 --> E7
    E3 --> E7
    E3 --> E8
    E4 --> E8
    E8 --> E9
    E7 --> E9
    E7 --> E10
    E9 --> E10
    E8 --> E11
    E5 --> E11
    E3 --> E12
    E8 --> E12
    E7 --> E12
    E2 --> E13
    E3 --> E13
    E7 --> E13
    E10 --> E13
    E1 --> E14
    E13 --> E14

    E1 --> E15
    E15 --> E16
    E9 --> E17
    E16 --> E17
    E15 --> E17
    E6 --> E18
    E3 --> E18
    E16 --> E18
    E17 --> E18
    E15 --> E19
    E3 --> E19
    E8 --> E19
    E19 --> E20
    E16 --> E20
    E17 --> E20
    E15 --> E21
    E16 --> E21
    E17 --> E21
    E3 --> E21
    E8 --> E21
    E21 --> E12
    E15 --> E12
    E15 --> E13
    E15 --> E14
    E21 --> E14
```

## Sequencing vs. roadmap

| Epics | Maps to [09-roadmap.md](docs/09-roadmap.md) phase | Notes |
|---|---|---|
| E1, E2 | v1a (Data model + FastAPI core) | Nothing else can start until these land. E1 is now Postgres-only. **Both are already implemented** as of this revision. |
| E3, E4, E5 | v1a / v1b boundary | E3 now also provisions each Organization's Qdrant collection — this is a new dependency E7 has on E3 that didn't exist when the vector index lived inside Postgres. |
| E6 | v1b (Ingestion + Extraction Agent parsing) | Model access via OpenRouter once E17 lands — see E17's note. |
| E7 | v1e (Qdrant collection provisioning + embedding pipeline) | Depends on both E3 (collection must exist) and E6 (parsed text to embed) — previously depended only on E6. |
| E8 | v1c (Pipeline + scorecards — backend portion only) | Can proceed in parallel with E6/E7; no data dependency between them. |
| E9, E10 | v1f / v1g (LLM crew, RAG search) | E10 now queries Qdrant, not a Postgres ANN index; both route model access via OpenRouter once E17 lands. |
| E11 | Unchanged from prior design, threaded through v1c/v1b | |
| E12 | v1 ships list ("consent + deletion flow covering embeddings") | Now a two-system deletion (Postgres + Qdrant) — see the cross-cutting risk table below. **Extended in this revision** to cover proctoring-data retention/deletion (I13) once E21 exists. |
| E13 | v1d (Multi-tenancy hardening + I2/I11 test suites) | The vector-isolation half of this suite now proves Qdrant collection-per-organization isolation, not RLS on a shared table. **Extended in this revision** to cover the six new tables E15 adds — same RLS mechanism, no new test *design*, just more tables. |
| E14 | Cuts across v1a→v1g | Qdrant connectivity added to readiness checks. **Extended in this revision** for proctoring ingestion health and stuck-`proctoring_session` alerting. |
| **E15–E20** **[New]** | v1 "Verdict Services" (see [09-roadmap.md](docs/09-roadmap.md)'s new dedicated Gantt section) | Ship as part of v1 proper, not gated the way E21 is — no new legal-category data involved. |
| **E21** **[New]** | v1-proctoring, a **separate, legally-gated roadmap row** — not part of v1's exit criteria | The one epic in this document whose ship date for any given organization is not primarily an engineering timeline — see its Definition of Done. |

---

## E1 — Foundational Data Layer & Migrations

**Goal:** Stand up the real relational schema from [docs/05-data-model.md](docs/05-data-model.md) as SQLAlchemy models with Alembic migrations. **This epic no longer owns any vector/embedding schema** — that moved to E7 and targets Qdrant, a separate system with its own provisioning path, not an Alembic migration.

**Key deliverables:**
- `app/db/base.py` — async engine/session setup, `DATABASE_URL` from settings.
- `app/models/` — one SQLAlchemy model per Postgres table: `organizations`, `hr_users`, `job_requisitions`, `candidates`, `resumes` (including the new `embedding_status`/`embedding_error` columns), `applications`, `interviews`, `scorecards`, `analysis_outputs`, `audit_log`, with native Postgres enums and the composite/partial unique constraints (e.g., `applications` unique-while-active).
- Alembic migration(s): create all tables, the cross-table CHECK trigger enforcing I3, and the "no UPDATE on submitted scorecards" DB-role revocation for I4. **No `CREATE EXTENSION vector`, no HNSW index, no `resume_chunks` table** — all removed from this epic's scope in the 2026-07-15 revision.
- `app/core/config.py` — Pydantic settings loading everything already listed in `.env.example`, including the new `QDRANT_URL`/`QDRANT_API_KEY`.

**Depends on:** Nothing (first epic).

**Docs/invariants:** [03-ontology.md](docs/03-ontology.md), [05-data-model.md](docs/05-data-model.md), I1–I10 in [04-invariants.md](docs/04-invariants.md) (I11 is now primarily E7/E13's concern, not this epic's).

**Definition of done:** `alembic upgrade head` runs clean against a local Postgres (no `pgvector` extension required); every Postgres table/constraint in 05-data-model.md exists; RLS is *on* but not yet exercised by app code (that's E2/E13).

---

## E2 — Auth & Multi-Tenant Request Context

**Goal:** Every authenticated request resolves to exactly one `organization_id`, sourced only from a verified session/token — never a client-supplied parameter — and that org_id is injected as (a) the DB session variable RLS depends on, and (b) the Qdrant collection name resolved for any vector operation.

**Key deliverables:**
- JWT validation against the managed auth provider's JWKS endpoint (`AUTH_JWKS_URL`/`AUTH_JWT_ISSUER`/`AUTH_JWT_AUDIENCE`), producing an `HRUser` + `organization_id` request context.
- FastAPI dependency that opens a DB transaction and `SET LOCAL app.current_org_id = :org_id` before any query runs, so RLS is live for every request.
- A second resolution step off the same request context: `organization_id` → Qdrant collection name (`resumechunks_{organization_id}`) — this is the vector-store equivalent of the RLS session variable, and must be derived the same way (server-side, from the authenticated session, never from a client-supplied field).
- Candidate-side auth: magic-link / time-limited email token issuance and verification (no password), per A9.
- Role enforcement scaffolding (`hr_generalist`, `recruiter`, `hiring_manager`) for later per-route authorization.

**Depends on:** E1 (models/session plumbing must exist to set org context against).

**Docs/invariants:** I2, I3, I11 (collection-resolution half), [06-architecture.md](docs/06-architecture.md) Multi-tenancy section, [07-technical-stack.md](docs/07-technical-stack.md) auth rows.

**Definition of done:** No route can read or write data without a resolved org context; a request with a forged/omitted org claim is rejected before touching either Postgres or Qdrant; this is the dependency every other epic's endpoints/workers build on for org scoping.

---

## E3 — Organization / HR User / Requisition Management API

**Goal:** CRUD surface for the entities HR teams manage directly: organizations (admin-only), HR user invitation/lifecycle, job requisitions. **New in this revision:** Organization creation now also provisions that org's dedicated Qdrant collection, and deactivation tears it down — this lifecycle coupling didn't exist when the vector index lived inside the shared Postgres instance.

**Key deliverables:**
- `POST/GET /organizations` (bootstrap-only in v1, likely admin-tooling not self-serve signup).
- **Qdrant collection provisioning on Organization creation:** create `resumechunks_{organization_id}` (cosine distance, vector size 1024) in the same request-handling flow as the Postgres row insert — synchronous, per [06-architecture.md](docs/06-architecture.md)'s sync/async boundary table. Needs an explicit compensating action if Postgres commits but Qdrant provisioning fails (or the reverse) — resolve the open question in [06-architecture.md](docs/06-architecture.md) before building this, don't improvise it mid-implementation.
- **Qdrant collection teardown on Organization deactivation:** delete or archive the org's collection — exact behavior (immediate delete vs. retained-but-inaccessible) should follow whatever retention decision [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md) settles on for deactivated orgs.
- HR user invite → active → deactivated lifecycle endpoints.
- Job requisition CRUD, `status` transitions (`draft → open → on_hold/filled/cancelled`), `scorecard_template` validation.
- Pydantic request/response schemas in `app/schemas/`.

**Depends on:** E2.

**Docs/invariants:** [03-ontology.md](docs/03-ontology.md) (HRUser, JobRequisition lifecycle), A2/A3/A11 in [02-assumptions.md](docs/02-assumptions.md), I2/I11 (Qdrant collection lifecycle), [05-data-model.md](docs/05-data-model.md) open question on Organization/collection lifecycle coupling.

**Definition of done:** An HR user can be invited, log in, and create/manage a requisition end-to-end through the API, fully org-scoped; creating an Organization leaves it with a working, empty Qdrant collection ready for E7 to write into.

---

## E4 — Candidate & Resume Ingestion

**Goal:** The synchronous half of the submission flow in [06-architecture.md](docs/06-architecture.md)'s sequence diagram: accept a resume file, store it, create/reuse the Candidate, create the Resume and Application rows, and enqueue parsing.

**Key deliverables:**
- `Ingestion Service` (`app/services/ingestion.py`) run inline on the request path per the architecture doc (not a separate deploy).
- `POST` resume-submission endpoint: candidate email/name intake, dedup-by-email per A8, file upload to S3 with `{org_id}/{resume_id}/{filename}` namespaced keys, signed-URL generation for later retrieval.
- Row creation: `Candidate` (create-or-reuse), `Resume` (`status=uploaded`, `embedding_status=not_embedded`), `Application` (`status=submitted`) in one transaction, respecting the partial-unique constraint (one active Application per Candidate+Requisition).
- Enqueue `parse_resume` job (stubbed until E5 exists, wired for real once it does).
- Web + email-in intake channels per the v1 ships list.

**Depends on:** E3 (needs Requisition to attach the Application to), E2.

**Docs/invariants:** I1, I3, A8, [06-architecture.md](docs/06-architecture.md) submission sequence, [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md) consent capture at intake.

**Definition of done:** Submitting a resume returns `202 Accepted` with Candidate/Resume/Application rows correctly linked and org-scoped; the file is retrievable only via a scoped signed URL; a job is enqueued (even if no worker consumes it yet).

---

## E5 — Async Task Queue Infrastructure

**Goal:** The Celery + Redis backbone every downstream worker epic (E6, E7, E9, E10, E11) builds on, including how org context travels with a job.

**Key deliverables:**
- `app/workers/celery_app.py` — Celery app config against `REDIS_URL`, task routing/queues per worker type (parsing, embedding, crew, notification) matching the "separate Fargate task definitions per worker type" decision in [07-technical-stack.md](docs/07-technical-stack.md).
- A shared task base class that requires an explicit `organization_id` in every job payload and, before the task body runs, both sets `app.current_org_id` for Postgres and resolves the org's Qdrant collection name for any task that needs vector access — the async-path equivalent of E2's request-context dependency for *both* storage systems now, not just one.
- Retry/backoff policy conventions for LLM-call-bound tasks (crew-orchestrated task treated as one retryable unit for v1).
- Local dev entrypoint (`celery -A app.workers.celery_app worker`) documented in README/CLAUDE.md equivalent.

**Depends on:** E1, E4 (first real producer of jobs).

**Docs/invariants:** [06-architecture.md](docs/06-architecture.md) sync/async boundary table, I2/I11 (org context must not leak or get dropped between enqueue and execution, for either Postgres or Qdrant).

**Definition of done:** A test task round-trips through Redis, executes with the correct org context set for both storage systems, and a task raising an exception is retried per policy rather than silently dropped.

---

## E6 — Resume Parsing (Extraction Agent)

**Goal:** The Parsing Worker: fetch the file, run the Extraction Agent (Claude Haiku 4.5), write `parsed_data`, enqueue embedding. **Unchanged by the Qdrant pivot** — this epic never touched vector storage.

**Key deliverables:**
- `app/crew/agents/extraction.py` — CrewAI agent bound to Haiku 4.5 per the fixed model assignment in [07-technical-stack.md](docs/07-technical-stack.md).
- `parse_resume` Celery task: fetch from S3 → text extraction → structured field extraction (work history, education, skills) → write `resumes.parsed_data`, `status=parsed` → enqueue `embed_resume`.
- Failure path: any extraction exception sets `status=parse_failed` with `parse_error` populated — never left stuck in `parsing` (I6).
- `resumes.status` is worker-written only; confirm no API route exposes direct client writes to it.

**Depends on:** E5.

**Docs/invariants:** I6, [06-architecture.md](docs/06-architecture.md) Parsing Worker row, [07-technical-stack.md](docs/07-technical-stack.md) model assignment.

**Definition of done:** A submitted resume reaches `status=parsed` with populated `parsed_data` on the happy path, and reaches `status=parse_failed` (not stuck) on a forced failure.

**[Revision note 2026-07-16]:** the Extraction Agent's model call now goes through **OpenRouter** rather than the Anthropic API directly, per the stack revision in [07-technical-stack.md](docs/07-technical-stack.md) — the model config layer this depends on is built in **E17**. If E6 is implemented before E17, use a direct model-ID placeholder and revisit at E17; if implemented after, use E17's config layer from the start.

---

## E7 — Vector Store Provisioning & Embedding Pipeline (Qdrant)

**Goal:** Chunk parsed resume text, embed each chunk, and upsert into the candidate's organization's dedicated Qdrant collection — this epic replaces the prior "Embedding Pipeline (pgvector)" epic entirely; the storage target changed, not just an implementation detail underneath the same schema.

**Key deliverables:**
- `app/services/vector_store.py` — a thin Qdrant client wrapper: collection provisioning helper (used by E3 at org-creation time), point upsert/delete-by-resume, and the similarity-search call E10 will use. Centralizing this is what lets the embedding-dimension/model-version open question in [07-technical-stack.md](docs/07-technical-stack.md) stay a one-place change later.
- `app/services/chunking.py` — chunk size/overlap strategy for resume text (an implementation-detail tuning parameter per [05-data-model.md](docs/05-data-model.md); pick a starting value, e.g. ~500 tokens / 50 overlap, as a service-config constant).
- `embed_resume` Celery task: chunk → call Voyage AI (`voyage-3`) per chunk → upsert points into `resumechunks_{organization_id}` (deterministic point ID from `(resume_id, chunk_index)`, so re-embedding is a plain upsert, not a separate delete-then-insert) → write `resumes.embedding_status=embedded` (or `embed_failed` with `embedding_error` populated) back to Postgres.
- Every point payload includes a redundant `organization_id` field (belt-and-suspenders filter, per I2/I11), even though the collection itself is already org-scoped.

**Depends on:** E6 (parsed text to embed), E3 (the org's Qdrant collection must already be provisioned).

**Docs/invariants:** I11, the "Vector store (Qdrant)" section of [05-data-model.md](docs/05-data-model.md), Embedding Worker row in [06-architecture.md](docs/06-architecture.md).

**Definition of done:** A parsed resume produces points in its organization's Qdrant collection with correct payload fields and 1024-dim embeddings; re-running embedding on the same resume replaces rather than duplicates points (verify via the deterministic point-ID upsert); `resumes.embedding_status` reflects the outcome; a same-org smoke query against the collection returns the expected chunks (full cross-tenant proof is E13's job).

---

## E8 — Application Pipeline, Interviews & Scorecards

**Goal:** The backend half of "pipeline + scorecards" — status transitions, interview scheduling metadata, and scorecard submission/amendment with full audit trail. **Unaffected by the Qdrant pivot** — this epic has no vector-store dependency and can run in parallel with E6/E7.

**Key deliverables:**
- Application status-transition endpoint backed by an explicit state machine matching the diagram in [04-invariants.md](docs/04-invariants.md) exactly — reject any (from, to) pair not on that diagram (I5).
- Interview CRUD (`scheduled/completed/cancelled/no_show`), always referencing exactly one Application (I7).
- Scorecard submission endpoint: create as `draft`, transition to `submitted` (locks further direct writes), enforced 1:1 with Interview via the DB unique constraint (I8).
- Scorecard amendment endpoint (distinct from update): writes the change plus an `audit_log` row in the same transaction, preserving the original (I4).
- `audit_log` write path — append-only, no update/delete exposed anywhere in the API.

**Depends on:** E3, E4.

**Docs/invariants:** I4, I5, I7, I8, state diagram in [04-invariants.md](docs/04-invariants.md), `scorecards`/`interviews`/`audit_log` tables in [05-data-model.md](docs/05-data-model.md).

**Definition of done:** State-machine unit tests enumerate every (from, to) pair from the diagram and only the valid ones succeed; submitting then amending a scorecard leaves both the original and an audit_log entry queryable; a direct update attempt on a submitted scorecard is rejected at the DB layer, not just the API layer.

---

## E9 — LLM Crew: Summarization

**Goal:** On-demand candidate/Application summary generation — the Summarizer Agent half of the LLM crew, gated so it only ever sees submitted scorecards (I10). **Data-fetch step is unaffected by the Qdrant pivot** (it reads Postgres scorecards, not vectors), but this epic now formally depends on E7 since it shares a crew definition with E10.

**Key deliverables:**
- `app/crew/agents/summarizer.py` — CrewAI agent bound to Sonnet 5.
- `app/crew/crew.py` — the shared crew definition referenced by both this epic and E10.
- Data-fetch step that queries `scorecards WHERE status = 'submitted'` exclusively before building agent context — the concrete I10 enforcement point.
- `generate_summary` Celery task: on-demand trigger → write/upsert `analysis_outputs` (`summary`, `source_scorecard_ids`, `crew_run` model-provenance metadata, `generated_at`).
- Staleness handling: flip `analysis_outputs.stale = true` when a new Scorecard is submitted for that Application after `generated_at`; lazy regeneration triggered on next view request.
- `GET` endpoint to fetch (and lazily trigger regeneration of) an Application's current summary.

**Depends on:** E8 (needs submitted scorecards to summarize), E7 (shared crew scaffolding).

**Docs/invariants:** I10, `analysis_outputs` table, Summarizer row in [06-architecture.md](docs/06-architecture.md), model assignment in [07-technical-stack.md](docs/07-technical-stack.md).

**Definition of done:** Integration test: create a draft scorecard alongside submitted ones for the same Application, trigger analysis, assert the draft's content appears nowhere in the generated output or the crew's retrieved context; regenerating overwrites in place (no history table).

**[Revision note 2026-07-16]:** the Summarizer Agent's model call now goes through **OpenRouter**, same note as E6. `app/crew/crew.py`'s shared crew definition, built here, is what **E17** extends with the fourth (Verdict/Judge) agent — E9 should build `crew.py` with that extension in mind (e.g., don't hardcode an assumption of exactly three agents anywhere it'd be awkward to add a fourth).

---

## E10 — RAG Search & Match Reasoning

**Goal:** HR-initiated, query-scoped candidate search: embed the query, run a similarity search against the requesting org's Qdrant collection only, then have the Reasoning Agent produce a per-candidate rationale — never a blended ranking score.

**Key deliverables:**
- `app/crew/agents/reasoning.py` — CrewAI agent bound to Opus 4.8.
- Search endpoint: accepts free-text query + optional `requisition_id`, enqueues a search job with `org_id` in the payload (never inferred from content).
- `search` Celery task: embed query (Voyage) → similarity search against `resumechunks_{org_id}` **only** (collection resolved server-side from the job's org_id, per E2/E5's context-propagation design) with the redundant `organization_id` payload filter also applied → Reasoning Agent call over the retrieved chunks only → write/refresh `analysis_outputs.match_rationale` for matched Applications.
- Result delivery: short-polling (`GET /search/{job_id}`) or an equivalent status-check endpoint, per the sync/async boundary table — full streaming is an explicit open question in [06-architecture.md](docs/06-architecture.md) and can be deferred past v1.
- Response shape: ranked-by-relevance list of candidates with rationale text and a link back to the full record — no single blended score field.

**Depends on:** E7, E9 (shares the crew definition and `analysis_outputs` write path).

**Docs/invariants:** I11 (the highest-risk new surface — now enforced by Qdrant collection-per-organization, not RLS, per [04-invariants.md](docs/04-invariants.md)'s 2026-07-15 revision), RAG search sequence diagram in [06-architecture.md](docs/06-architecture.md).

**Definition of done:** Seed two organizations' Qdrant collections with semantically near-identical resume content; search as Org A; assert zero Org B points are ever retrieved or reasoned over, **and** assert that a request carrying a forged/spoofed `org_id` cannot cause the search job to resolve to a different organization's collection; response contains rationale text, not a bare ranking score.

**[Revision note 2026-07-16]:** the Reasoning Agent's model call now goes through **OpenRouter**, same note as E6/E9.

---

## E11 — Notifications

**Goal:** Transactional email on pipeline state changes. **Unaffected by the Qdrant pivot.**

**Key deliverables:**
- `notify` Celery task consuming events from Application status transitions and Scorecard submission.
- Integration with the transactional email provider (Postmark/SES per [07-technical-stack.md](docs/07-technical-stack.md)) via `EMAIL_PROVIDER_API_KEY`.
- Template set for the minimum v1 notification set (submission confirmation, status change, interview scheduled).

**Depends on:** E5, E8 (the events it reacts to).

**Docs/invariants:** Notification Worker row in [06-architecture.md](docs/06-architecture.md), async classification in the sync/async boundary table.

**Definition of done:** An Application status transition or scorecard submission reliably enqueues and sends the corresponding email in a dev/sandbox provider setup, without blocking the triggering API request.

---

## E12 — Privacy, Consent & Deletion

**Goal:** Implement I9's right-to-be-forgotten routine end-to-end. **This epic changed materially in this revision:** deletion now spans two systems (Postgres + Qdrant) instead of one transactional database, which is a new consistency risk to design for, not just an implementation detail to swap.

**Key deliverables:**
- Consent capture at resume submission (candidate-facing disclosure of AI processing, per [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md)).
- Deletion endpoint/routine: anonymize `candidates.full_name/email/phone` in place, set `pii_deleted_at`, anonymize free-text scorecard fields referencing the candidate by name — all without deleting rows (preserves I9's aggregate-analytics guarantee) — this half stays a single Postgres transaction.
- **Cross-system delete step:** after (or as part of) the Postgres transaction, delete all Qdrant points for the candidate's resumes from their organization's collection, plus the resume file in object storage. **Must include an explicit compensating-action design** (retry queue with alerting, or a reconciliation job diffing "deleted in Postgres" against "still present in Qdrant") — see the new risk called out in [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md); do not ship this as a best-effort fire-and-forget call.
- Retention-window enforcement per the retention table in [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md), if any automatic (non-request-driven) retention expiry is in v1 scope — confirm with the product owner before building.
- **[New 2026-07-16]** Separate two-party consent capture for interview proctoring (`proctoring_sessions.candidate_consented_at`/`interviewer_consented_at`), distinct from and in addition to resume-submission consent — see [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md)'s dedicated consent-flow section.
- **[New 2026-07-16]** I13 enforcement: a scheduled retention job hard-deleting `proctoring_events` past its (legal-review-pending) retention window, plus extending the I9 deletion routine to hard-delete `proctoring_events`, `verdicts`, `transcripts.text`, and `assignment_submissions` files for a deleted Candidate — same "derived data, hard-delete not anonymize" treatment already applied to `analysis_outputs`/Qdrant points.

**Depends on:** E3 (candidate ownership), E8, E7 (points to purge), **E15 (new tables to purge), E21 (proctoring data specifically — though the retention *job* for `proctoring_events` should ship as part of E21 itself, not wait on this epic, given I13's independent urgency)**.

**Docs/invariants:** I9, **I13**, [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md) deletion flow diagram, its two-system consistency risk section, and its new "Interview proctoring — biometric data" section.

**Definition of done:** Integration test: trigger deletion, assert PII fields are anonymized in Postgres and all corresponding points are gone from the org's Qdrant collection, assert aggregate requisition funnel counts are unchanged; a second test forcing the Qdrant delete call to fail confirms the compensating-action path (retry/alert/reconciliation) actually fires rather than silently leaving orphaned points. **[New]** A third test: seed `proctoring_events` older than the retention window, run the scheduled retention job, assert they're purged without a deletion request; a fourth test: trigger I9 deletion, assert `proctoring_events`/`verdicts`/`transcripts`/`assignment_submissions` are all gone for that candidate.

---

## E13 — Multi-Tenancy Test Suite & Release Gating

**Goal:** The automated cross-tenant test suite that [04-invariants.md](docs/04-invariants.md) and [09-roadmap.md](docs/09-roadmap.md) both call a release blocker — covering I2 (Postgres relational data) and I11 (Qdrant vector search). **The I11 half of this suite is a materially different test design in this revision:** it now proves collection-per-organization structural isolation plus collection-resolution correctness, not "does the RLS policy filter rows correctly."

**Key deliverables:**
- Test harness: seed two organizations with overlapping/near-identical data, including semantically similar resumes embedded into each organization's own Qdrant collection.
- I2 suite: authenticated as Org A, attempt to read every Org B entity by ID across every resource type, assert 404/denied on all of them.
- I11 suite: (a) run a vector similarity search as Org A seeded to be a near-perfect semantic match for Org B content, assert zero Org B points are returned regardless of similarity score; (b) attempt to construct a request/job with a spoofed or manipulated `org_id` and assert it cannot cause collection resolution to point at another organization's collection — this second case is new and specific to the collection-per-org design, distinct from the old "does the query filter correctly" test shape.
- Wire this suite into CI as a required, non-skippable check gating merges to main / release builds.
- **[New 2026-07-16]** Extend the I2 suite's resource-type coverage to the six tables E15 adds (`transcripts`, `proctoring_sessions`, `proctoring_events`, `assignments`, `assignment_submissions`, `verdicts`) — no new test *design* needed (same RLS mechanism as every other table), just extend the existing parametrized resource-type list.

**Depends on:** E2, E3 (collection provisioning must exist to seed test collections), E7, E10, **E15 (new tables to include in the I2 sweep)**.

**Docs/invariants:** I2, I11, the v1→v2 exit criteria in [09-roadmap.md](docs/09-roadmap.md).

**Definition of done:** Suite runs in CI, fails the build on any cross-tenant leak in either Postgres or Qdrant, and is documented as a required check. **[New]** The I2 resource-type sweep includes all six new tables, not just the original ten.

---

## E14 — Observability & Deployment Readiness

**Goal:** The minimum operational scaffolding needed to run this in a pilot: structured logging, health checks per worker type and per storage dependency, error tracking, and deployable configs.

**Key deliverables:**
- Structured logging (org_id, request_id/job_id correlation) across API and all worker types.
- `/health` (already stubbed) extended with a real readiness check — **now covering both Postgres and Qdrant connectivity**, not just Postgres; equivalent liveness signal for each Celery worker type.
- Error tracking integration (e.g., Sentry) for both API and worker processes.
- The monitoring alert for resumes stuck in `parsing` past a timeout threshold (I6), plus a new alert for resumes stuck in `embedding_status=embedding` past a timeout — the Qdrant-side analog that didn't exist as a distinct concern when embedding was a synchronous-feeling part of the same Postgres write path.
- Deployment configs: separate task definitions for API, parsing worker, embedding worker, crew worker, notification worker, plus Qdrant Cloud connection/credential management as a distinct operational concern from RDS/ElastiCache.
- **[New 2026-07-16]** `/health` readiness check extended to cover OpenRouter connectivity (a new hard external dependency for *every* crew agent, not just one). A monitoring alert for `proctoring_sessions` stuck in `analyzing` past a timeout threshold — the proctoring-side analog of the existing `parsing`/`embedding` stuck-state alerts. Separate task definitions added for the Proctoring Analysis Worker and Transcript & Assignment Reviewer Worker.

**Depends on:** E1 (baseline), E13 (nothing ships to a pilot without the isolation suite green), **E15 (new tables the health/alerting checks cover), E21 (proctoring-specific alerting)**.

**Docs/invariants:** I6 operational enforcement note, Hosting row in [07-technical-stack.md](docs/07-technical-stack.md), **I13's operational retention-job monitoring**.

**Definition of done:** Every process type can be started independently with its own health signal; readiness check fails loudly if Qdrant is unreachable, not just if Postgres is; a resume stuck in `parsing` or stuck in `embedding` triggers an alert; API and worker errors surface in a trackable place, not just stdout.

---

## E15 — Extended Data Model: Verdicts, Transcripts, Proctoring, Assignments **[New 2026-07-16]**

**Goal:** Stand up the six new Postgres tables from [docs/05-data-model.md](docs/05-data-model.md)'s "Verdict-service tables" section as SQLAlchemy models with an Alembic migration — the E1-equivalent foundation for every epic below. Purely additive to E1's schema; no existing table changes.

**Key deliverables:**
- `app/models/` additions: `transcripts`, `proctoring_sessions`, `proctoring_events`, `assignments`, `assignment_submissions`, `verdicts`, plus their native Postgres enums.
- Alembic migration: create all six tables, RLS policies on each (same pattern as E1's migration), the `applications`/`assignments` org-consistency trigger (I3 pattern extended), and the `verdicts` `resume_id`/`interview_id` exclusivity + same-org CHECK trigger described in [05-data-model.md](docs/05-data-model.md).
- `UNIQUE (application_id, assignment_id)` on `assignment_submissions`, `UNIQUE (application_id, service_type)` on `verdicts`, `UNIQUE (interview_id)` on `transcripts`/`proctoring_sessions`.

**Depends on:** E1 (extends its schema/migration chain; no other epic dependency — job_requisitions/applications/interviews/candidates/resumes already exist).

**Docs/invariants:** [05-data-model.md](docs/05-data-model.md)'s Verdict-service tables section, I2 (RLS on the new tables), I12–I15 (schema-level pieces: `deterministic_score NOT NULL`, etc.).

**Definition of done:** `alembic upgrade head` runs clean with all six new tables present; every constraint/trigger in the data-model doc's description exists; RLS is *on* for all six (same "not yet exercised by app code" caveat E1 carried).

---

## E16 — Scoring Engine **[New 2026-07-16]**

**Goal:** The shared, deterministic rules framework every one of the three verdict services runs through before any model call — the concrete implementation of **I12**'s "Judge never runs without a preceding Scoring Engine result."

**Key deliverables:**
- `app/services/scoring/` — one rule module per service type (`resume_fit.py`, `proctoring_integrity.py`, `transcript_assignment.py`), each a pure function taking structured input (parsed resume + requisition, proctoring events, transcript + rubric + assignment submission respectively) and returning a structured sub-score/flag payload matching `verdicts.deterministic_score`'s JSONB shape.
- Rule definitions are engineering-authored and versioned in code, per A23 — no config-table/no-code builder in v1 (see the open question in [06-architecture.md](docs/06-architecture.md) about where this should live, resolved here as "code").
- No model calls anywhere in this package — fully deterministic and unit-testable without mocking an LLM, by design.

**Depends on:** E15 (tables to read from/shape output against).

**Docs/invariants:** I12, A23 in [02-assumptions.md](docs/02-assumptions.md), the Scoring Engine component in [06-architecture.md](docs/06-architecture.md).

**Definition of done:** Each of the three rule modules has unit tests covering its scoring logic in isolation (no DB, no model); calling any rule module twice with identical input produces identical output (determinism is directly tested, not assumed).

---

## E17 — Verdict/Judge Agent & OpenRouter Gateway **[New 2026-07-16]**

**Goal:** Two things bundled because they're the same underlying change: (1) migrate all LLM crew model access to OpenRouter, and (2) add the Verdict/Judge agent — the fourth crew role — that every verdict service calls after the Scoring Engine runs.

**Key deliverables:**
- Model configuration layer (`app/crew/models.py` or equivalent): every crew agent's model ID becomes an OpenRouter-routed identifier (`openrouter/anthropic/claude-...`) via LiteLLM's built-in provider prefix, reading `OPENROUTER_API_KEY` from settings. This is the layer E6/E9/E10's agents (whichever land first) point at.
- `app/crew/agents/judge.py` — the Verdict/Judge agent, bound to the 200–300B-class model named in [07-technical-stack.md](docs/07-technical-stack.md) once that open question is resolved.
- Extend `app/crew/crew.py` (built in E9) with the Judge agent as a fourth role, callable from any of the three verdict-generation entry points (E18/E20/E21).
- The Judge agent's task signature always requires a `deterministic_score` argument (the Scoring Engine's output) — no code path exists to invoke it without one, the concrete enforcement point for **I12**.
- `crew_run` JSONB provenance recording extended to include which OpenRouter model ID served the Judge role, same convention as the existing three roles.

**Depends on:** E9 (crew scaffolding to extend), E16 (Scoring Engine output shape must be defined for the Judge's input contract), E15 (`verdicts` table to write to).

**Docs/invariants:** I12, the OpenRouter revision note in [07-technical-stack.md](docs/07-technical-stack.md) and [06-architecture.md](docs/06-architecture.md).

**Definition of done:** A test double proves the Judge agent cannot be invoked without a preceding scoring-engine-shaped argument (I12, enforced at the function-signature/contract level, not just by convention); all four crew roles (Extraction, Summarizer, Reasoning, Judge) resolve their model via the OpenRouter config layer, confirmed by inspecting the actual model ID each call is made with in a test.

---

## E18 — Resume Analyzer Verdict **[New 2026-07-16]**

**Goal:** The first of the three verdict services: score a parsed resume against its requisition's requirements and produce a `pass`/`review`/`fail` verdict with narrative.

**Key deliverables:**
- `generate_resume_verdict` Celery task: read `Resume.parsed_data` + `JobRequisition` (title, department, any structured requirements) → Scoring Engine (`resume_fit` rules) → Judge agent call → write `verdicts` (`service_type=resume_analysis`).
- `GET` endpoint to fetch (and lazily trigger regeneration of) an Application's Resume Analyzer verdict, mirroring E9's summary-fetch endpoint pattern.
- Staleness handling: flip `verdicts.stale = true` if the Resume is re-parsed after `generated_at` (mirrors `analysis_outputs`' staleness pattern).

**Depends on:** E6 (parsed resume data), E3 (requisition data), E16, E17.

**Docs/invariants:** I12, the Resume Analyzer row in [00-ideation.md](docs/00-ideation.md), `verdicts` table in [05-data-model.md](docs/05-data-model.md).

**Definition of done:** A parsed Resume with a linked requisition produces a `verdicts` row with a populated `deterministic_score` and narrative; the endpoint returns `pass`/`review`/`fail` plus narrative, never a bare numeric score in the response shape.

---

## E19 — Transcript Ingestion & Assignment Submission API **[New 2026-07-16]**

**Goal:** The synchronous/ingestion half of the Transcript + Assignment Reviewer service: get a transcript into Postgres, and let candidates submit assignments.

**Key deliverables:**
- `ingest_transcript` Celery task: triggered by a video-platform webhook/poll (platform-provided transcript) or, absent one, an STT step per A27 (exact STT vendor TBD, see [07-technical-stack.md](docs/07-technical-stack.md)) → write `transcripts` (`status=available`).
- `POST` assignment-submission endpoint (candidate-facing, magic-link authenticated per E2's candidate auth path): file/text/URL intake per A26 (no code execution), row creation in `assignment_submissions`.
- `Assignment` CRUD (HR-facing, per requisition): `draft → published → archived` lifecycle.

**Depends on:** E15, E3 (requisitions to attach Assignments to), E8 (Interviews to attach Transcripts to).

**Docs/invariants:** A26, A27, `transcripts`/`assignments`/`assignment_submissions` tables in [05-data-model.md](docs/05-data-model.md).

**Definition of done:** A completed Interview with a platform-provided transcript reaches `transcripts.status=available` without manual entry; a candidate can submit an assignment via magic link and the row is correctly linked to their Application.

---

## E20 — Transcript + Assignment Reviewer Verdict **[New 2026-07-16]**

**Goal:** The second verdict service: score a transcript (and any assignment submission) against a competency rubric.

**Key deliverables:**
- `generate_transcript_verdict` Celery task: gated on `Interview.status = completed` (**I14** — reject and write no `verdicts` row otherwise) → read `transcripts.text` + `assignment_submissions` (if any) + the Assignment's `rubric` → Scoring Engine (`transcript_assignment` rules) → Judge agent call → write `verdicts` (`service_type=transcript_assignment_review`).
- `GET` endpoint mirroring E18's pattern.
- Staleness handling: flip `stale=true` if a new Scorecard is submitted for the same Application after `generated_at` (same trigger condition I10 already uses for `analysis_outputs`).

**Depends on:** E19 (transcript/assignment data), E16, E17.

**Docs/invariants:** I14, `verdicts` table in [05-data-model.md](docs/05-data-model.md).

**Definition of done:** Integration test: attempt verdict generation against a `scheduled`/`cancelled`/`no_show` Interview, assert rejection with no `verdicts` row written (I14); against a `completed` Interview, assert a verdict is produced.

---

## E21 — Interview Live Proctoring **[New 2026-07-16 — gated on legal review, see below]**

**Goal:** The third verdict service, and the one this document's own [09-roadmap.md](docs/09-roadmap.md) sequences separately from the rest of v1: ingest signal from an external video platform for a completed interview, run biometric integrity detection, and produce a proctoring verdict — never in real time, never intervening in the live call (**I15**).

**Key deliverables:**
- Proctoring Ingestion Service: webhook/bot receiver for the external video platform (Zoom/Meet/Teams — exact platform TBD, see [07-technical-stack.md](docs/07-technical-stack.md)); creates/updates `proctoring_sessions`. **Must verify inbound webhook signatures** — an unverified webhook is a real spoofing surface, per the open question in [06-architecture.md](docs/06-architecture.md).
- Two-party consent enforcement: no `proctoring_events` row can be written unless both `candidate_consented_at` and `interviewer_consented_at` are set on the owning `proctoring_session` — enforced at the data-access layer, not just the API layer.
- Proctoring Analysis Worker: post-interview only, pulls the recording/signal reference, calls the (TBD) proctoring signal vendor, writes `proctoring_events`.
- `generate_proctoring_verdict` Celery task: Scoring Engine (`proctoring_integrity` rules) → Judge agent call → write `verdicts` (`service_type=interview_proctoring`).
- I13 retention job: scheduled hard-delete of `proctoring_events` past the (legal-review-pending) retention window — ships with this epic, not deferred to E12, given I13's independent urgency.
- Architectural guarantee for I15: no code path from any component in this epic back into a live interview session (no session-control API calls, no participant-management capability) — verified by code review, not just by omission.

**Depends on:** E15, E16, E17, E3, E8. **Also gated on a precondition outside engineering's control:** per [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md) and [09-roadmap.md](docs/09-roadmap.md), this epic's *code* can be built in parallel with the rest of v1, but **must not be enabled for any real organization/jurisdiction until that jurisdiction's biometric-data and all-party-consent legal review clears** — see the roadmap's dedicated "v1-proctoring" row.

**Docs/invariants:** I13, I15, A21, A22, A28, the entire "Interview proctoring — biometric data" section in [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md).

**Definition of done:** Engineering DoD (can be met before legal clearance): consent gating verified by integration test (no ingestion without both consents); I15 verified by architectural review confirming no live-session callback path exists anywhere in this epic's code; a completed interview with both consents produces `proctoring_events` and a `verdicts` row; the I13 retention job purges events past the (placeholder, pending-legal) retention window in a test. **Launch DoD (separate from engineering DoD, per-organization/jurisdiction):** legal sign-off obtained per [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md), named proctoring vendor under a signed DPA — neither of which engineering can satisfy by writing code, and this epic is not "done" for a given organization until both are true for that organization's jurisdiction(s).

---

## Cross-cutting risks carried over from the docs

| Risk | Source | Implication for epic sequencing |
|---|---|---|
| RAG search (E7/E9/E10) is a sequential dependency before pilot onboarding in the current roadmap timeline. | [09-roadmap.md](docs/09-roadmap.md) open questions | If the team wants to de-risk pilot timing, E8 (pipeline/scorecards) could ship as a leaner backend-only v1 slice while E6/E7/E9/E10 follow as a fast-follow. |
| No fallback/secondary LLM provider. | [07-technical-stack.md](docs/07-technical-stack.md) | E9/E10 should at minimum have circuit-breaking/graceful-degradation behavior even without a second provider. |
| Embedding vector dimension/model version has no documented migration plan — **now more consequential**, since a swap requires provisioning new Qdrant collections (vector size is fixed per collection) across every organization, not a single-table migration. | [05-data-model.md](docs/05-data-model.md), [07-technical-stack.md](docs/07-technical-stack.md) | E7 should isolate the embedding-model reference and collection-naming scheme behind `app/services/vector_store.py` so a future migration isn't a full rewrite. |
| `audit_log` has no partitioning/archival strategy. | [05-data-model.md](docs/05-data-model.md) | Explicitly deferred to v2; E1 should just avoid designs that would block adding partitioning later. |
| **New:** deletion (I9) now spans two systems with no shared transaction — a partial failure leaves either orphaned searchable PII in Qdrant or an unreconciled anonymization in Postgres. | [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md) | E12 must ship a compensating-action mechanism (retry/alert or reconciliation job), not a bare best-effort call — treat this as part of E12's definition of done, not a follow-up. |
| **New:** Qdrant collection-per-organization is a deliberate reversal of the prior "avoid a second tenant-isolation surface" decision, accepted for performance/scaling reasons. | [06-architecture.md](docs/06-architecture.md) | E13's test suite is the concrete proof this tradeoff is safe in practice — do not treat it as a lower-priority test class than the original Postgres RLS suite just because it's newer. |
| **New:** Organization creation/deactivation now has a distributed-provisioning step (Postgres row + Qdrant collection) with its own partial-failure mode. | [06-architecture.md](docs/06-architecture.md) open questions | E3 needs an explicit answer to "what happens if Qdrant collection provisioning fails after the Postgres org row commits" before this is built, not improvised during implementation. |
| **New 2026-07-16:** interview proctoring (E21) is gated on a legal review with an unknown, likely multi-month timeline entirely outside engineering's control. | [08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md), [09-roadmap.md](docs/09-roadmap.md) | E21's code can and should be built in parallel with the rest of v1 (its dependencies — E15–E17, E3, E8 — are all v1-track epics), but no sprint plan should treat E21 as "done" in the sense of shippable-to-a-real-org until legal sign-off exists for that org's jurisdiction. Don't let engineering velocity on E21 create pressure to launch ahead of that review. |
| **New 2026-07-16:** OpenRouter (E17) is now a single point of failure in front of every crew model call across all four agent roles and all three verdict services — more concentrated risk than the pre-existing "no fallback LLM provider" risk above, not a mitigation of it. | [07-technical-stack.md](docs/07-technical-stack.md) | E17 should include basic circuit-breaking/error-surfacing for OpenRouter outages from day one, given how much now depends on it; treat this as a slightly elevated version of the existing no-fallback-provider risk, not a new independent one. |
| **New 2026-07-16:** three vendor selections are still open (Verdict/Judge model, video platform, proctoring signal detection vendor) and each blocks a different epic (E17, E19/E21, E21 respectively) from being fully implementable. | [07-technical-stack.md](docs/07-technical-stack.md) open questions | E16 (Scoring Engine) and E15 (schema) can and should proceed without these decisions, since they're vendor-agnostic; E17/E19/E21's actual integration code cannot be finished until each respective vendor is named — sequence planning should treat these as external blockers to flag early, not discover mid-sprint. |
| **New 2026-07-16:** the Scoring Engine's rubrics (E16) directly influence a verdict that could factor into hiring decisions, raising the same disparate-impact concern the autonomous-ranking exclusion in [01-problem-space-and-scope.md](docs/01-problem-space-and-scope.md) was written to avoid — but the rubrics themselves aren't currently in either the legal-review scope (E21) or the general privacy review pending elsewhere. | [02-assumptions.md](docs/02-assumptions.md), [09-roadmap.md](docs/09-roadmap.md) open questions | Confirm with the product owner whether E16/E18/E20's rubrics need their own disparate-impact review before pilot launch, distinct from and in addition to E21's biometric-specific legal gate — currently unresolved, not just for proctoring. |
