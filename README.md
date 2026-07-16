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
Dockerfile      multi-stage build for the app image (API + future workers)
docker-compose.yml  local stack: api + postgres + redis + qdrant
entrypoint.sh   container startup: runs migrations, then execs the given command
EPIC.md         v1 backend epics
CODE.md         story lifecycle / coding workflow
CONTRIBUTING.md branching, PR, and review rules
```

## Running the app

The app runs exclusively as a Docker container — there is no supported "run it bare on the host" path for the API/workers. Docker Desktop (or an equivalent engine) is the only requirement; you do not need Python installed locally just to run the app.

```powershell
copy .env.example .env
# fill in .env with real values (AI provider keys, etc.) - DATABASE_URL/
# REDIS_URL/QDRANT_URL are overridden by docker-compose.yml to point at
# the compose-managed containers, so their .env values don't matter locally.

docker compose up --build
```

This starts the API (`http://localhost:8000`, `/health` for a liveness check), plus Postgres, Redis, and a local Qdrant container standing in for Qdrant Cloud (dev/test only — see [docs/07-technical-stack.md](docs/07-technical-stack.md)). See [Dockerfile](Dockerfile), [docker-compose.yml](docker-compose.yml), and [entrypoint.sh](entrypoint.sh) for the image build and container startup (Alembic migrations run automatically before the app starts).

Celery worker containers (parsing/embedding/crew/notification) aren't defined yet — `app/workers/` has no real Celery app to run until E5 lands; `docker-compose.yml` has a comment marking where they'll be added.

## Development setup (tests / linting only)

Docker runs the app; a local `.venv` is still used to write and run tests and lint, per [CODE.md](CODE.md)'s workflow. Requires Python 3.12. All installs go through `.venv` — never a bare `pip install`.

```powershell
# create venv (first time only)
python -m venv .venv

# install dependencies
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

Bash-tool equivalents use `.venv/Scripts/python.exe`.

Run checks (required before any PR, per [CONTRIBUTING.md](CONTRIBUTING.md)):

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check app tests
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, PR, and review requirements, and [CODE.md](CODE.md) for the step-by-step workflow every story follows (stub → approval → tests → implementation → approval → push).

## Documentation index

Start at [docs/README.md](docs/README.md). Read order: ideation → scope → assumptions → ontology → invariants → data model → architecture → technical stack → privacy/compliance → roadmap.
