# 07 — Technical Stack

**Purpose:** Lock in concrete technology choices for each architectural component, with rationale and the rejected alternative.

**Depends on:** [06-architecture.md](06-architecture.md) (components this stack implements).
**Feeds into:** [08-privacy-and-compliance.md](08-privacy-and-compliance.md) (storage/hosting choices affect compliance posture) and [09-roadmap.md](09-roadmap.md) (phasing assumes this stack's capabilities).

> **Revision note (2026-07-15):** the vector database choice changed from pgvector-inside-Postgres to a dedicated Qdrant instance. This is a direct reversal of the "no dedicated vector database" decision this document previously made — see below for the honest accounting, and [CHANGELOG.md](../CHANGELOG.md) for when this changed.

---

## Stack choices

| Layer | Choice | Why | Alternative considered |
|---|---|---|---|
| Backend language/runtime | Python 3.12 | RAG and multi-agent LLM orchestration are core, not a delegated side call — Python has the deepest ecosystem for both. | TypeScript/Node (original choice) — rejected once the system's central logic became RAG retrieval and multi-agent orchestration. |
| Backend framework | FastAPI | Async-native, Pydantic models map directly onto structured LLM outputs and RAG payloads, automatic OpenAPI schema for the frontend. | Django — heavier framework overhead not justified for an API-first, orchestration-heavy backend. |
| Frontend framework | Next.js (React) — unchanged | Pure API client of the FastAPI backend; right fit for a data-dense HR dashboard. | A Python server-rendered framework — rejected, would recouple frontend to backend language. |
| Primary relational database | PostgreSQL | ACID-transactional storage for the pipeline/scorecard/audit data whose invariants (I3–I9) depend on relational constraints, triggers, and row-level security. No longer holds any vector data — see the Vector database row below. | MySQL — rejected on the same grounds as the original stack decision (RLS + JSONB + enum-type support favor Postgres). |
| Vector database | **Qdrant** (one collection per Organization) | Purpose-built ANN performance and richer filtering/hybrid-search headroom than pgvector offers, without that workload competing with the primary OLTP Postgres instance as resume volume grows; lets the vector workload (high write volume from chunking, different query shape) scale independently of the relational workload. Hosted as **Qdrant Cloud** (managed) rather than self-hosted, to stay consistent with this stack's existing "avoid owning infrastructure that's undifferentiated relative to the product problem" posture (same reasoning already applied to RDS and ElastiCache below). | **pgvector inside the existing PostgreSQL instance** — this was the v1 decision as of the 2026-07-14 pivot, and is the alternative being explicitly rejected in *this* revision. That decision's stated rationale (avoiding a second tenant-isolation surface) was sound and is not dismissed lightly — see the "collection-per-organization" isolation design in [06-architecture.md](06-architecture.md) for how the reintroduced surface is mitigated. Self-hosted Qdrant (e.g., on Fargate + EBS) was also considered and rejected for the same "avoid operating a new stateful system ourselves" reasoning this stack already applies elsewhere. |
| Embeddings model | Voyage AI (`voyage-3`, 1024-dim) — unchanged | Purpose-built retrieval embeddings with strong domain recall; Anthropic's recommended embeddings partner. | Self-hosted open-source embedding models — rejected for v1, avoids standing up embedding inference infrastructure. |
| LLM crew / agent orchestration | CrewAI — unchanged | Purpose-built for role-based agents collaborating as a defined crew, each bindable to a different model by task complexity. | LangGraph — rejected for v1, requires materially more custom orchestration code. |
| LLM models (multi-model assignment) | Claude Haiku 4.5 — Extraction Agent; Claude Sonnet 5 — Summarizer Agent; Claude Opus 4.8 — Reasoning Agent — unchanged | Matches model capability and cost to task complexity and call volume. | A single model for every crew role — rejected: wastes spend on high-volume extraction or under-powers high-stakes reasoning. |
| Async task queue | Celery + Redis — unchanged | Mature multi-step task chaining for the parse → embed → (on-demand) crew pipeline. | RQ — lacks Celery's chaining/canvas features; Dramatiq — rejected mainly for ecosystem/hiring-familiarity reasons. |
| Object storage | S3-compatible storage (AWS S3) — unchanged | Standard for file storage with signed-URL access patterns. | Storing files as DB blobs — rejected outright. |
| Authentication (HR users) | Managed auth provider (Auth0/Clerk) with org-scoped sessions — unchanged | JWT validation from FastAPI is no harder than from any other framework; org_id in the session drives both the Postgres RLS variable and Qdrant collection resolution. | Custom-built auth — rejected for security-surface reasons. |
| Authentication (candidates) | Magic-link / time-limited email token, no password — unchanged | Matches A9 in [02-assumptions.md](02-assumptions.md). | Full candidate account system — still out per the Scope Creep Watchlist. |
| Hosting | AWS: ECS Fargate for the FastAPI API and all Celery workers (separate task definitions per worker type), RDS for PostgreSQL, S3 for objects, ElastiCache for Redis, **Qdrant Cloud for the vector store** | Same managed/serverless-adjacent posture across every stateful dependency — Qdrant Cloud is added on the same terms as RDS/ElastiCache: a managed service, not infrastructure the team operates itself. | Self-managed Kubernetes, and self-hosted Qdrant specifically — both rejected for the same operational-overhead reasoning applied elsewhere in this stack. |
| Email delivery | Transactional email API (Postmark/SES) — unchanged | Deliverability/bounce handling is a solved problem. | Self-hosted SMTP — still rejected. |

## Choices made specifically to keep v1 scope tight

- **No microservices split, despite the added storage surface.** The API and all Celery workers remain one Python codebase, one repo, one data-access layer, even though they now talk to two stateful storage systems (Postgres, Qdrant) instead of one.
- **A dedicated vector database (Qdrant), scoped by collection-per-organization rather than a shared collection with a payload filter.** This is a deliberate reversal from the prior "no dedicated vector database" position — restated honestly here rather than silently dropped: the isolation-surface cost the original decision was trying to avoid is real, and is mitigated (not eliminated) by giving Qdrant a structural per-organization boundary instead of relying on filter discipline alone.
- **No self-hosted ML/NLP or embedding infrastructure.** Both the LLM crew and the embedding step call hosted provider APIs (Anthropic, Voyage) rather than standing up model-serving or GPU infrastructure. Qdrant Cloud extends this same posture to the vector store itself — it is a managed database service, not inference infrastructure, so hosting it managed rather than self-managed is a direct application of this principle, not an exception to it.
- **No custom auth.** Unchanged rationale from the original stack decision.
- **A fixed three-model crew assignment, not a configurable/pluggable model registry.** Unchanged from the prior decision.

## Open Questions

- Does the Claude API need a fallback/secondary provider for availability, especially given a live user-facing search flow depends on it synchronously-from-the-user's-perspective?
- Should CrewAI's agent definitions live in the same FastAPI/Celery codebase, or is there a case for packaging the crew as an independently versioned/deployed component?
- At what per-organization chunk volume, or total collection count, does Qdrant Cloud's plan/tier need reassessing — does collection-per-organization remain cost-effective at higher organization counts than [02-assumptions.md](02-assumptions.md)'s A14 anticipates, or does the shared-collection-with-payload-filter multitenancy pattern Qdrant itself recommends become necessary?
- Is Voyage AI's embedding dimension (1024) and model version something to pin with a documented migration plan — changing it later requires provisioning new Qdrant collections (vector size is fixed per collection) and re-embedding every point across every organization.
- **New in this revision:** does Qdrant Cloud's authentication model (API key scoping) support per-collection or per-organization scoped keys, which would add a fourth isolation layer beyond collection-per-org + payload filter + application-layer session scoping — worth evaluating once collection-per-org volume is known, not a v1 blocker.
