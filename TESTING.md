# Testing Plan

**Purpose:** The single source of truth for how Sift is tested — strategy, tooling, environments, and the concrete test-case catalog. This doc is the driver: new test work starts here (add/update a test case row, then implement it), rather than being written up after the fact. Keep it current as epics land — a stale test plan is worse than none.

**Depends on:** [docs/04-invariants.md](docs/04-invariants.md) (I1–I15 are the backbone of the regression suite), [docs/02-assumptions.md](docs/02-assumptions.md) (A14 sizes load targets), [EPIC.md](EPIC.md) (each epic's own Definition of Done is a test-case source), [vector.md](vector.md) (RAG pipeline specifics), [CODE.md](CODE.md) (per-story test-writing workflow this doc's case catalog feeds into).

---

## 1. Scope

### 1.1 In scope

| Area | Detail |
|---|---|
| Backend | FastAPI API, Celery workers, Postgres schema/RLS/triggers, Qdrant vector store, CrewAI agents (Extraction, Judge), Scoring Engine — everything under `app/` in this repo today |
| RAG pipeline | Chunking, embedding (Voyage), retrieval, verdict generation (Scoring Engine + Judge) for **resumes and interview transcripts/audio** — see [vector.md](vector.md) |
| Frontend `[PLANNED]` | Next.js UI, once scaffolded — test strategy defined now so it isn't an afterthought when frontend work starts; nothing here is built yet |
| Live vendor integration testing | A separate, explicitly-gated test tier that makes real calls to OpenRouter (LLM), Voyage (embeddings), and a real Qdrant instance — see §7 |
| Multi-tenancy isolation (I2/I11) | The highest-priority test class in this whole plan — cross-org data leakage, in both Postgres and Qdrant |
| Non-functional | Load/performance (sized off A14), defect management, test reporting, logging/evidence conventions |

### 1.2 Out of scope

| Area | Why |
|---|---|
| Interview Live Proctoring (E21) | Not built — legally gated (biometric data), explicitly deferred per [docs/09-roadmap.md](docs/09-roadmap.md). No test cases for I13/I15 until the feature exists. |
| Assignment submissions (E19's assignment half) | Not built this session — no `assignments`/`assignment_submissions` tables exist yet. |
| E8–E12, E21 (pipeline/scorecards, notifications, privacy/deletion) | Not built yet — tracked as a coverage gap (§6), not tested because there's nothing to test. |
| Penetration testing / formal security audit | Distinct discipline from this plan — this doc covers the I2/I11 cross-tenant suite and routine `security-review` skill usage, not a third-party pentest engagement. |
| Accessibility (WCAG) audit | Deferred until frontend exists; flag as a `[PLANNED — not yet scoped]` line item once it does, not silently assumed covered by E2E. |
| Localization/i18n testing | Per A5/A7 in [docs/02-assumptions.md](docs/02-assumptions.md), v1 is English-only by assumption — no test coverage for other languages until that assumption is revisited. |
| Mobile app testing | No mobile app exists or is planned per [docs/07-technical-stack.md](docs/07-technical-stack.md). |
| Real candidate PII in any test environment | Never — see §8's seed-data governance rule. This is a hard boundary, not a scheduling gap. |

## 2. Testing philosophy

- **Test logic directly, not framework glue.** The house convention (already in every existing test file) is to test service/task functions with fakes for the DB session, Qdrant client, Voyage/OpenRouter/Whisper calls, boto3, and Celery's `send_task` — not to spin up a real server or mock at the HTTP layer for unit-level checks. Framework wiring (routes actually resolving, dependency injection actually firing) is a *separate*, thinner layer of functional tests (§7.2), not duplicated at the unit level.
- **Fakes over deep-mocking.** Small hand-written fake classes (`_FakeSession`, `_FakeQdrantClient`, etc.) that model just the behavior a test needs, rather than `unittest.mock.MagicMock` with elaborate `.return_value` chains — cheaper to read, cheaper to keep correct when a signature changes.
- **Determinism is tested, not assumed.** Every Scoring Engine rule module has an explicit "same input twice → same output" test (I12's own requirement) — this generalizes to anything claiming to be deterministic.
- **Cross-tenant isolation (I2/I11) is a release blocker, not a regular test class.** It gets its own CI-required check once built (§12), separate from the general suite, and is never skipped or marked "known flaky."
- **Live-dependency integration tests skip, don't fail, when the dependency is unreachable locally** (see `tests/integration/conftest.py`), but **must run for real in CI** where Postgres/Redis/Qdrant are provisioned as service containers ([.github/workflows/ci.yml](.github/workflows/ci.yml)). A test that only ever runs mocked is not proof the real trigger/RLS policy/constraint works — see §6's gap notes for where this currently falls short.
- **No vendor call runs in the default test suite.** OpenRouter/Voyage/Whisper/S3/Qdrant Cloud calls are always faked in `pytest`'s default invocation; the only "real" external dependencies the default suite touches are Postgres/Redis/Qdrant, and only via local docker-compose or CI service containers, never a hosted instance. **The one deliberate exception is the separate live-vendor test tier in §7 — opt-in, never part of the default run, never gating a PR.**

## 3. Test types, tooling & environments

### 3.1 Test type → tooling matrix

| Type | Tooling | Status | Runs |
|---|---|---|---|
| Unit | `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`, see `pyproject.toml`) | **Built, extensive** — 28 test files under `tests/` | Every commit (local), every PR/push to main (CI) |
| Functional / API (route-level) | `httpx.AsyncClient` + FastAPI's `ASGITransport` (no server process) | **Gap — not built yet** (§7.2, §13) | Would run alongside unit tests, same `pytest` invocation |
| Integration (live DB/vector store) | `pytest` + `asyncpg` direct connections, real Postgres/Redis/Qdrant via docker-compose or CI service containers | **Built, partial** — schema/RLS/trigger coverage for tables that exist; no live Qdrant integration tests yet (§13) | CI (always); locally only if `docker compose up postgres redis qdrant` |
| Smoke / sanity | A short manual (or scripted) walk of the critical path against docker-compose services | **Documented, not automated** (§7.4) | Before merging anything touching the pipeline; before any deploy |
| Regression | The I1–I15 invariant suite + epic DoD checks, run as part of the normal `pytest` suite plus the dedicated cross-tenant suite once built | **Partially built** (§6) | Every PR/push; cross-tenant suite becomes a required CI check once built |
| E2E (backend-only) | A scripted Python walk of the real API + real Celery worker + real Postgres/Qdrant/Redis (docker-compose), no UI involved | **Gap — not built yet**, spec in §7.6 | Pre-merge for pipeline-touching changes; nightly/scheduled once built |
| E2E (with frontend) `[PLANNED]` | **Playwright** (Python or TS bindings — match whichever language the frontend team standardizes tooling around; Playwright's own multi-language support makes this a non-issue either way). Ships its own Chromium/Firefox/WebKit browser binaries, so no separate browser-driver install/version-matching headache. | Not applicable yet | N/A |
| Load / performance | **Locust** (Python-native, fits this codebase's existing language, scriptable scenarios) as the primary choice; **k6** (JS-based, better raw throughput/lower resource overhead per virtual user) as an alternative if Locust's overhead becomes limiting at higher concurrency; **JMeter** listed as a third option specifically if this ever needs to satisfy an enterprise/compliance requirement for a named, GUI-driven, Java-based tool — heavier to script and maintain than the other two, not the default recommendation | **Gap — no infra yet**, targets specified in §7.7 | Pre-pilot-launch, then on a schedule (not every PR) |
| UAT | Persona-based manual scripts, sign-off tracked outside this repo (e.g. a checklist in the pilot-org rollout doc) | **Gap — no pilot org yet**, scripts specified in §7.8 | Before each new organization's pilot go-live |
| Live LLM / Vector DB testing | Real `OPENROUTER_API_KEY` + real Voyage + real Qdrant — no mocks. See §7.9 for the full design. | **Gap — spec only**, no test files yet | Manual/scheduled only, never per-PR (cost + latency + vendor non-determinism) |
| Security review | `code-review`/`security-review` skills (this repo's tooling) + the I2/I11 cross-tenant suite | Ad hoc today | Before merging auth/tenancy/PII-adjacent changes |
| Defect / ticket management | **Jira** (`VHIRE` project, already provisioned — see §10) | Built (project exists), process defined here | Whenever a test — of any type above — finds a real defect |
| Test reporting | `pytest-html` or `allure-pytest` for rich per-run reports; JUnit XML (`pytest --junitxml=`) for CI-native reporting; Locust/k6's own HTML/JSON summary export for load runs | **Gap — not wired into CI yet**, spec in §11 | Every CI run once wired up; every manual test session in the interim |

**Note on Playwright vs. Selenium:** Playwright is the recommended default for the eventual frontend E2E suite — it auto-manages browser binaries (no separate driver-version matching the way Selenium requires), has built-in auto-waiting (fewer flaky sleep-based tests), and covers Chromium/Firefox/WebKit out of the box in one API. Selenium is noted here only because it was explicitly asked about: it remains a reasonable choice if the team already has Selenium Grid infrastructure or needs a browser Playwright doesn't support, but it is not the default recommendation for a project starting its frontend E2E suite from zero.

### 3.2 Test environments

| Environment | What's running | Used for |
|---|---|---|
| **Local, no services** | Just the `.venv` + pytest | Unit tests only — the majority of the suite; DB/Qdrant-dependent tests self-skip (see `tests/integration/conftest.py`'s `_migrated_database` fixture) |
| **Local, docker-compose** (`docker compose up postgres redis qdrant`) | Real Postgres, Redis, Qdrant containers per `docker-compose.yml` | Integration tests, manual smoke walk, future E2E script |
| **Local, full stack** (`docker compose up`) | Above + the FastAPI `api` container + a Celery `worker` container | Manual smoke test end-to-end (upload → parse → embed → verdict), local load-test target |
| **CI** (`.github/workflows/ci.yml`) | Ubuntu runner, Postgres/Redis/Qdrant as GitHub Actions service containers, `alembic upgrade head`, then `pytest` | Every PR to `main` and every push to `main` — the actual release gate |
| **Live-vendor** `[Gap — not provisioned]` | Local or CI-manual run with real `OPENROUTER_API_KEY`/`VOYAGE_API_KEY` and either a real Qdrant Cloud sandbox or the same docker-compose Qdrant (Qdrant itself doesn't need to be "live vendor" — only the LLM/embedding calls do) | The §7.9 live LLM/Vector DB test tier |
| **Staging** `[PLANNED]` | Not yet provisioned — would mirror `docker-compose.yml`'s shape on real infra (ECS Fargate per [docs/07-technical-stack.md](docs/07-technical-stack.md)) with real (sandbox-tier) OpenRouter/Voyage/Whisper/S3 credentials | Load testing, UAT sign-off, pilot-org dry runs |

No test environment other than the explicitly-named **Live-vendor** tier ever uses real vendor credentials, and none of them — including that tier — ever uses production credentials or real candidate data. This follows directly from I2/I9's own posture on PII handling and is restated as a hard rule in §8.

### 3.3 Browser & runtime environment matrix `[PLANNED — no frontend yet]`

Nothing to test today (no frontend exists). Defined now so it's not improvised later:

| Target | Priority | Notes |
|---|---|---|
| Chromium (latest stable) | P0 | Playwright's default; covers Chrome and Edge (both Chromium-based) for practical purposes |
| Firefox (latest stable) | P1 | Playwright-bundled `firefox` channel |
| WebKit (Playwright's Safari proxy) | P1 | Close to Safari but not identical — real Safari verification (below) is P2, not a per-PR gate |
| Real Safari (macOS) | P2 | Only via a cloud device farm (BrowserStack/Sauce Labs) if/when Safari-specific bugs are suspected or reported — not part of routine CI given the cost/infra overhead for a B2B HR tool where enterprise customers skew Chrome/Edge |
| Mobile viewports | Out of scope | No mobile app or mobile-optimized UI planned (§1.2) |
| Screen sizes | P1 once frontend exists | Standard desktop breakpoints (1920×1080, 1366×768) — HR/recruiter tooling is a desktop-first workflow, per the product's own framing in [docs/00-ideation.md](docs/00-ideation.md) |

## 4. How to read a test case

Every test case in §7's catalog uses the same compact row format: **ID | one-line Given→Then description | file/location (or "—" if not built) | priority**. This is deliberately terse for scanability across ~70+ cases — it is not a substitute for a full test script, it's an index. IDs are stable — reference them in PR descriptions and commit messages when a test is added/changed (e.g. `Tests: UT-014, FUNC-003`).

**Priority key:** **P0** = must pass to merge/deploy · **P1** = should pass, flag if skipped · **P2** = nice-to-have coverage.
**Status key:** ✅ built and passing · ⚠️ built but with a known gap (read the note) · ❌ not built · `[PLANNED]` intentionally deferred (frontend-dependent, or explicitly out of scope for now).

When a case needs more than one line (e.g. writing a new manual UAT/smoke script), expand it to this template rather than inventing a new format:

```
ID:              UAT-003
Title:           Recruiter requests a Resume Analyzer verdict and judges its usefulness
Preconditions:   A submitted, parsed, embedded resume exists for a real (sample) candidate;
                 the requisition it's applied against has scorecard_template.required_skills set.
Steps:           1. As Recruiter, open the candidate's Application.
                 2. Request/view the Resume Analyzer verdict.
                 3. Read the pass/review/fail label and narrative.
Expected result: The narrative references specific, verifiable evidence from the resume
                 (not generic filler); the label matches the tester's own independent judgment
                 of fit at least loosely — sign-off is a judgment call, not a hard assertion.
Priority:        P0 (blocks pilot go-live if verdicts read as untrustworthy)
Status:          Gap — no pilot org yet
```

## 5. Coverage map — invariant / epic → test file

| ID | What it guarantees | Test file(s) | Status |
|---|---|---|---|
| I1 | Resume → exactly one Candidate | `tests/models/test_schema.py::test_resume_candidate_id_not_nullable`, `tests/integration/test_initial_schema.py::test_i1_resume_requires_candidate` | ✅ |
| I2 | No cross-org PII (Postgres RLS + Qdrant collection boundary) | `tests/integration/test_initial_schema.py::test_rls_enabled_on_every_org_scoped_table`, `tests/integration/test_transcripts_and_verdicts.py::test_rls_enabled_on_new_tables` (RLS *presence*) | ⚠️ **Gap**: no test yet proves RLS *behavior* (query as Org A, assert Org B rows are invisible) — see §13 |
| I3 | Same-org relationships (Application ↔ Candidate/Requisition) | `tests/integration/test_initial_schema.py::test_i3_rejects_cross_org_application`, `test_i3_allows_same_org_application` | ✅ |
| I4 | Scorecard immutability post-submit | `tests/integration/test_initial_schema.py::test_i4_direct_update_on_submitted_scorecard_rejected`, `test_i4_amend_scorecard_writes_audit_log_and_preserves_via_new_status` | ✅ |
| I5 | Valid Application status transitions | ⚠️ **Gap** — `applications.status` transition guard (the state machine in [docs/04-invariants.md](docs/04-invariants.md)) is not yet implemented (E8, out of this session's scope) | ❌ Not built |
| I6 | Resume parse state integrity (never stuck in `parsing`) | `tests/workers/test_parsing.py::test_parse_resume_failure_sets_parse_failed_and_does_not_enqueue` | ✅ |
| I7 | Interview → exactly one Application | `tests/integration/test_initial_schema.py::test_i7_interview_requires_application` | ✅ |
| I8 | Scorecard ↔ Interview 1:1 | `tests/integration/test_initial_schema.py::test_i8_scorecard_unique_per_interview` | ✅ |
| I9 | Deletion preserves aggregates | ⚠️ **Gap** — E12 (privacy/deletion) not built this session | ❌ Not built |
| I10 | AnalysisOutput only from submitted Scorecards | ⚠️ **Gap** — E9 (Summarizer) not built this session | ❌ Not built |
| I11 | RAG search never crosses org boundary | `tests/services/test_vector_store.py` (unit, collection naming + payload filter construction) | ⚠️ **Gap**: no live-Qdrant test proves cross-org isolation *in practice* — see §13 |
| I12 | Judge never runs without a Scoring Engine result | `tests/crew/agents/test_judge.py::test_run_judge_requires_deterministic_score_with_no_default`, `test_run_judge_raises_type_error_when_deterministic_score_omitted`; DB-layer: `tests/models/test_schema.py::test_verdicts_deterministic_score_not_nullable` | ✅ |
| I13 | Proctoring retention window | N/A — proctoring (E21) explicitly out of scope this session | `[PLANNED]` |
| I14 | Transcript verdict only after Interview completed | `tests/workers/test_verdicts.py::test_generate_transcript_verdict_rejects_non_completed_interview` | ✅ |
| I15 | Proctoring never intervenes live | N/A — proctoring (E21) explicitly out of scope this session | `[PLANNED]` |
| E3 | Org/HR user/requisition lifecycle | `tests/services/test_organizations.py`, `tests/services/test_hr_users.py`, `tests/services/test_requisitions.py` | ✅ |
| E4 | Candidate & resume ingestion | `tests/services/test_ingestion.py`, `tests/services/test_storage.py` | ✅ |
| E5 | Async task queue org-context propagation | `tests/workers/test_base.py` | ✅ |
| E6 | Resume parsing | `tests/workers/test_parsing.py`, `tests/services/test_text_extraction.py`, `tests/crew/agents/test_extraction.py` | ✅ |
| E7 | Chunking/embedding pipeline | `tests/services/test_chunking.py`, `tests/services/test_embeddings.py`, `tests/workers/test_embedding.py` | ✅ |
| Verdict services (this session) | Scoring Engine + Judge + verdict generation | `tests/services/scoring/`, `tests/crew/agents/test_judge.py`, `tests/workers/test_verdicts.py`, `tests/integration/test_transcripts_and_verdicts.py` | ✅ |
| Transcript/audio ingestion | Text + STT paths converge on one pipeline | `tests/services/test_transcription.py`, `tests/services/test_transcripts.py` | ✅ |
| E8–E21 | Pipeline/scorecards, notifications, privacy, multi-tenancy test suite, observability, verdict data model extensions, proctoring | Not built this session | ❌ Not built |

## 6. Where this leaves the release gate today

CI (`ruff` + `alembic upgrade head` + `pytest`) is green and required on every PR to `main`. That is **not** the same as "I2/I11 cross-tenant isolation is proven" — the dedicated suite [docs/04-invariants.md](docs/04-invariants.md) and [docs/09-roadmap.md](docs/09-roadmap.md) both call a release blocker (E13) does not exist yet. Until it does, treat any change touching `app/api/deps.py`, `app/workers/base.py`, or `app/services/vector_store.py` as requiring manual cross-tenant verification (§7.3's I2/I11 test-case rows) before merge, not just green CI.

---

## 7. Test case catalog

### 7.1 Unit tests (backend) — built

Representative sample; the full set is the 28 files under `tests/` (§5's coverage map points to specifics). New unit tests for new code follow the same fake-based pattern.

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

### 7.2 Functional / API (route-level) tests — **gap, to be built**

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

### 7.3 Integration tests (live Postgres/Redis/Qdrant)

| ID | Case | File | Priority |
|---|---|---|---|
| INT-001…011 | Schema/RLS-presence/trigger/constraint checks for the original 10 tables | `tests/integration/test_initial_schema.py` | P0, built |
| INT-012…019 | Schema/RLS-presence/trigger/constraint checks for `transcripts`/`verdicts` | `tests/integration/test_transcripts_and_verdicts.py` | P0, built |
| **INT-020** | **[Gap]** Seed two orgs with candidates/resumes; authenticate as Org A; attempt to read every Org B row by ID across every table (parametrized by table name) → 404/denied on all | — | **P0, not built (I2)** |
| **INT-021** | **[Gap]** Seed two orgs' Qdrant collections with near-identical resume content; run `vector_store.search` scoped to Org A; assert zero Org B points returned regardless of similarity score | — | **P0, not built (I11)** |
| **INT-022** | **[Gap]** Construct a task payload/request with a spoofed `organization_id`; assert it cannot resolve to another org's Qdrant collection or Postgres RLS context | — | **P0, not built (I2/I11)** |
| **INT-023** | **[Gap]** Real `AsyncQdrantClient` round-trip: provision a collection, upsert points, search, delete points, delete collection — against a real (docker-compose) Qdrant, not the fake client unit tests use | — | **P1, not built** |
| INT-024 | Full `parse_resume` → `embed_resume` chain against a real Postgres row and a real (docker-compose) Qdrant collection, with Voyage/OpenRouter calls stubbed at the network boundary only | — | P1, not built |

INT-020/021/022 together **are** the E13 cross-tenant test suite — building them is the single highest-priority testing gap this plan identifies (§6, §13).

### 7.4 Smoke / sanity tests

Run before merging any change that touches the ingestion → parsing → embedding → verdict chain, and before any deploy. Currently a manual checklist (automating this as a single script is a P1 backlog item, §13).

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

### 7.5 Regression checklist (run before merging to `main`)

1. `ruff check app tests` clean.
2. `pytest` clean (unit + whatever integration tests can run — CI always runs the full set against live services).
3. `alembic upgrade head` (and, for a new migration, `alembic downgrade base` then `upgrade head` again) succeeds with no manual intervention.
4. Every invariant row in §5 marked ✅ still has a passing test — a red flag if a refactor "accidentally" made one of these tests vacuous (e.g., a fake that no longer exercises the real code path).
5. New Celery tasks are registered under the correct queue in `app/workers/celery_app.py`'s `task_routes` and use `OrgScopedTask`/`org_scoped_session`.
6. New org-scoped routes depend on `get_org_scoped_db` (or an equivalent org-scoped path), never plain `get_db`, unless explicitly justified (the way `organizations.py`'s bootstrap routes are).
7. Any new vendor call (LLM, embeddings, STT) is stubbed in its unit/functional test, never live — live coverage belongs in §7.9 only.

### 7.6 End-to-end scenarios

**Backend-only E2E `[Gap — spec, not built]`:** a single Python script (candidate for `tests/e2e/test_full_pipeline.py`, run only against `docker compose up` — the full stack, worker included — never in the default `pytest` invocation) that exercises the real HTTP API, a real running Celery worker, and real Postgres/Qdrant/Redis, with only the paid vendor calls (OpenRouter/Voyage/Whisper) stubbed via a local HTTP mock (e.g. `respx` for httpx) rather than in-process monkeypatching, since a real worker process is involved.

| ID | Scenario |
|---|---|
| E2E-001 | Create org → invite HR user → create requisition → submit resume → poll until `parsed`/`embedded` → request resume verdict → poll until a verdict exists → assert `pass`/`review`/`fail` + narrative present, no bare score anywhere in the response |
| E2E-002 | Same setup → mark an Interview `completed` → submit a transcript as text → poll until embedded → request transcript verdict → assert produced |
| E2E-003 | Same setup, but submit an audio file instead of text → assert the STT step runs (mocked) and the resulting verdict is indistinguishable in shape from E2E-002's |
| E2E-004 | Attempt a transcript verdict against a `scheduled` (not `completed`) interview → assert no verdict is ever produced, no matter how long you poll (I14) |

**Frontend E2E `[PLANNED]`:** once a frontend exists, add Playwright specs mirroring E2E-001–004 through the actual UI (HR login → post requisition → view pipeline → view verdict), run against the browser matrix in §3.3, plus:

| ID | Scenario (planned) |
|---|---|
| E2E-F01 | HR generalist logs in, sees only their organization's requisitions/candidates (UI-level I2 check, complementing the backend cross-tenant suite) |
| E2E-F02 | Recruiter uploads a resume via the UI, watches status update from `uploaded` → `parsed` → `embedded` without a manual refresh (or documents that it requires one, if no real-time channel is built) |
| E2E-F03 | Hiring manager views a Resume Analyzer verdict and cannot find any bare numeric score displayed anywhere in the UI (product requirement, not just an API contract) |

### 7.7 Load / performance testing `[PLANNED — no infra yet]`

Sizing is derived from A14 ([docs/02-assumptions.md](docs/02-assumptions.md)): **10–500 applications per requisition, 5–200 open requisitions per year**, i.e. a target organization processes on the order of low thousands of resumes per year, not per day — this is an interactive, not a bulk-batch, load profile. Targets below are first-cut, to be revised once a real pilot org's usage is observed (per A14/A18's own "unvalidated" framing). Tooling per §3.1: Locust primary, k6/JMeter as alternatives.

| ID | Scenario | Target | Tooling |
|---|---|---|---|
| LOAD-001 | Concurrent resume submissions (`POST /applications`) | 50 concurrent submissions complete (202 returned) with p95 < 2s for the synchronous part (upload + row creation); async parse/embed backlog drains within a few minutes | Locust against docker-compose `api` |
| LOAD-002 | Embedding worker throughput | A queue of 500 pending `embed_resume` jobs drains without OOM or task loss, at whatever rate Voyage's rate limits actually allow (this is bounded by the vendor, not our code — the test's job is to confirm our retry/backoff behaves, not to beat vendor limits) | Celery + a seeded Redis queue |
| LOAD-003 | RAG retrieval query latency (`vector_store.search`) | p95 < 500ms against a collection with 10k points (roughly 500 resumes × ~20 chunks each, a full year at A14's upper bound) | Direct Qdrant client benchmark, no HTTP layer involved |
| LOAD-004 | Verdict generation end-to-end latency (Scoring Engine + RAG + Judge) | p95 under a few tens of seconds per A17's "tens of seconds is acceptable" assumption — flag to product if consistently exceeded | Timed E2E-001 runs under load, real OpenRouter calls (this specific target cannot be measured meaningfully with a mocked Judge — it's one of the few load scenarios that needs the §7.9 live tier) |
| LOAD-005 | Sustained load soak (a full working day's worth of submissions for the largest A14 org, compressed into an hour) | No memory leak in the worker process, no connection pool exhaustion on Postgres/Qdrant | Locust scripted ramp, staging environment once it exists |

This category has zero built infrastructure today — the first concrete step is standing up a Locust script against `docker compose up`, not a staging environment (staging can come once the local numbers are sane).

### 7.8 User Acceptance Testing (UAT)

Persona-based, tied to the JTBDs in [docs/00-ideation.md](docs/00-ideation.md). Run manually before each new pilot organization's go-live; sign-off tracked outside this repo (a rollout checklist, not a `pytest` file) since it's inherently a human judgment call, not an automatable assertion. See §4 for the full expanded-template version of a UAT case.

| ID | Persona | Script |
|---|---|---|
| UAT-001 | HR Generalist (org admin) | Stand up the organization, invite the first HR users, confirm they can log in and see only their own org's data |
| UAT-002 | Recruiter | Post a requisition, submit several real (anonymized/sample) resumes, confirm parsed fields look sane for their actual candidate pool's resume formats — this is the concrete validation point for A5/A7's "resumes are mostly well-structured PDF/DOCX" assumption |
| UAT-003 | Recruiter | Request a Resume Analyzer verdict for a real candidate, judge whether the narrative is useful/trustworthy enough to act on — the concrete validation point for A24 ("one shared Judge model produces adequate quality") |
| UAT-004 | Hiring Manager | View a Transcript Reviewer verdict after a real interview, confirm the `pass`/`review`/`fail` + narrative shape reads as decision-support, not a black-box score |
| UAT-005 | HR Generalist | Submit an interview transcript both as pasted text and as an uploaded audio recording, confirm both produce a usable verdict and neither feels like a degraded second-class path |
| UAT-006 | Org admin | Attempt (or have Sift's team demonstrate) that no action in the UI/API ever exposes another organization's candidate data — the human-facing complement to the automated I2/I11 suite |

UAT sign-off for verdict-quality items (UAT-003, UAT-004) directly informs the open calibration questions in [docs/02-assumptions.md](docs/02-assumptions.md) (A24) and should be fed back into that doc, not just closed out silently. Every UAT defect gets a Jira ticket per §10, not just an informal note.

### 7.9 Live LLM & Vector DB testing `[Gap — spec only, no test files yet]`

Every test elsewhere in this catalog fakes OpenRouter/Voyage/Qdrant. That proves the *code path* is correct (right prompt built, right function called, right field written) — it proves nothing about whether the **real model** produces usable output, whether **real embeddings** retrieve semantically relevant chunks, or what **real latency** looks like. This tier closes that gap, deliberately kept separate from the default suite because it costs money, has non-deterministic output, and depends on third-party availability.

**Design:**
- Location: `tests/live/` (new directory), marked with a custom pytest marker `@pytest.mark.live_llm`.
- Trigger: `pytest -m live_llm`, never part of the default `pytest` invocation and never a required CI check. Run manually, or on a schedule (e.g. weekly) against `main`.
- Gating: session-scoped fixture skips the entire file (not a hard failure) if `OPENROUTER_API_KEY`/`VOYAGE_API_KEY` aren't set to real-looking values — same "skip, don't fail, when unreachable" convention `tests/integration/conftest.py` already uses for Postgres.
- Cost control: use the smallest/cheapest configured model for exploratory runs where the specific model doesn't matter (e.g. extraction JSON-validity checks), and the real configured `JUDGE_MODEL` only for the cases that specifically need to validate that model's output quality.
- Assertions are looser than unit tests by necessity (model output isn't byte-identical run to run) — assert *shape* and *schema validity* always, assert *content quality* only against the golden answer keys in §8, with tolerance (e.g. "expected skill present in matched_skills" rather than "exact dict equality").

| ID | Case | Priority |
|---|---|---|
| LIVE-001 | Extraction Agent, called with a real sample resume (§8's golden set) → returns valid JSON with non-empty `work_history`/`skills` matching the answer key's expected fields (allow partial credit — flag if match rate drops below a set threshold, e.g. 80%) | P0 |
| LIVE-002 | Extraction Agent, called with a deliberately malformed/near-empty resume text → does not crash; either returns a minimal valid JSON shape or the caller's existing failure path (`parse_failed`) engages correctly | P1 |
| LIVE-003 | Judge Agent, called with a real Scoring Engine output + real retrieved chunks (from a real Voyage-embedded, real-Qdrant-searched golden resume) → returns valid `{verdict_label, narrative}` JSON, `verdict_label` is one of the three allowed values, `narrative` is non-empty and references specifics (not generic filler — a human-reviewed pass/fail judgment, tracked as a UAT-003-style sign-off, not a strict assertion) | P0 |
| LIVE-004 | Voyage `embed_chunks` on a real chunk of resume text → returns a 1024-dim vector (dimension check), and embedding the *same* text twice produces cosine similarity ≈ 1.0 (embedding stability check) | P0 |
| LIVE-005 | Real Qdrant round-trip: upsert a golden resume's real embeddings, run a real semantic query for a skill known (from the answer key) to be present → the golden resume's chunk is retrieved in the top-k results | P0 |
| LIVE-006 | Real Qdrant round-trip: run a semantic query for a skill known to be **absent** from a golden resume → confirm it is *not* artificially forced into top-k (sanity check that retrieval isn't just "always return everything") | P1 |
| LIVE-007 | Whisper STT on a real short sample audio clip (§8's golden set) with a known transcript → resulting text has an acceptable word-error-rate against the golden transcript (exact match not expected/required) | P1 |
| LIVE-008 | End-to-end latency measurement for LIVE-001/003/005/007 individually, logged (not just asserted pass/fail) — feeds LOAD-004's real-world target validation | P1 |

**What this tier deliberately does not do:** it does not gate merges, it does not run on every PR, and it is not a substitute for the mocked unit/functional tests — those still need to exist and pass on every commit regardless of how well the live tier performs on any given day.

---

## 8. Seed data & golden answer keys

Every test type above that touches real content (live LLM/vector tests in §7.9, load tests in §7.7, UAT in §7.8) needs realistic-but-safe data to run against — and for anything asserting on *quality* (not just "didn't crash"), it needs a known-correct answer to grade against, not just plausible-looking input.

### 8.1 Governance — the hard rule

**No real candidate PII, ever, in any test environment, including the live-vendor tier.** All seed resumes/transcripts/audio are either:
1. Fully synthetic (LLM-generated or hand-written fictional profiles), or
2. Genuinely donated/anonymized samples with explicit consent and all identifying details scrubbed/replaced.

This is a direct extension of I2/I9's PII posture, not a separate policy — a test environment is not exempt from the same rules production data handling follows.

### 8.2 What's needed

| Dataset | Contents | Answer key | Used by |
|---|---|---|---|
| **Golden resumes** | ~15–20 synthetic resumes spanning: clean well-structured PDF, messy/dense PDF, plain-text, a resume with sparse/missing sections, varied seniority levels and skill sets (per A5/A7's own uncertainty about real-world resume structure — this set should deliberately include the "hard" cases, not just the easy ones) | A paired `*.expected.json` per resume: expected `work_history`/`education`/`skills` (for Extraction Agent grading, LIVE-001), expected `matched_skills` against 2–3 sample requisitions (for Scoring Engine + Judge grading, LIVE-003, UAT-002/003) | LIVE-001–006, LOAD-001–003, UAT-002/003 |
| **Golden requisitions** | 3–5 sample job requisitions with `scorecard_template.required_skills` populated, spanning at least one role each golden resume set is a strong/weak/partial match for | Expected pass/review/fail band per (resume, requisition) pair, calibrated by a human reviewer once, then used as the regression baseline for future model/prompt changes | LIVE-003, UAT-003 |
| **Golden transcripts** | 5–10 synthetic interview transcripts of varying length/quality (including at least one deliberately below any minimum-length rubric threshold, to exercise `transcript_review`'s flag) | Expected `score_transcript` flags, expected verdict band | UT-021 (already covered, no live data needed), LIVE-003 equivalent for transcripts, UAT-004/005 |
| **Golden audio clips** | 3–5 short (under a minute) synthetic or donated-and-anonymized audio clips with a known correct transcript | The known correct transcript text, for word-error-rate comparison | LIVE-007, UAT-005 |
| **Bulk synthetic volume** | A scripted generator (not hand-authored) producing hundreds of resumes at A14's upper-bound volume, quality not curated (this set is for throughput, not quality grading) | None needed — these are throughput filler, not graded | LOAD-001–005 |

### 8.3 Storage & maintenance

- Location: `tests/fixtures/golden/` (new directory) — `resumes/`, `requisitions/`, `transcripts/`, `audio/`, each file paired with a `.expected.json` of the same basename.
- Ownership: whoever adds a new golden case is responsible for hand-verifying its answer key once at creation time (a human, not the model being tested, decides ground truth) — noted as a comment/metadata field in the `.expected.json` itself (`"verified_by"`, `"verified_at"`).
- Versioning: if a model/prompt change causes a previously-passing LIVE-* case to start failing against its golden answer key, that's a real signal (either a regression, or the golden answer key itself needs revisiting) — never silently update the golden file to match new output without a human deciding which one was wrong.
- This dataset does not exist yet — building even the minimum viable slice (5 resumes + answer keys, 2 requisitions) is a prerequisite for LIVE-001–006 and UAT-002/003 being meaningful rather than just mechanically executed. Tracked in §13.

### 8.4 Fixture code (existing, unrelated to golden data)

- Unit tests: inline fixtures per test file (no shared fixture library yet — the codebase is small enough that this hasn't become a maintenance problem; revisit if `conftest.py` sprawl starts happening).
- Integration tests: `tests/integration/conftest.py`'s `seed` fixture pattern (per-file, builds exactly the rows that file's tests need) — see `test_initial_schema.py` and `test_transcripts_and_verdicts.py` for the established shape. This is distinct from the golden dataset above — integration-test seed rows are structurally minimal (just enough to exercise a constraint), not content-realistic.

## 9. Logging & test evidence

Distinct from application logging (`app/`'s own structured logging, tracked under EPIC.md's E14) — this section is about what test *runs themselves* should log, so a failure (or a live-tier pass) leaves enough evidence to act on without re-running.

- **Failures always log the full context that produced them.** For live LLM tests (§7.9) specifically, a failed assertion must capture and print/save the raw model response (prompt + output), not just "assertion failed: expected X got Y" — otherwise a live-model failure is nearly impossible to debug after the fact given non-determinism. Use `pytest`'s `caplog` fixture plus an explicit `print()`/log line inside each LIVE-* test's failure path, not just relying on pytest's default assertion diff.
- **Test affirmation, not just failure, gets logged for the live tier.** Every LIVE-* run should log a one-line pass confirmation with the key evidence (e.g. `LIVE-005 PASS: query "kubernetes" retrieved golden_resume_03 chunk 2, score=0.87`), not just a bare green checkmark — this is what makes a scheduled/manual live-tier run auditable without re-running it to see what actually happened.
- **Structured over free-text where practical.** Prefer `logger.info("event", extra={...})`-style structured fields (mirroring the convention `app/` itself should use per E14) over free-text log lines in any new test logging, so logs are greppable/filterable in CI artifact output.
- **CI captures logs as artifacts.** `pytest`'s default captured-output-on-failure behavior is enough for the mocked suite; once the live tier (§7.9) exists and runs on a schedule, its run should upload a log file as a CI artifact (`actions/upload-artifact`) rather than relying on console scrollback, since these runs are infrequent enough that scrollback won't be around when someone investigates a week later.
- **Load test runs log their own summary artifact** (Locust's HTML report / CSV stats export) rather than only printing a live TUI — this is what gets attached to the Jira ticket or PR when reporting a LOAD-* result (§11).

## 10. Defect / findings / ticket management

**Tool: Jira**, project key `VHIRE` (already provisioned — see `CLAUDE.md`'s 2026-07-15 entry for how it was set up; `JIRA_BASE_URL`/`JIRA_PROJECT_KEY` etc. are in `.env.example`). This plan does not introduce a new tracker — it uses the one this repo already has.

### 10.1 When to file a ticket

Any test failure in §7 that represents a **real product/code defect** (not a flaky test, not an environment issue, not an intentionally-failing negative-path assertion) gets a Jira ticket. A test simply going red in CI is not itself the record of the defect — the ticket is.

### 10.2 Ticket conventions

| Field | Convention |
|---|---|
| Issue type | `Bug` (distinct from the `Story`/`Epic` types already used for feature work per `EPIC.md`'s Jira sync) |
| Summary | Include the test ID that caught it, e.g. `[FUNC-008] Requisition status PATCH accepts an invalid transition` |
| Description | What broke, the test ID/file, repro steps, expected vs. actual, environment (local/CI/staging/live-vendor tier) |
| Priority | Map from the test case's own priority (§4's P0/P1/P2) — a P0 test case's failure is at minimum a Jira `High`, never `Low` |
| Labels | Test category as a label (`unit`, `functional`, `integration`, `smoke`, `e2e`, `load`, `uat`, `live-llm`) so defects are filterable by which testing layer caught them — useful for spotting if one layer is catching a disproportionate share of real bugs, a signal the test pyramid balance needs revisiting |
| Linked to | The epic (`VHIRE-*`) the affected code belongs to, per `EPIC.md`'s existing epic↔story linkage |

### 10.3 Lifecycle

`New → Triaged → In Progress → Fixed (PR open) → Verified (test now passes, re-run confirmed) → Closed`. A ticket is not closed on "PR merged" — it's closed once the originating test case (or a new regression test, if none existed) is confirmed green, closing the loop back to §7's catalog.

### 10.4 Triage cadence

Given this is currently a small/solo-adjacent team (per this repo's own `CONTRIBUTING.md` Lead-Architect-review model), there's no formal recurring triage meeting yet — P0 defects get triaged same-day by whoever's reviewing the failing PR; P1/P2 defects get triaged at the start of the next work session touching that area. Revisit this cadence once the team grows past the current single-reviewer model.

## 11. Findings & reporting mechanisms

| Test type | Report artifact | Where it lives |
|---|---|---|
| Unit / functional / integration (CI) | `pytest`'s console output (pass/fail counts) today; `[Gap]` JUnit XML (`pytest --junitxml=report.xml`) surfaced as a GitHub Actions check annotation, once wired up | CI run logs today; `[PLANNED]` a proper CI-native test report |
| Unit / functional / integration (local, ad hoc) | `[Gap]` `pytest-html` or `allure-pytest` for a browsable HTML report when debugging a larger local run | Not wired up yet — plain console output today |
| Smoke / sanity | The checklist in §7.4 itself, checked off manually; result (pass/fail per step, date, who ran it) recorded in the PR description for pipeline-touching changes | PR description; no separate report file |
| E2E (backend script, once built) | Script's own pass/fail summary + timing per scenario; `[PLANNED]` upload as a CI artifact for the scheduled nightly run | CI artifacts once built |
| Load tests | Locust's built-in HTML report (or k6's JSON/HTML summary) — request counts, latency percentiles, failure rate | Attached to the relevant Jira ticket (§10) or PR when reporting a LOAD-* result; archived location TBD once staging exists |
| Live LLM/Vector DB tests | Per-case pass/fail + evidence line (§9) from the scheduled run's log; `[PLANNED]` a short weekly summary (pass rate trend per LIVE-* case) so model/prompt drift is visible over time, not just per-run | CI artifact (log upload) once the tier is built |
| UAT | The expanded test-case template from §4, filled in per persona/script, signed off by name+date; aggregated into a single go/no-go summary before a pilot org's launch | A rollout checklist doc per pilot org (outside this repo — this repo tracks the *scripts*, not per-customer sign-off records) |
| Defects | Jira `VHIRE` project (§10) is the system of record for individual findings | Jira |
| Overall release readiness | The §7.5 regression checklist, run and confirmed before any merge to `main`; §6's "where this leaves the release gate" statement kept current as an honest running summary, not a one-time snapshot | This document |

**Reporting cadence:** CI results are inherently per-commit/per-PR (continuous). Load and live-LLM tier results are point-in-time snapshots tied to whenever they're run (§3.1's "manual/scheduled only") — each such run should be summarized (pass rate, notable regressions, any new Jira tickets filed) in whatever channel the team already uses for async updates, rather than silently living only in a CI artifact nobody opens.

---

## 12. CI/CD gating

**Today** ([.github/workflows/ci.yml](.github/workflows/ci.yml)): `ruff check` → `alembic upgrade head` → `pytest`, against real Postgres/Redis/Qdrant service containers, required on every PR to `main` and every push to `main`.

**Recommended additions, in priority order:**
1. **The I2/I11 cross-tenant suite (§7.3's INT-020/021/022), once built, as its own required check** — separate from the general `pytest` job so it can never be silently skipped or bundled into "tests passed" without being individually visible in the PR checks list. This is what [docs/09-roadmap.md](docs/09-roadmap.md) means by "release blocker."
2. **Functional/API tests (§7.2)** folded into the existing `pytest` job once built — no new CI job needed, just more test files.
3. **A scheduled (not per-PR) job for the E2E script (§7.6)**, **the live LLM/Vector DB tier (§7.9)**, and **load tests (§7.7)** — all three are slower, cost money, or are non-deterministic, and shouldn't gate every commit, but should run on a cadence (e.g. nightly/weekly against `main`) so regressions surface within days, not at the next pilot demo.
4. **JUnit XML + coverage reporting** (`pytest --cov --junitxml=`) surfaced in PRs, once the functional-test gap is closed enough that a coverage number means something — premature right now given §7.2's gap would just measure "how much of the untested route layer is untested."

---

## 13. Known gaps — testing roadmap

In priority order:

1. **I2/I11 cross-tenant suite (§7.3, INT-020/021/022).** The single most important gap — everything else in this plan assumes tenant isolation holds, and right now that's asserted by design/code review, not proven by a test that would fail if a future change broke it.
2. **Functional/API tests (§7.2).** Every route's actual HTTP behavior (status codes, validation errors, auth enforcement) is currently unverified except by manual smoke testing.
3. **Golden seed dataset (§8.2).** Blocks the live LLM/vector tier (§7.9) and quality-focused UAT (UAT-002/003) from being meaningful — needs at minimum 5 golden resumes + 2 requisitions + answer keys before those test cases are anything more than a spec.
4. **Live LLM & Vector DB test tier (§7.9).** Zero test files exist; this is the only place real model/embedding quality and real latency get validated at all today.
5. **Backend E2E script (§7.6, E2E-001–004).** Nothing today proves the full chain (upload → parse → embed → verdict) works end-to-end without a human running the smoke checklist by hand.
6. **Load testing infra (§7.7).** Zero tooling stood up; first step is a Locust script against docker-compose, not a staging environment.
7. **Test reporting wiring (§11).** JUnit XML/coverage/HTML reports aren't produced anywhere yet — today's only artifact is raw CI console output.
8. **Frontend testing (§3.3, §7.6, §7.8 planned rows).** Blocked entirely on frontend work starting — nothing to test yet.
9. **E8–E21 test coverage** (pipeline/scorecards, notifications, privacy/deletion, observability, verdict data model extensions, proctoring) — tracked in [EPIC.md](EPIC.md)'s own per-epic Definition of Done; each epic's test cases should be added to this doc's §7 tables as that epic is built, not deferred to a future testing-plan rewrite.
