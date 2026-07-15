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

---

## 2026-07-13 — Push initial documentation set to GitHub

**Prompt:**
> push this local repo to the remote - https://github.com/bc0de0/virtual_hire.git. This is a first time push and will require a git init action. Also, ensure meaningful commit messages and manage a changelog.

**Response summary:**
Initialized git (no identity was configured on the machine, so set it locally to `Kunal Gupte <kunal@revorion.ai>` for this repo only), added a Node/TypeScript-oriented `.gitignore` and a `CHANGELOG.md` (Keep a Changelog format), committed all 14 existing files with a descriptive message, renamed the default branch to `main`, added the `origin` remote, and pushed with `-u` to establish tracking. Confirmed with the user before the push since it was the first write to a shared remote.

---

## 2026-07-14 — Redo architecture and tech stack for RAG + multi-model LLM crew (Python backend)

**Prompt:**
> rethink the architecture and techstack keeping in mind the following parameters - we need a seperate backend, a RAG based vector DB and querying support for resume search and retrival and matching also we will need a multi model LLM crew for tasks like summarizer and reasoning. Python is a natural candidate for this tasks. Redo all revelant documents with this parameters in mind

**Response summary:**
Re-read all 10 docs plus the README, then revised every document the new requirements actually touch rather than only the two stack docs, since a backend-language and architecture change ripples through scope, assumptions, ontology, invariants, and the schema:

- **06-architecture.md** — full rewrite: frontend and backend are now separate deployables (Next.js talking only to a Python backend's API); added an Ingestion → Extraction Agent → Embedding Worker pipeline; added a dedicated RAG search sequence diagram (embed query → org-scoped vector search → Reasoning Agent rationale — deliberately retrieval-first so cross-org data can never reach the LLM call); extended the multi-tenancy section to cover the vector index and explicitly explained why pgvector-in-Postgres was chosen over a dedicated vector database (avoids a second tenant-isolation surface).
- **07-technical-stack.md** — full rewrite: Python 3.12 + FastAPI backend, PostgreSQL + `pgvector`, Voyage AI embeddings, CrewAI for multi-agent orchestration, and a fixed per-task model assignment (Claude Haiku 4.5 for extraction, Sonnet 5 for summarization, Opus 4.8 for reasoning/matching) — each choice with a rejected alternative (LangGraph, dedicated vector DB, self-hosted embeddings, Django).
- **01-problem-space-and-scope.md** — added RAG search/retrieval as an in-scope row; sharpened the "AI-based candidate ranking" Scope Creep Watchlist entry to draw an explicit line between the now-in-scope HR-initiated, query-scoped, advisory search feature and the still-out-of-scope autonomous/background ranking that gates decisions; updated the bounded-context diagram to show the LLM crew and vector index inside the boundary with the hosted AI providers as external.
- **02-assumptions.md** — added assumptions A16–A20 on embedding quality, multi-step crew latency, search query volume, fixed shared-model sufficiency, and third-party PII exposure to the AI providers.
- **03-ontology.md** — added `ResumeChunk/Embedding` and `AnalysisOutput` to the "not first-class" list as derived/regenerable artifacts (same treatment as `parsed_data`), consistent with the doc's existing anti-over-modeling stance.
- **04-invariants.md** — extended I2's description to explicitly cover the vector table, and added I10 (AnalysisOutput may only be generated from submitted, not draft, Scorecards) and I11 (RAG search/match results are always org-scoped, retrieval-filtered before any LLM reasoning call).
- **05-data-model.md** — added `resume_chunks` (pgvector column, HNSW index, org-scoped RLS) and `analysis_outputs` (summary, match rationale, `source_scorecard_ids` for I10 auditability, `crew_run` recording which model handled each agent role) tables; updated the ER diagram and the invariant-enforcement summary table.
- **08-privacy-and-compliance.md** — added embeddings and LLM crew output to the PII inventory; added a new subprocessors section naming Anthropic and Voyage AI with a **[NEEDS LEGAL REVIEW]** flag for DPAs; updated the deletion flow to hard-delete `resume_chunks`/`analysis_outputs` (rather than anonymize, since they exist only to serve search/summarization); updated the candidate consent notice text to disclose AI processing.
- **09-roadmap.md** — moved RAG search and the LLM crew into v1's ship list (no longer deferred); updated the v1→v2 exit criteria to require the I11 test suite and AI-subprocessor DPAs; updated the Gantt chart with embedding-pipeline and crew-build phases.
- **00-ideation.md** and **docs/README.md** — smaller consistency edits (non-goal boundary clarification, a new search-adoption success metric, updated doc summaries).
- **.gitignore** — extended to cover Python backend artifacts (`.venv/`, `__pycache__/`, Celery) alongside the existing Node/Next.js entries.
- **CHANGELOG.md** — added a `### Changed` entry under `[Unreleased]` documenting the pivot and every file it touched.

Every changed document's Open Questions section was updated to reflect genuinely new unresolved decisions introduced by this pivot (e.g., whether RAG should ship as a v1 fast-follow instead of a pilot-blocking dependency, embedding-dimension migration risk, cross-border transfer questions for the new AI subprocessors) rather than being left stale.

---

## 2026-07-14 — Project scaffolding + Python venv setup

**Prompt:**
> create the project scaffolding (directory structure) with minimum internal files & stubs / and or gitkeep if empty, install .venv via terminal in project root for python. No local install rule strictly enforced. Install project dependencies in the venv along with env setup. Create a requirements file for quick reference and setup.

**Response summary:**
Found no Python interpreter on the machine (only the Windows Store alias stub) and no `winget`-installed runtime; confirmed with the user before installing Python 3.12 via `winget install Python.Python.3.12` (a machine-wide, user-scoped install). Created `requirements.txt`/`requirements-dev.txt` (FastAPI, SQLAlchemy async + asyncpg + alembic + pgvector, Celery+Redis, boto3, anthropic, voyageai, crewai, pytest, ruff) and `.env.example` matching [docs/07-technical-stack.md](docs/07-technical-stack.md), created `.venv` at the project root, and installed everything into it (never bare `pip install` — always via `.venv\Scripts\python.exe -m pip`).

Hit two real dependency-resolution failures along the way and fixed both rather than working around them: (1) `crewai`'s transitive `litellm` pin resolved to a version with no Windows wheel, requiring a Rust toolchain to build from source — pinned `litellm==1.55.3` instead of installing Rust for a transitive dependency; (2) that pin's `httpx<0.28` requirement conflicted with an explicit `httpx==0.28.1` pin — loosened to `httpx>=0.27.0,<0.28.0`. Also found Python 3.12 venvs no longer bundle `setuptools`, and `crewai`'s telemetry module imports `pkg_resources` at import time — added `setuptools==75.6.0` (pinned below 81, since newer setuptools releases have dropped `pkg_resources` entirely).

Built out a full first-pass scaffold (SQLAlchemy models for all 10 tables in [docs/05-data-model.md](docs/05-data-model.md), FastAPI route stubs, Celery worker stubs, CrewAI agent definitions, Alembic env) under a `backend/` directory alongside an empty `frontend/` placeholder — then the user interrupted mid-task: no `backend/` wrapper (all app code should live directly at the repo root), no frontend at all, and far fewer files ("just the outline for now"). Asked a clarifying question on how minimal "outline" should mean; user chose directory-skeleton-only. Restructured accordingly: moved `app/`, `alembic/`, `tests/`, and the requirements/env files up to the project root, deleted `backend/` and `frontend/` entirely, and stripped `app/` down to one `__init__.py` per package with a one-line docstring (no model classes, no route handlers, no Celery task bodies, no CrewAI agent configs) — matching the directory shape of [docs/06-architecture.md](docs/06-architecture.md)'s components (`core`, `db`, `models`, `schemas`, `api/routes`, `services`, `workers`, `crew`) without pre-writing their implementation. Kept `app/main.py` as a minimal real FastAPI entrypoint (just the app instance + a `/health` route) since an app needs *some* entrypoint, and simplified `alembic/env.py` to not depend on the now-removed `app.core.config`/`app.db.base` (target_metadata is `None` until models exist). Also trimmed `.gitignore`'s frontend/Node section since there's no frontend yet.

Verified the final state end-to-end after the restructure: `app.main:app` imports and boots, `pytest --collect-only` runs clean (no tests yet, as expected), and `ruff check app tests` passes with no findings.

---

## 2026-07-14 — Backend v1 epic breakdown

**Prompt:**
> do a deep tissue analysis of current repo and suggest the epics we will need to take to finish the backend for the first release give the output in a epic.md file in project root

**Response summary:**
Re-read the current repo state (confirmed it's still scaffold-only — empty `__init__.py` stubs under every `app/` package, no models/routes/workers/crew implementations) alongside [docs/05-data-model.md](docs/05-data-model.md), [06-architecture.md](docs/06-architecture.md), [04-invariants.md](docs/04-invariants.md), [07-technical-stack.md](docs/07-technical-stack.md), and [09-roadmap.md](docs/09-roadmap.md), then wrote `EPIC.md` at the project root: 14 backend-only epics (E1 data layer through E14 observability/deployment readiness), each with goal, key deliverables, explicit epic-level dependencies, the specific docs/invariants it implements, and a definition of done anchored to that invariant's own test description (e.g., E13's DoD is literally the I2/I11 cross-tenant test suite the invariants doc already specifies).

Structured as a dependency graph (Mermaid) rather than a flat list, since several epics (e.g., E8 pipeline/scorecards vs. E6/E7 parsing/embedding) have no data dependency on each other and can run in parallel — the doc calls this out explicitly in the sequencing table rather than forcing a single linear order. Also carried forward four open questions already flagged in the docs (RAG-before-pilot sequencing, no LLM fallback provider, embedding-dimension migration risk, audit_log partitioning) into a "cross-cutting risks" section at the end, framed as sequencing implications rather than re-litigating them.

Scope was deliberately held to backend only — frontend, calendar integration, ATS export, and the Scope Creep Watchlist items were excluded, matching [01-problem-space-and-scope.md](docs/01-problem-space-and-scope.md) and the v1 "does NOT ship" row in [09-roadmap.md](docs/09-roadmap.md). No code was written in this session.

---

## 2026-07-14 — Jira auth setup for EPIC.md → story sync

**Prompt:**
> we want to create the stories based on the epics in epic.md file in a new workspace on jira - create a .env file in root with the jira api key if applicable and update the .env.example file as well or give me a alternate method to auth my jira with this repository

**Response summary:**
No Jira MCP server was connected in this session (only a Linear connector showed up as available-but-unauthorized). Asked the user to choose between an Atlassian API token in `.env` (works immediately, no interactive OAuth needed) versus a Jira MCP server (requires an interactive browser step this non-interactive session can't perform) — user chose the API token route. Added `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN`/`JIRA_PROJECT_KEY` to `.env.example` with a pointer to Atlassian's token-generation page, and created a git-ignored `.env` (verified via `git check-ignore`) with the same placeholders for the user to fill in directly rather than pasting the token into chat.

---

## 2026-07-15 — Create Jira project + first epic/stories/sprint from EPIC.md

**Prompt:**
> I have created the jira api token key use it to create a new project having the same name as the project repository and its associated key. Add it to the .env file and then create the first epic with associated tasks or backlogs or sprints

**Response summary:**
User filled in `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN` in `.env` (Atlassian site `hexdefender.atlassian.net`). Verified the token via `GET /rest/api/3/myself`, then validated candidate project keys derived from the repo name (`virtual_hire`) via `GET /rest/api/3/projectvalidate/key` before committing to one, rather than guessing at Jira's key-format rules.

Created a team-managed Scrum project (`POST /rest/api/3/project`, template `com.pyxis.greenhopper.jira:gh-simplified-agility-scrum`) named `virtual_hire` with key `VHIRE` — Scrum was chosen over Kanban specifically because the user asked for "backlogs or sprints," which the Scrum template ships with by default. Wrote `JIRA_PROJECT_KEY=VHIRE` into `.env`.

Created the first Jira Epic (`VHIRE-1`) mirroring E1 — Foundational Data Layer & Migrations from [EPIC.md](EPIC.md) (summary, description, dependencies, definition of done copied from that epic's section), then created four Story issues (`VHIRE-2..5`) as children of that epic, one per E1 key deliverable (DB session/engine setup, SQLAlchemy models for all 11 tables, the Alembic migration covering pgvector/HNSW/RLS/triggers, and the settings module). Found the project's auto-created board (`GET /rest/agile/1.0/board`), created "Sprint 1 - E1 Data Layer" on it (first name attempt hit Jira's 30-character sprint-name limit, shortened and retried), and moved all four stories into that sprint via `POST /rest/agile/1.0/sprint/{id}/issue`. Verified placement by re-fetching the sprint's issues before reporting done.

All Jira API calls were made directly via `curl`/Python `urllib` reading credentials from `.env` (`set -a; source .env; set +a`), writing multi-line JSON payloads to scratchpad files rather than inline shell strings after an inline single-quoted JSON payload failed to parse on the first attempt (a Windows Git Bash quoting issue, not a Jira-side error) — never printed the token itself to command output.

---

## 2026-07-15 — Pivot vector storage from pgvector to Qdrant (docs, EPIC.md, Jira)

**Prompt:**
> we are going to start coding. Typically we will follow the jira stories and sprints that we have defined. Change the db model from pgvector to a full qdrant db for vector embeddings and postgres for the rest of the models. Giving flexibility for both relational as well as vector searches and indexing. Re-write the stories in the jira considering this first and update the epic.md file accordingly in root too

**Response summary:**
This reverses the 2026-07-14 pivot's explicit "no dedicated vector database" decision in [docs/06-architecture.md](docs/06-architecture.md) and [docs/07-technical-stack.md](docs/07-technical-stack.md), which had argued a dedicated vector DB would double the tenant-isolation surface I2/I11 must be verified against. Since EPIC.md and the Jira stories both cite docs/03–09 directly, asked the user whether to propagate the change through the full doc set or just EPIC.md/Jira — user chose the full propagation, matching this project's established pattern from the prior pivot.

Made one explicit architecture call not dictated by the user's prompt: **collection-per-organization** in Qdrant (rather than Qdrant's own recommended shared-collection-with-payload-filter multitenancy pattern), to preserve the same *structural* isolation boundary RLS gave Postgres, given I2's framing of cross-tenant leaks as "the most severe possible failure for this system." Documented this as a deliberate, named tradeoff (not a free upgrade) in every doc it touches, including the new operational costs it reintroduces.

Rewrote: [docs/05-data-model.md](docs/05-data-model.md) (removed `resume_chunks` as a Postgres table, added a "Vector store (Qdrant)" section with the collection-per-org design, point/payload schema, and `resumes.embedding_status` as the new Postgres-side tracking column), [docs/06-architecture.md](docs/06-architecture.md) and [docs/07-technical-stack.md](docs/07-technical-stack.md) (full rewrites — component diagrams, sequence diagrams, multi-tenancy section, and an honest reversal of the prior "why not a dedicated vector database" argument, including Qdrant Cloud as the hosting choice to stay consistent with the existing managed-services posture). Targeted edits to [docs/04-invariants.md](docs/04-invariants.md) (I2/I11 enforcement mechanism), [docs/08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md) (Qdrant Cloud as a new subprocessor, and a new open question about the two-system deletion routine's partial-failure risk now that Postgres anonymization and Qdrant point deletion aren't one transaction), [docs/09-roadmap.md](docs/09-roadmap.md) (Gantt wording), [docs/03-ontology.md](docs/03-ontology.md) and [docs/README.md](docs/README.md) (stale references).

Rewrote [EPIC.md](EPIC.md): E1 now Postgres-only (no vector schema); E3 gained a new deliverable (provision/tear down the org's Qdrant collection on org create/deactivate) and became a new dependency of E7; E7 was renamed "Vector Store Provisioning & Embedding Pipeline" and now targets Qdrant; E10's search task now queries Qdrant instead of a Postgres ANN index; E12's deletion routine now explicitly requires a compensating-action design for the new two-system consistency risk (not a bare best-effort call); E13's I11 test suite now proves collection-per-org isolation and collection-resolution correctness rather than RLS-filter correctness; E14 gained Qdrant to its readiness checks. Added a cross-cutting-risks entry for the new partial-provisioning/partial-deletion failure modes this pivot introduces.

Updated `requirements.txt` (dropped `pgvector`, added `qdrant-client`) and `.env`/`.env.example` (`QDRANT_URL`/`QDRANT_API_KEY`), and added a `CHANGELOG.md` entry recording the pivot and every file it touched.

Updated the existing Jira epic and its four stories in the `VHIRE` project (`VHIRE-1` through `VHIRE-5`) via the REST API to match E1's revised scope — `VHIRE-3`'s model list dropped `resume_chunks` and gained `embedding_status`/`embedding_error` on `resumes`; `VHIRE-4` dropped the `pgvector` extension/HNSW-index/vector-RLS scope entirely; `VHIRE-5` gained the new Qdrant env vars. Left Jira epics/stories for E3's collection-provisioning work and E7 (Qdrant embedding pipeline) uncreated for now, since only E1's sprint had been built out in Jira and the user's ask was to rewrite what already existed before coding begins, not to pre-build every future sprint.

---

## 2026-07-15 — Add CODE.md coding workflow

**Prompt:**
> we will complete sprint 1 from the jira backlog but before that create a code.md file in root that will create a coding best practice and workflow - typically the coding flow should follow the following steps - 1. from the jira story pick the next in line backlog item 2. Generate a stub / object model with docstrings and comments outlining the signature of the new additions 3. Wait for a human approvval 4. Once approved write test cases if required 5. concrete implementation and unit test pass test 6. Wait for human approval again 7 push to remote

**Response summary:**
Wrote `CODE.md` at the project root documenting the seven-step story lifecycle exactly as specified, with a Mermaid flowchart and steps 3/6 called out explicitly as hard stops (work does not proceed past them without an explicit in-conversation approval, and a round of requested changes loops back rather than counting as implicit approval). Filled in the specifics the user's outline left open, each grounded in this repo's existing conventions rather than invented generically: stub docstrings should state the contract (params/returns/raises/which invariant ID from [docs/04-invariants.md](docs/04-invariants.md) it enforces) since there's no implementation body yet for a reader to infer intent from — explicitly framed as a one-time exception to the project's normal terse/no-comments house style, reverting to that style once real implementation lands in step 5; step 4's "if required" was interpreted as scaling test rigor to the story's actual risk (pure scaffolding may need only a smoke test, invariant-enforcing logic needs contract tests written before the implementation); step 7 ties every commit message to its Jira key and keeps one story per commit.

Added a "Definition of done" checklist per story (cross-referencing EPIC.md's own DoD language so a story can't quietly ship a superset or subset of what its epic actually calls for), a short note on when CHANGELOG.md entries are and aren't warranted (architecture-level, not per-story — consistent with how it's been used so far), and environment reminders (`.venv`-only installs, PowerShell/Bash-tool syntax, `.env` never committed) pulled from existing CLAUDE.md/EPIC.md conventions rather than restated generically. Left branching as direct-to-main (matching how this repo has operated in every prior session) with an open question flagging PR-based review as a possible future change rather than assuming it now. No code was written in this session.
