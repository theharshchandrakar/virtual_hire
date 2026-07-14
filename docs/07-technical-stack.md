# 07 — Technical Stack

**Purpose:** Lock in concrete technology choices for each architectural component, with rationale and the rejected alternative.

**Depends on:** [06-architecture.md](06-architecture.md) (components this stack implements).
**Feeds into:** [08-privacy-and-compliance.md](08-privacy-and-compliance.md) (storage/hosting choices affect compliance posture) and [09-roadmap.md](09-roadmap.md) (phasing assumes this stack's capabilities).

---

## Stack choices

| Layer | Choice | Why | Alternative considered |
|---|---|---|---|
| Backend language/runtime | TypeScript on Node.js | One language across API, workers, and (per below) frontend — reduces context-switching for a small v1 team and keeps hiring/onboarding simple. | Python — stronger NLP/data ecosystem, but rejected because parsing/analysis is delegated to a hosted LLM API rather than in-house models (see Analysis layer below), removing Python's main advantage here. |
| Backend framework | NestJS | Opinionated structure (modules, DI) keeps a small team consistent as the codebase grows past a single developer; built-in support for the guard/interceptor patterns needed for the org-scoping enforcement in [06-architecture.md](06-architecture.md). | Express — simpler and more minimal, rejected because it leaves request-scoping and validation conventions unenforced, riskier given I2's stakes. |
| Frontend framework | Next.js (React) | Server-rendered pages suit an HR-facing dashboard with data-heavy tables; one framework serves both the HR UI and the lightweight candidate submission form. | Remix — comparable capability, rejected only for ecosystem familiarity/maturity margin at time of choice, not a strong technical difference. |
| Primary database | PostgreSQL | Native Row-Level Security directly implements the multi-tenancy design in [06-architecture.md](06-architecture.md); JSONB columns handle the semi-structured `parsed_data`/`ratings` fields from [05-data-model.md](05-data-model.md) without a second database. | MongoDB — natural fit for resume JSON, rejected because it lacks RLS-equivalent tenant isolation primitives and the core entities (Application, Interview, Scorecard) are genuinely relational with real foreign-key integrity needs (I1, I7, I8). |
| Queue / async processing | Redis + BullMQ | Lightweight, same infra footprint as caching needs, sufficient durability guarantees for v1's job volume (A14 scale); simple local dev story. | AWS SQS — more durable/managed at scale, rejected for v1 to avoid cloud-lock-in this early and because BullMQ's retry/backoff features are sufficient at target volume; revisit if hosting moves fully managed. |
| Object storage | S3-compatible storage (AWS S3) | Standard for file storage with signed-URL access patterns needed for the namespaced-key isolation approach in [06-architecture.md](06-architecture.md). | Storing files as DB blobs — rejected outright; bloats the primary database and breaks the separation of structured vs. file data assumed throughout [05-data-model.md](05-data-model.md). |
| Resume parsing & analysis (LLM layer) | Hosted Claude API (Anthropic) for document text/field extraction and scorecard summarization | Avoids building and maintaining custom NLP/NER models for resume parsing — a hosted LLM handles varied resume formats (per A7's uncertainty) better than a bespoke pipeline the v1 team would need to train and tune. | Self-hosted open-source NLP models (e.g., spaCy-based extraction) — rejected for v1: higher engineering investment for uncertain accuracy gain, and doesn't reduce operational burden the way a hosted API call does. |
| Authentication (HR users) | Managed auth provider (e.g., Auth0/Clerk) with org-scoped sessions | Avoids building session/password/MFA infrastructure in-house for a security-sensitive surface; org_id embedded in the issued session maps directly to the RLS session variable in [06-architecture.md](06-architecture.md). | Custom-built auth (Passport.js + own user table) — rejected for v1: security surface area (password storage, reset flows, MFA) is exactly the kind of undifferentiated heavy lifting not worth owning pre-PMF. |
| Authentication (candidates) | Magic-link / time-limited email token, no password | Matches assumption A9 (no persistent candidate accounts needed in v1); minimal surface for a secondary user type. | Full candidate account system — rejected per the Scope Creep Watchlist in [01-problem-space-and-scope.md](01-problem-space-and-scope.md) (candidate self-service portal is explicitly deferred). |
| Hosting | AWS (ECS Fargate for API/workers, RDS for Postgres, S3 for objects, ElastiCache for Redis) | Managed/serverless-adjacent compute avoids owning Kubernetes operations for a small team; RDS gives managed backups/failover for the database holding all PII. | Self-managed Kubernetes — rejected for v1: the operational overhead (cluster management, scaling policies) isn't justified at target scale (A14) and diverts engineering time from product work. |
| Email delivery | Transactional email API (e.g., Postmark/SES) | Deliverability and bounce/complaint handling for candidate-facing notifications is a solved problem not worth rebuilding. | Self-hosted SMTP — rejected: deliverability reputation management is a specialized, ongoing burden inappropriate for v1 focus. |

## Choices made specifically to keep v1 scope tight

- **No microservices split.** API and workers are separate deployable processes (for independent scaling of sync vs. async load per [06-architecture.md](06-architecture.md)), but they share one codebase, one repo, and one data-access layer. Splitting into per-domain services (candidate-service, interview-service, etc.) is explicitly deferred — it solves a team-scaling problem this project doesn't have yet, and would multiply the surface area for the multi-tenancy invariant (I2) to be re-verified across service boundaries.
- **No self-hosted ML/NLP infrastructure.** Delegating parsing and analysis to a hosted LLM API avoids standing up model-serving infrastructure, GPU provisioning, and retraining pipelines — all undifferentiated work relative to the actual problem (structured pipeline visibility).
- **No custom auth.** As above — security-critical, well-solved-elsewhere problem.
- **Single shared database with RLS instead of per-tenant infrastructure.** Directly stated and justified in [06-architecture.md](06-architecture.md); repeated here as a stack-level consequence, not just an architecture-level one.

## Open Questions

- Does the choice of Claude API for resume parsing need a fallback/secondary provider for availability, or is a single-provider dependency acceptable for v1 given the async, non-blocking nature of parsing?
- Should the frontend and backend be split into separate deploys now (even within one repo) to allow independent scaling/release cadence, or is a single deploy unit acceptable through v1?
- At what request volume does Redis+BullMQ's durability become insufficient and force a migration to SQS or similar — should we instrument for this signal now?
