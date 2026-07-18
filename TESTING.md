# Testing Plan

**Purpose:** The single source of truth for how Sift is tested — strategy, tooling, environments, and the concrete test-case catalog. This doc is the driver: new test work starts here (add/update a test case row, then implement it), rather than being written up after the fact. Keep it current as epics land — a stale test plan is worse than none.

**Scope:** Backend (exists today — FastAPI + Celery + Postgres + Qdrant, per [docs/07-technical-stack.md](docs/07-technical-stack.md)) and Frontend (Next.js, planned per the same doc, **not yet scaffolded** in this repo). Every section below is written for the backend as it exists now; frontend/E2E/UAT sections describe the plan to execute once frontend work starts, clearly marked `[PLANNED]` where nothing exists yet — none of it is fabricated as already-done.

**Depends on:** [docs/04-invariants.md](docs/04-invariants.md) (I1–I15 are the backbone of the regression suite), [docs/02-assumptions.md](docs/02-assumptions.md) (A14 sizes load targets), [EPIC.md](EPIC.md) (each epic's own Definition of Done is a test-case source), [vector.md](vector.md) (RAG pipeline specifics), [CODE.md](CODE.md) (per-story test-writing workflow this doc's case catalog feeds into).

---

## 1. Testing philosophy

- **Test logic directly, not framework glue.** The house convention (already in every existing test file) is to test service/task functions with fakes for the DB session, Qdrant client, Voyage/OpenRouter/Whisper calls, boto3, and Celery's `send_task` — not to spin up a real server or mock at the HTTP layer for unit-level checks. Framework wiring (routes actually resolving, dependency injection actually firing) is a *separate*, thinner layer of functional tests (§6.2), not duplicated at the unit level.
- **Fakes over deep-mocking.** Small hand-written fake classes (`_FakeSession`, `_FakeQdrantClient`, etc.) that model just the behavior a test needs, rather than `unittest.mock.MagicMock` with elaborate `.return_value` chains — cheaper to read, cheaper to keep correct when a signature changes.
- **Determinism is tested, not assumed.** Every Scoring Engine rule module has an explicit "same input twice → same output" test (I12's own requirement) — this generalizes to anything claiming to be deterministic.
- **Cross-tenant isolation (I2/I11) is a release blocker, not a regular test class.** It gets its own CI-required check once built (§7), separate from the general suite, and is never skipped or marked "known flaky."
- **Live-dependency integration tests skip, don't fail, when the dependency is unreachable locally** (see `tests/integration/conftest.py`), but **must run for real in CI** where Postgres/Redis/Qdrant are provisioned as service containers ([.github/workflows/ci.yml](.github/workflows/ci.yml)). A test that only ever runs mocked is not proof the real trigger/RLS policy/constraint works — see §5's gap notes for where this currently falls short.
- **No vendor call ever runs in a test.** OpenRouter/Voyage/Whisper/S3/Qdrant Cloud calls are always faked; the only "real" external dependencies tests touch are Postgres/Redis/Qdrant, and only via local docker-compose or CI service containers, never a hosted instance.

## 2. Test types & tooling

| Type | Tooling | Status | Runs |
|---|---|---|---|
| Unit | `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`, see `pyproject.toml`) | **Built, extensive** — 28 test files under `tests/` | Every commit (local), every PR/push to main (CI) |
| Functional / API (route-level) | `httpx.AsyncClient` + FastAPI's `ASGITransport` (no server process) | **Gap — not built yet** (§6.2, §9) | Would run alongside unit tests, same `pytest` invocation |
| Integration (live DB/vector store) | `pytest` + `asyncpg` direct connections, real Postgres/Redis/Qdrant via docker-compose or CI service containers | **Built, partial** — schema/RLS/trigger coverage for tables that exist; no live Qdrant integration tests yet (§9) | CI (always); locally only if `docker compose up postgres redis qdrant` |
| Smoke / sanity | A short manual (or scripted) walk of the critical path against docker-compose services | **Documented, not automated** (§6.4) | Before merging anything touching the pipeline; before any deploy |
| Regression | The I1–I15 invariant suite + epic DoD checks, run as part of the normal `pytest` suite plus the dedicated cross-tenant suite once built | **Partially built** (§5) | Every PR/push; cross-tenant suite becomes a required CI check once built |
| E2E (backend-only) | A scripted Python walk of the real API + real Celery worker + real Postgres/Qdrant/Redis (docker-compose), no UI involved | **Gap — not built yet**, spec in §6.6 | Pre-merge for pipeline-touching changes; nightly/scheduled once built |
| E2E (with frontend) | `[PLANNED]` Playwright, once a frontend exists | Not applicable yet | N/A |
| Load / performance | `[PLANNED]` Locust or k6 against a docker-compose or staging stack | **Gap — no infra yet**, targets specified in §6.7 | Pre-pilot-launch, then on a schedule (not every PR) |
| UAT | Persona-based manual scripts, sign-off tracked outside this repo (e.g. a checklist in the pilot-org rollout doc) | **Gap — no pilot org yet**, scripts specified in §6.8 | Before each new organization's pilot go-live |
| Security review | `code-review`/`security-review` skills (this repo's tooling) + the I2/I11 cross-tenant suite | Ad hoc today | Before merging auth/tenancy/PII-adjacent changes |

## 3. Test environments

| Environment | What's running | Used for |
|---|---|---|
| **Local, no services** | Just the `.venv` + pytest | Unit tests only — the majority of the suite; DB/Qdrant-dependent tests self-skip (see `tests/integration/conftest.py`'s `_migrated_database` fixture) |
| **Local, docker-compose** (`docker compose up postgres redis qdrant`) | Real Postgres, Redis, Qdrant containers per `docker-compose.yml` | Integration tests, manual smoke walk, future E2E script |
| **Local, full stack** (`docker compose up`) | Above + the FastAPI `api` container + a Celery `worker` container | Manual smoke test end-to-end (upload → parse → embed → verdict), local load-test target |
| **CI** (`.github/workflows/ci.yml`) | Ubuntu runner, Postgres/Redis/Qdrant as GitHub Actions service containers, `alembic upgrade head`, then `pytest` | Every PR to `main` and every push to `main` — the actual release gate |
| **Staging** `[PLANNED]` | Not yet provisioned — would mirror `docker-compose.yml`'s shape on real infra (ECS Fargate per [docs/07-technical-stack.md](docs/07-technical-stack.md)) with real (sandbox-tier) OpenRouter/Voyage/Whisper/S3 credentials | Load testing, UAT sign-off, pilot-org dry runs |

No test environment ever uses production credentials or a shared Qdrant Cloud/OpenRouter account with real candidate data — this follows directly from I2/I9's own posture on PII handling.

## 4. Coverage map — invariant / epic → test file

| ID | What it guarantees | Test file(s) | Status |
|---|---|---|---|
| I1 | Resume → exactly one Candidate | `tests/models/test_schema.py::test_resume_candidate_id_not_nullable`, `tests/integration/test_initial_schema.py::test_i1_resume_requires_candidate` | ✅ |
| I2 | No cross-org PII (Postgres RLS + Qdrant collection boundary) | `tests/integration/test_initial_schema.py::test_rls_enabled_on_every_org_scoped_table`, `tests/integration/test_transcripts_and_verdicts.py::test_rls_enabled_on_new_tables` (RLS *presence*) | ⚠️ **Gap**: no test yet proves RLS *behavior* (query as Org A, assert Org B rows are invisible) — see §9 |
| I3 | Same-org relationships (Application ↔ Candidate/Requisition) | `tests/integration/test_initial_schema.py::test_i3_rejects_cross_org_application`, `test_i3_allows_same_org_application` | ✅ |
| I4 | Scorecard immutability post-submit | `tests/integration/test_initial_schema.py::test_i4_direct_update_on_submitted_scorecard_rejected`, `test_i4_amend_scorecard_writes_audit_log_and_preserves_via_new_status` | ✅ |
| I5 | Valid Application status transitions | ⚠️ **Gap** — `applications.status` transition guard (the state machine in [docs/04-invariants.md](docs/04-invariants.md)) is not yet implemented (E8, out of this session's scope) | ❌ Not built |
| I6 | Resume parse state integrity (never stuck in `parsing`) | `tests/workers/test_parsing.py::test_parse_resume_failure_sets_parse_failed_and_does_not_enqueue` | ✅ |
| I7 | Interview → exactly one Application | `tests/integration/test_initial_schema.py::test_i7_interview_requires_application` | ✅ |
| I8 | Scorecard ↔ Interview 1:1 | `tests/integration/test_initial_schema.py::test_i8_scorecard_unique_per_interview` | ✅ |
| I9 | Deletion preserves aggregates | ⚠️ **Gap** — E12 (privacy/deletion) not built this session | ❌ Not built |
| I10 | AnalysisOutput only from submitted Scorecards | ⚠️ **Gap** — E9 (Summarizer) not built this session | ❌ Not built |
| I11 | RAG search never crosses org boundary | `tests/services/test_vector_store.py` (unit, collection naming + payload filter construction) | ⚠️ **Gap**: no live-Qdrant test proves cross-org isolation *in practice* — see §9 |
| I12 | Judge never runs without a Scoring Engine result | `tests/crew/agents/test_judge.py::test_run_judge_requires_deterministic_score_with_no_default`, `test_run_judge_raises_type_error_when_deterministic_score_omitted`; DB-layer: `tests/models/test_schema.py::test_verdicts_deterministic_score_not_nullable` | ✅ |
| I13 | Proctoring retention window | N/A — proctoring (E21) explicitly out of scope this session | ❌ Not applicable yet |
| I14 | Transcript verdict only after Interview completed | `tests/workers/test_verdicts.py::test_generate_transcript_verdict_rejects_non_completed_interview` | ✅ |
| I15 | Proctoring never intervenes live | N/A — proctoring (E21) explicitly out of scope this session | ❌ Not applicable yet |
| E3 | Org/HR user/requisition lifecycle | `tests/services/test_organizations.py`, `tests/services/test_hr_users.py`, `tests/services/test_requisitions.py` | ✅ |
| E4 | Candidate & resume ingestion | `tests/services/test_ingestion.py`, `tests/services/test_storage.py` | ✅ |
| E5 | Async task queue org-context propagation | `tests/workers/test_base.py` | ✅ |
| E6 | Resume parsing | `tests/workers/test_parsing.py`, `tests/services/test_text_extraction.py`, `tests/crew/agents/test_extraction.py` | ✅ |
| E7 | Chunking/embedding pipeline | `tests/services/test_chunking.py`, `tests/services/test_embeddings.py`, `tests/workers/test_embedding.py` | ✅ |
| Verdict services (this session) | Scoring Engine + Judge + verdict generation | `tests/services/scoring/`, `tests/crew/agents/test_judge.py`, `tests/workers/test_verdicts.py`, `tests/integration/test_transcripts_and_verdicts.py` | ✅ |
| Transcript/audio ingestion | Text + STT paths converge on one pipeline | `tests/services/test_transcription.py`, `tests/services/test_transcripts.py` | ✅ |
| E8–E21 | Pipeline/scorecards, notifications, privacy, multi-tenancy test suite, observability, verdict data model extensions, proctoring | Not built this session | ❌ Not built |

## 5. Where this leaves the release gate today

CI (`ruff` + `alembic upgrade head` + `pytest`) is green and required on every PR to `main`. That is **not** the same as "I2/I11 cross-tenant isolation is proven" — the dedicated suite [docs/04-invariants.md](docs/04-invariants.md) and [docs/09-roadmap.md](docs/09-roadmap.md) both call a release blocker (E13) does not exist yet. Until it does, treat any change touching `app/api/deps.py`, `app/workers/base.py`, or `app/services/vector_store.py` as requiring manual cross-tenant verification (§6.3's I2/I11 test-case rows) before merge, not just green CI.

---

## 6. Test case catalog

IDs are stable — reference them in PR descriptions and commit messages when a test is added/changed (`Tests: UT-014, FUNC-003`). Priority: **P0** = must pass to merge/deploy, **P1** = should pass, flag if skipped, **P2** = nice-to-have coverage.

### 6.1 Unit tests (backend) — built

Representative sample; the full set is the 28 files under `tests/` (§4's coverage map points to specifics). New unit tests for new code follow the same fake-based pattern.

| ID | Case | File | Priority |
|---|---|---|---|
| UT-001 | JWT with valid signature/claims → `HRUserClaims` | `tests/core/test_security.py` | P0 |
| UT-002 | JWT with invalid signature/expired/missing claims → `InvalidCredentialsError` | `tests/core/test_security.py` | P0 |
| UT-003 | Magic-link token round-trips claims; rejects expired/wrong-secret/wrong-type tokens | `tests/services/test_candidate_auth.py` | P0 |
| UT-004 | `get_org_scoped_db` sets `app.current_org_id` via `SET LOCAL` before yielding | `tests/api/test_deps.py` | P0 |
| UT-005 | `require_role` allows/rejects by role | `tests/api/test_deps.py` | P1 |
| UT-006 | Qdrant collection name deterministic from org UUID, differs per org | `tests/services/test_vector_store.py` | P0 |
| UT-007 | `provision_collection`/`delete_collection` idempotent (no-op if already exists/absent) | `tests/services/test_vector_store.py` | P0 |
| UT-008 | `upsert_points` produces identical point IDs on re-embed (idempotent replace, not duplicate) | `tests/services/test_vector_store.py` | P0 |
| UT-009 | `search` always includes the `organization_id` payload filter, optional `source_type`/`source_id` narrowing | `tests/services/test_vector_store.py` | P0 |
| UT-010 | Organization creation provisions Qdrant *before* the Postgres commit; Postgres failure triggers compensating Qdrant delete | `tests/services/test_organizations.py` | P0 |
| UT-011 | Organization creation never touches Postgres if Qdrant provisioning fails (fail closed) | `tests/services/test_organizations.py` | P0 |
| UT-012 | Requisition status transition guard accepts every valid `(from, to)` pair and rejects every invalid one | `tests/services/test_requisitions.py` | P0 |
| UT-013 | Resume ingestion: candidate dedup by `(org_id, email)` — reuse vs. create | `tests/services/test_ingestion.py` | P0 |
| UT-014 | Resume ingestion enqueues `parse_resume` with correct `resume_id`/`organization_id` | `tests/services/test_ingestion.py` | P1 |
| UT-015 | `parse_resume` sets `status=parsed` + `parsed_data` on success, enqueues `embed_resume` | `tests/workers/test_parsing.py` | P0 |
| UT-016 | `parse_resume` sets `status=parse_failed` + `parse_error` on any exception, does **not** enqueue embedding | `tests/workers/test_parsing.py` (I6) | P0 |
| UT-017 | `chunk_text` produces overlapping windows of the right size; rejects `overlap >= chunk_size` | `tests/services/test_chunking.py` | P0 |
| UT-018 | `embed_chunks([])` short-circuits without a network call | `tests/services/test_embeddings.py` | P1 |
| UT-019 | `embed_resume`/`embed_transcript` both funnel through `_embed_and_upsert`, differing only in `source_type` | `tests/workers/test_embedding.py` | P0 |
| UT-020 | `embed_resume` sets `embed_failed` + `embedding_error` on any exception | `tests/workers/test_embedding.py` | P0 |
| UT-021 | `score_resume_fit`/`score_transcript` are pure, deterministic (identical input → identical output twice) | `tests/services/scoring/` | P0 |
| UT-022 | `run_judge` has no default for `deterministic_score` — cannot be called without it (I12) | `tests/crew/agents/test_judge.py` | P0 |
| UT-023 | `parse_judge_result`/`parse_extraction_result` reject invalid JSON / missing / invalid fields | `tests/crew/agents/` | P1 |
| UT-024 | `generate_resume_verdict` upserts in place on re-run (no duplicate row); skips when resume unparsed | `tests/workers/test_verdicts.py` | P0 |
| UT-025 | `generate_transcript_verdict` rejects non-`completed` interviews, writes nothing (I14) | `tests/workers/test_verdicts.py` | P0 |
| UT-026 | Transcript ingestion (text and audio paths) both set `status=available` and enqueue `embed_transcript` | `tests/services/test_transcripts.py` | P0 |
| UT-027 | `org_scoped_session` sets `app.current_org_id` for the async task path (E5's request-context equivalent) | `tests/workers/test_base.py` | P0 |
| UT-028 | `model_for_role` resolves the correct configured model per crew role; sets `OPENROUTER_API_KEY` in `os.environ` | `tests/crew/test_models.py` | P1 |

### 6.2 Functional / API (route-level) tests — **gap, to be built**

None of these exist yet — every current test calls a service/task function directly, never through an actual HTTP request. This is the next testing investment this repo needs. Use `httpx.AsyncClient(transport=ASGITransport(app=app))` against `app.main.app`, with the DB/Qdrant/Celery dependencies overridden via FastAPI's `app.dependency_overrides` (fakes, same style as the unit tests) — no live services required for this layer either.

| ID | Case | Priority |
|---|---|---|
| FUNC-001 | `POST /organizations` with a valid name → 201 + a real row shape | P0 |
| FUNC-002 | `POST /organizations` when Qdrant provisioning fails → 503, no org created | P0 |
| FUNC-003 | `GET /organizations/{id}` for a nonexistent id → 404 | P1 |
| FUNC-004 | `PATCH /organizations/{id}/deactivate` → 200, status flips, idempotent on a missing org → 404 | P1 |
| FUNC-005 | `POST /hr-users` without a valid bearer token → 401 | P0 |
| FUNC-006 | `POST /hr-users` with a valid token, role mismatch on a role-gated route → 403 | P1 |
| FUNC-007 | `POST /requisitions` with a missing required field → 422 (Pydantic validation) | P1 |
| FUNC-008 | `PATCH /requisitions/{id}/status` with an invalid transition → 409, valid transition → 200 | P0 |
| FUNC-009 | `POST /applications` (resume submission) with a file → 202, Application/Resume/Candidate rows created | P0 |
| FUNC-010 | `POST /applications` for a duplicate active (candidate, requisition) pair → conflict surfaced correctly | P1 |
| FUNC-011 | `POST /interviews/{id}/transcript` with neither `text` nor `audio_file` → 400 | P0 |
| FUNC-012 | `POST /interviews/{id}/transcript` with `text` → 202, correct `source=platform_provided` | P0 |
| FUNC-013 | `POST /interviews/{id}/transcript` with an audio file → 202, STT stubbed, `source=generated_stt` | P0 |
| FUNC-014 | `GET /applications/{id}/verdicts/{service_type}` with no verdict yet → 404 + regeneration enqueued | P0 |
| FUNC-015 | `GET /applications/{id}/verdicts/{service_type}` with a stale verdict → 200 (stale data returned) + regeneration enqueued | P1 |
| FUNC-016 | `GET /health` → 200 `{"status": "ok"}` always, regardless of DB/Qdrant state (it's a liveness check, not readiness — flag if this should change once E14 lands) | P2 |
| FUNC-017 | Every route rejects a request whose bearer token's `org_id` doesn't match a path/body `organization_id`-shaped field, if any route ever accepts one as input (defense-in-depth check — audit routes for this pattern as they're added) | P0 |

### 6.3 Integration tests (live Postgres/Redis/Qdrant)

| ID | Case | File | Priority |
|---|---|---|---|
| INT-001…011 | Schema/RLS-presence/trigger/constraint checks for the original 10 tables | `tests/integration/test_initial_schema.py` | P0, built |
| INT-012…019 | Schema/RLS-presence/trigger/constraint checks for `transcripts`/`verdicts` | `tests/integration/test_transcripts_and_verdicts.py` | P0, built |
| **INT-020** | **[Gap]** Seed two orgs with candidates/resumes; authenticate as Org A; attempt to read every Org B row by ID across every table (parametrized by table name) → 404/denied on all | — | **P0, not built (I2)** |
| **INT-021** | **[Gap]** Seed two orgs' Qdrant collections with near-identical resume content; run `vector_store.search` scoped to Org A; assert zero Org B points returned regardless of similarity score | — | **P0, not built (I11)** |
| **INT-022** | **[Gap]** Construct a task payload/request with a spoofed `organization_id`; assert it cannot resolve to another org's Qdrant collection or Postgres RLS context | — | **P0, not built (I2/I11)** |
| **INT-023** | **[Gap]** Real `AsyncQdrantClient` round-trip: provision a collection, upsert points, search, delete points, delete collection — against a real (docker-compose) Qdrant, not the fake client unit tests use | — | **P1, not built** |
| INT-024 | Full `parse_resume` → `embed_resume` chain against a real Postgres row and a real (docker-compose) Qdrant collection, with Voyage/OpenRouter calls stubbed at the network boundary only | — | P1, not built |

INT-020/021/022 together **are** the E13 cross-tenant test suite — building them is the single highest-priority testing gap this plan identifies (§5, §9).

### 6.4 Smoke / sanity tests

Run before merging any change that touches the ingestion → parsing → embedding → verdict chain, and before any deploy. Currently a manual checklist (automating this as a single script is a P1 backlog item, §9).

| ID | Step | Expected result |
|---|---|---|
| SMOKE-001 | `docker compose up postgres redis qdrant` then `alembic upgrade head` | Migration completes with no errors |
| SMOKE-002 | `uvicorn app.main:app` boots, `GET /health` | `200 {"status": "ok"}` |
| SMOKE-003 | `celery -A app.workers.celery_app worker` starts | No import errors, worker registers `parse_resume`/`embed_resume`/`embed_transcript`/`generate_resume_verdict`/`generate_transcript_verdict` |
| SMOKE-004 | `POST /organizations` with a real name | 201, a real Qdrant collection named `resumechunks_{id}` exists (verify via `qdrant-client` or the Qdrant dashboard) |
| SMOKE-005 | `POST /applications` with a real resume file (requires a real `AUTH_JWKS_URL` or a locally-signed test token) | 202; within a few seconds (worker running), `resumes.status=parsed`, then `embedding_status=embedded`; points exist in the org's Qdrant collection with `source_type=resume` |
| SMOKE-006 | `GET /applications/{id}/verdicts/resume_analysis` | First call: 404 + enqueue; poll again after the worker runs: 200 with a `pass`/`review`/`fail` label and narrative (requires real `OPENROUTER_API_KEY`) |
| SMOKE-007 | `POST /interviews/{id}/transcript` with `text` | 202; shortly after, points exist in the same Qdrant collection with `source_type=transcript` |
| SMOKE-008 | `GET /applications/{id}/verdicts/transcript_review` against a `completed` interview | 200 with a verdict; against a `scheduled` interview, no verdict is ever produced (I14) |

This is the same sequence [vector.md](vector.md)'s own Verification section describes — this doc is now the canonical place it's tracked as a repeatable checklist.

### 6.5 Regression checklist (run before merging to `main`)

1. `ruff check app tests` clean.
2. `pytest` clean (unit + whatever integration tests can run — CI always runs the full set against live services).
3. `alembic upgrade head` (and, for a new migration, `alembic downgrade base` then `upgrade head` again) succeeds with no manual intervention.
4. Every invariant row in §4 marked ✅ still has a passing test — a red flag if a refactor "accidentally" made one of these tests vacuous (e.g., a fake that no longer exercises the real code path).
5. New Celery tasks are registered under the correct queue in `app/workers/celery_app.py`'s `task_routes` and use `OrgScopedTask`/`org_scoped_session`.
6. New org-scoped routes depend on `get_org_scoped_db` (or an equivalent org-scoped path), never plain `get_db`, unless explicitly justified (the way `organizations.py`'s bootstrap routes are).
7. Any new vendor call (LLM, embeddings, STT) is stubbed in its test, never live.

### 6.6 End-to-end scenarios

**Backend-only E2E `[Gap — spec, not built]`:** a single Python script (candidate for `tests/e2e/test_full_pipeline.py`, run only against `docker compose up` — the full stack, worker included — never in the default `pytest` invocation) that exercises the real HTTP API, a real running Celery worker, and real Postgres/Qdrant/Redis, with only the paid vendor calls (OpenRouter/Voyage/Whisper) stubbed via a local HTTP mock (e.g. `respx` for httpx) rather than in-process monkeypatching, since a real worker process is involved.

| ID | Scenario |
|---|---|
| E2E-001 | Create org → invite HR user → create requisition → submit resume → poll until `parsed`/`embedded` → request resume verdict → poll until a verdict exists → assert `pass`/`review`/`fail` + narrative present, no bare score anywhere in the response |
| E2E-002 | Same setup → mark an Interview `completed` → submit a transcript as text → poll until embedded → request transcript verdict → assert produced |
| E2E-003 | Same setup, but submit an audio file instead of text → assert the STT step runs (mocked) and the resulting verdict is indistinguishable in shape from E2E-002's |
| E2E-004 | Attempt a transcript verdict against a `scheduled` (not `completed`) interview → assert no verdict is ever produced, no matter how long you poll (I14) |

**Frontend E2E `[PLANNED]`:** once a frontend exists, add Playwright specs mirroring E2E-001–004 through the actual UI (HR login → post requisition → view pipeline → view verdict), plus:

| ID | Scenario (planned) |
|---|---|
| E2E-F01 | HR generalist logs in, sees only their organization's requisitions/candidates (UI-level I2 check, complementing the backend cross-tenant suite) |
| E2E-F02 | Recruiter uploads a resume via the UI, watches status update from `uploaded` → `parsed` → `embedded` without a manual refresh (or documents that it requires one, if no real-time channel is built) |
| E2E-F03 | Hiring manager views a Resume Analyzer verdict and cannot find any bare numeric score displayed anywhere in the UI (product requirement, not just an API contract) |

### 6.7 Load / performance testing `[PLANNED — no infra yet]`

Sizing is derived from A14 ([docs/02-assumptions.md](docs/02-assumptions.md)): **10–500 applications per requisition, 5–200 open requisitions per year**, i.e. a target organization processes on the order of low thousands of resumes per year, not per day — this is an interactive, not a bulk-batch, load profile. Targets below are first-cut, to be revised once a real pilot org's usage is observed (per A14/A18's own "unvalidated" framing).

| ID | Scenario | Target | Tooling |
|---|---|---|---|
| LOAD-001 | Concurrent resume submissions (`POST /applications`) | 50 concurrent submissions complete (202 returned) with p95 < 2s for the synchronous part (upload + row creation); async parse/embed backlog drains within a few minutes | Locust or k6 against docker-compose `api` |
| LOAD-002 | Embedding worker throughput | A queue of 500 pending `embed_resume` jobs drains without OOM or task loss, at whatever rate Voyage's rate limits actually allow (this is bounded by the vendor, not our code — the test's job is to confirm our retry/backoff behaves, not to beat vendor limits) | Celery + a seeded Redis queue |
| LOAD-003 | RAG retrieval query latency (`vector_store.search`) | p95 < 500ms against a collection with 10k points (roughly 500 resumes × ~20 chunks each, a full year at A14's upper bound) | Direct Qdrant client benchmark, no HTTP layer involved |
| LOAD-004 | Verdict generation end-to-end latency (Scoring Engine + RAG + Judge) | p95 under a few tens of seconds per A17's "tens of seconds is acceptable" assumption — flag to product if consistently exceeded | Timed E2E-001 runs under load |
| LOAD-005 | Sustained load soak (a full working day's worth of submissions for the largest A14 org, compressed into an hour) | No memory leak in the worker process, no connection pool exhaustion on Postgres/Qdrant | Locust scripted ramp, staging environment once it exists |

This category has zero built infrastructure today — the first concrete step is standing up a Locust or k6 script against `docker compose up`, not a staging environment (staging can come once the local numbers are sane).

### 6.8 User Acceptance Testing (UAT)

Persona-based, tied to the JTBDs in [docs/00-ideation.md](docs/00-ideation.md). Run manually before each new pilot organization's go-live; sign-off tracked outside this repo (a rollout checklist, not a `pytest` file) since it's inherently a human judgment call, not an automatable assertion.

| ID | Persona | Script |
|---|---|---|
| UAT-001 | HR Generalist (org admin) | Stand up the organization, invite the first HR users, confirm they can log in and see only their own org's data |
| UAT-002 | Recruiter | Post a requisition, submit several real (anonymized/sample) resumes, confirm parsed fields look sane for their actual candidate pool's resume formats — this is the concrete validation point for A5/A7's "resumes are mostly well-structured PDF/DOCX" assumption |
| UAT-003 | Recruiter | Request a Resume Analyzer verdict for a real candidate, judge whether the narrative is useful/trustworthy enough to act on — the concrete validation point for A24 ("one shared Judge model produces adequate quality") |
| UAT-004 | Hiring Manager | View a Transcript Reviewer verdict after a real interview, confirm the `pass`/`review`/`fail` + narrative shape reads as decision-support, not a black-box score |
| UAT-005 | HR Generalist | Submit an interview transcript both as pasted text and as an uploaded audio recording, confirm both produce a usable verdict and neither feels like a degraded second-class path |
| UAT-006 | Org admin | Attempt (or have Sift's team demonstrate) that no action in the UI/API ever exposes another organization's candidate data — the human-facing complement to the automated I2/I11 suite |

UAT sign-off for verdict-quality items (UAT-003, UAT-004) directly informs the open calibration questions in [docs/02-assumptions.md](docs/02-assumptions.md) (A24) and should be fed back into that doc, not just closed out silently.

---

## 7. CI/CD gating

**Today** ([.github/workflows/ci.yml](.github/workflows/ci.yml)): `ruff check` → `alembic upgrade head` → `pytest`, against real Postgres/Redis/Qdrant service containers, required on every PR to `main` and every push to `main`.

**Recommended additions, in priority order:**
1. **The I2/I11 cross-tenant suite (§6.3's INT-020/021/022), once built, as its own required check** — separate from the general `pytest` job so it can never be silently skipped or bundled into "tests passed" without being individually visible in the PR checks list. This is what [docs/09-roadmap.md](docs/09-roadmap.md) means by "release blocker."
2. **Functional/API tests (§6.2)** folded into the existing `pytest` job once built — no new CI job needed, just more test files.
3. **A scheduled (not per-PR) job for the E2E script (§6.6)** and, later, load tests (§6.7) — these are slower and shouldn't gate every commit, but should run on a cadence (e.g. nightly against `main`) so regressions surface within a day, not at the next pilot demo.
4. **Coverage reporting** (`pytest --cov`) surfaced in PRs, once the functional-test gap is closed enough that a coverage number means something — premature right now given §6.2's gap would just measure "how much of the untested route layer is untested."

## 8. Test data & fixtures

- Unit tests: inline fixtures per test file (no shared fixture library yet — the codebase is small enough that this hasn't become a maintenance problem; revisit if `conftest.py` sprawl starts happening).
- Integration tests: `tests/integration/conftest.py`'s `seed` fixture pattern (per-file, builds exactly the rows that file's tests need) — see `test_initial_schema.py` and `test_transcripts_and_verdicts.py` for the established shape.
- No synthetic-but-realistic resume/transcript corpus exists yet for UAT/load testing — building a small anonymized sample set (varied formats, per A5/A7's own uncertainty about real-world resume structure) is a prerequisite for UAT-002 and LOAD-001-003 being meaningful, not just mechanically passing.

## 9. Known gaps — testing roadmap

In priority order:

1. **I2/I11 cross-tenant suite (§6.3, INT-020/021/022).** The single most important gap — everything else in this plan assumes tenant isolation holds, and right now that's asserted by design/code review, not proven by a test that would fail if a future change broke it.
2. **Functional/API tests (§6.2).** Every route's actual HTTP behavior (status codes, validation errors, auth enforcement) is currently unverified except by manual smoke testing.
3. **Backend E2E script (§6.6, E2E-001–004).** Nothing today proves the full chain (upload → parse → embed → verdict) works end-to-end without a human running the smoke checklist by hand.
4. **Load testing infra (§6.7).** Zero tooling stood up; first step is a Locust/k6 script against docker-compose, not a staging environment.
5. **Frontend testing (§6.6, §6.8 planned rows).** Blocked entirely on frontend work starting — nothing to test yet.
6. **E8–E21 test coverage** (pipeline/scorecards, notifications, privacy/deletion, observability, verdict data model extensions, proctoring) — tracked in [EPIC.md](EPIC.md)'s own per-epic Definition of Done; each epic's test cases should be added to this doc's §6 tables as that epic is built, not deferred to a future testing-plan rewrite.
