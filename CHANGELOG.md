# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed
- **Vector storage moved from pgvector-inside-Postgres to a dedicated Qdrant vector store**, one collection per Organization, to gain purpose-built ANN performance and independent scaling from the relational workload. This reverses the 2026-07-14 pivot's explicit "no dedicated vector database" decision; the reintroduced tenant-isolation surface is mitigated via a collection-per-organization structural boundary (in place of the RLS policy the prior design relied on) plus a redundant payload filter. Postgres retains all relational tables and drops `resume_chunks` entirely, adding `resumes.embedding_status` in its place. Affects [docs/04-invariants.md](docs/04-invariants.md) (I2/I11 enforcement mechanism), [docs/05-data-model.md](docs/05-data-model.md) (full rewrite of the vector storage section), [docs/06-architecture.md](docs/06-architecture.md) and [docs/07-technical-stack.md](docs/07-technical-stack.md) (full rewrites), [docs/08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md) (new Qdrant Cloud subprocessor, two-system deletion consistency risk), [docs/09-roadmap.md](docs/09-roadmap.md) (Gantt wording), [docs/03-ontology.md](docs/03-ontology.md) and [docs/README.md](docs/README.md) (wording fixes), plus [EPIC.md](EPIC.md) (E1, E3, E7, E10, E12, E13, E14 rewritten) and the corresponding Jira epic/stories in the `VHIRE` project.
- `requirements.txt`: dropped `pgvector`, added `qdrant-client`; `.env.example` gained `QDRANT_URL`/`QDRANT_API_KEY`.

### Added
- Project scaffolding at the repo root: `app/` (FastAPI backend package - `core`, `db`, `models`, `schemas`, `api/routes`, `services`, `workers`, `crew`, each a directory-skeleton stub per [docs/06-architecture.md](docs/06-architecture.md)'s components), `alembic/` (async-ready migration env, no migrations yet), `tests/`, plus `requirements.txt` / `requirements-dev.txt` / `.env.example` at root for quick setup reference.
- A project-root `.venv` (Python 3.12, installed via winget since no interpreter existed on the machine) with all backend dependencies installed from `requirements-dev.txt` - `fastapi`, `sqlalchemy[asyncio]`+`asyncpg`+`alembic`+`pgvector`, `celery[redis]`, `boto3`, `anthropic`, `voyageai`, `crewai`, `pytest`, `ruff` - verified importable end-to-end (`app.main:app` boots, `pytest --collect-only` and `ruff check` both pass clean).

### Changed
- **Backend stack pivoted from TypeScript/NestJS to Python/FastAPI**, and the architecture was redrawn around a RAG-based vector search pipeline (PostgreSQL + `pgvector`, Voyage AI embeddings) and a multi-model LLM crew (CrewAI: Claude Haiku for extraction, Sonnet for summarization, Opus for candidate-requisition matching/reasoning). Affects [docs/06-architecture.md](docs/06-architecture.md) and [docs/07-technical-stack.md](docs/07-technical-stack.md) (full rewrites), with ripple updates to [docs/01-problem-space-and-scope.md](docs/01-problem-space-and-scope.md) (in-scope table, Scope Creep Watchlist boundary, bounded context diagram), [docs/02-assumptions.md](docs/02-assumptions.md) (new RAG/crew assumptions A16–A20), [docs/03-ontology.md](docs/03-ontology.md) (derived AnalysisOutput/ResumeChunk artifacts), [docs/04-invariants.md](docs/04-invariants.md) (new I10/I11 extending tenant isolation to the vector index), [docs/05-data-model.md](docs/05-data-model.md) (new `resume_chunks` and `analysis_outputs` tables), [docs/08-privacy-and-compliance.md](docs/08-privacy-and-compliance.md) (embeddings as PII, third-party AI subprocessors, updated deletion flow), [docs/09-roadmap.md](docs/09-roadmap.md) (v1 now ships RAG search, updated Gantt), and [docs/README.md](docs/README.md).
- `.gitignore` narrowed to Python-only entries (`__pycache__/`, `.venv/`, Celery artifacts) - the Node/Next.js section was removed since there is no frontend scaffolded yet.

### Added
- Initial foundational documentation set in `/docs` (10 numbered documents + index), covering ideation, problem scope, assumptions, ontology, invariants, data model, architecture, technical stack, privacy/compliance, and roadmap for the Resume Collector & Interview Analyzer platform.
- `CLAUDE.md` prompt log recording prompts given to Claude and summaries of the resulting work.
- `.gitignore` for the Node/TypeScript stack chosen in [docs/07-technical-stack.md](docs/07-technical-stack.md).
