# Sift

Resume Collector & Interview Analyzer platform for HR teams — a Python backend combining a relational data store, a RAG-based vector search pipeline, and a multi-model LLM crew for resume parsing, summarization, and match reasoning.

Full product and architecture reasoning lives in [docs/](docs/README.md) (start there — it's a connected, dependency-ordered set, not standalone pages). This README is setup and orientation only.

## Status

Backend, pre-v1. The repo is scaffold-only as of 2026-07-15 — see [EPIC.md](EPIC.md) for the v1 epic breakdown and [CODE.md](CODE.md) for the story-by-story workflow used to build it out.

## Stack

| Layer | Choice |
|---|---|
| API | Python 3.12, FastAPI |
| Relational data | PostgreSQL, SQLAlchemy (async) + Alembic |
| Vector store | Qdrant (one collection per Organization) |
| Async tasks | Celery + Redis |
| Object storage | S3-compatible |
| LLM crew | CrewAI, per-task model assignment (Claude Haiku / Sonnet / Opus), Voyage AI embeddings |

Rationale and rejected alternatives for each are in [docs/07-technical-stack.md](docs/07-technical-stack.md).

## Project layout

```
app/
  api/routes/   FastAPI route handlers
  core/         config, settings
  crew/         CrewAI agent definitions
  db/           session/engine setup
  models/       SQLAlchemy models
  schemas/      Pydantic schemas
  services/     business logic
  workers/      Celery tasks
alembic/        migrations
tests/          mirrors app/ structure
docs/           architecture & product documentation (read first)
EPIC.md         v1 backend epics
CODE.md         story lifecycle / coding workflow
CONTRIBUTING.md branching, PR, and review rules
```

## Setup

Requires Python 3.12. All installs go through the project's `.venv` — never a bare `pip install`.

```powershell
# create venv (first time only)
python -m venv .venv

# install dependencies
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt

# configure environment
copy .env.example .env
# then fill in .env with real values (DB, Qdrant, AI provider keys, etc.)
```

Bash-tool equivalents use `.venv/Scripts/python.exe`.

Run migrations once a Postgres instance is reachable via `DATABASE_URL`:

```powershell
.venv\Scripts\alembic.exe upgrade head
```

Run the dev server:

```powershell
.venv\Scripts\uvicorn.exe app.main:app --reload
```

Run checks (required before any PR, per [CONTRIBUTING.md](CONTRIBUTING.md)):

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check app tests
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, PR, and review requirements, and [CODE.md](CODE.md) for the step-by-step workflow every story follows (stub → approval → tests → implementation → approval → push).

## Documentation index

Start at [docs/README.md](docs/README.md). Read order: ideation → scope → assumptions → ontology → invariants → data model → architecture → technical stack → privacy/compliance → roadmap.
