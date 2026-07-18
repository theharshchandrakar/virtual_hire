# Vector Store & RAG Pipeline — Implementation Guide

**Purpose:** How the RAG pipeline (resume search/matching, transcript/audio review) is actually implemented in code, for a dev who needs to touch it. For *why* the architecture looks this way, see [docs/05-data-model.md](docs/05-data-model.md)'s "Vector store (Qdrant)" section and [docs/06-architecture.md](docs/06-architecture.md) — this doc doesn't re-derive that reasoning, it documents the implementation built on top of it.

**Session scope:** this pipeline covers **resumes** and **interview transcripts (including transcripts generated from interview audio recordings via STT)**. It does **not** cover Interview Live Proctoring (E21) — that's a separate, legally-gated biometric-analysis feature (face/gaze/voice detection) that this session deliberately did not build. It also does not cover Assignment submissions/rubrics (E19's assignment half) — the Transcript Reviewer verdict scores the transcript alone.

---

## 1. One collection per Organization, one payload discriminator for content type

Every Organization has exactly one Qdrant collection, named `resumechunks_{organization_id}` (`app/services/vector_store.py:collection_name_for_org`). This collection holds chunks from **both** resumes and transcripts — there is no second collection for transcripts. A `source_type` field in each point's payload (`"resume"` or `"transcript"`) is the only thing that distinguishes them:

| Payload field | Resume points | Transcript points |
|---|---|---|
| `organization_id` | org's UUID (redundant filter, I2/I11 belt-and-suspenders) | same |
| `source_type` | `"resume"` | `"transcript"` |
| `source_id` | `resumes.id` | `transcripts.id` |
| `candidate_id` | the resume's candidate | resolved via `transcript.interview_id → interviews.application_id → applications.candidate_id` |
| `chunk_index` | ordinal position within the chunked text | same |
| `chunk_text` | the source text this vector represents | same |
| `embedded_at` | ISO timestamp | same |

This is why one set of functions — `chunk_text`, `embed_chunks`, `upsert_points`, `delete_points_by_source`, `search` — serves both content types. Nothing in `vector_store.py`, `chunking.py`, or `embeddings.py` knows or cares whether it's handling a resume or a transcript; only the caller (`app/workers/tasks/embedding.py`) supplies a different `source_type`/`source_id`.

Point IDs are deterministic: `uuid5(namespace, f"{source_type}:{source_id}:{chunk_index}")`. Re-embedding the same resume or transcript is a plain `upsert` that replaces the prior points for that source — never a duplicate, never a separate delete-then-insert (see `app/services/vector_store.py:_point_id`).

## 2. The pipeline, end to end

### Resume path
```
POST /applications (upload)
  → app.services.ingestion.submit_resume
    → Candidate create-or-reuse, Resume + Application rows, S3 upload
    → enqueue parse_resume
  → app.workers.tasks.parsing.parse_resume
    → S3 download → text_extraction.extract_text (PDF/txt/md)
    → Extraction Agent (CrewAI, Haiku 4.5 via OpenRouter by default)
    → write resumes.parsed_data, status=parsed
    → enqueue embed_resume
  → app.workers.tasks.embedding.embed_resume
    → S3 download + extract_text again (embedding wants the resume's actual
      prose, not the structured parsed_data JSON — a deliberate choice so
      chunks are semantically meaningful for similarity search)
    → chunking.chunk_text → embeddings.embed_chunks (Voyage voyage-3)
    → vector_store.delete_points_by_source (clear any prior points for this
      resume) → vector_store.upsert_points (source_type="resume")
    → write resumes.embedding_status=embedded
```

### Transcript / interview-audio path
```
POST /interviews/{id}/transcript (text OR audio_file)
  → app.services.transcripts.ingest_transcript_text / ingest_transcript_audio
    → [audio only] app.services.transcription.transcribe_audio (Whisper)
    → write transcripts.text, source, status=available
    → enqueue embed_transcript
  → app.workers.tasks.embedding.embed_transcript
    → chunking.chunk_text → embeddings.embed_chunks (same functions as above)
    → vector_store.delete_points_by_source / upsert_points (source_type="transcript")
```

By the time content reaches the embedding step, an audio recording and a platform-provided transcript are indistinguishable — both are just `transcripts.text`. The STT step is a preprocessing detail confined to `app.services.transcription` and the two `ingest_transcript_*` functions in `app.services.transcripts`; nothing downstream (chunking, embedding, retrieval, scoring) knows an audio file was ever involved.

## 3. RAG retrieval feeding the "scorecard logic" (Scoring Engine + Judge)

This is the part of the pipeline the rest of this doc has been building toward: **querying the vectorized results to produce a verdict.**

```
app.workers.tasks.verdicts.generate_resume_verdict(application_id)
  1. Scoring Engine (deterministic, no model call):
     app.services.scoring.resume_fit.score_resume_fit(parsed_data, requirements)
     → {"skill_match_ratio": ..., "matched_skills": [...], "missing_skills": [...], "flags": [...]}
  2. RAG retrieval:
     embed the requisition's title + matched/missing skills as a query
     → vector_store.search(org_id, query_vector, source_type="resume", source_id=resume.id)
     → top-k chunks from THIS candidate's own resume only (not a cross-candidate search)
  3. Judge agent (app.crew.agents.judge.run_judge):
     takes deterministic_score + retrieved chunks → returns {verdict_label, narrative}
  4. Write/overwrite a `verdicts` row (service_type=resume_analysis)
```

```
app.workers.tasks.verdicts.generate_transcript_verdict(interview_id)
  0. Gate: reject unless Interview.status == completed (I14) — writes nothing otherwise
  1. Scoring Engine: app.services.scoring.transcript_review.score_transcript(text, rubric)
  2. RAG retrieval: vector_store.search(..., source_type="transcript", source_id=transcript.id)
  3. Judge agent, same run_judge function as the resume path
  4. Write/overwrite a `verdicts` row (service_type=transcript_assignment_review)
```

**I12's ordering guarantee is enforced at the function signature, not by convention:** `run_judge(*, deterministic_score, context_chunks, task_description)` has no default for `deterministic_score` — there is no way to call it, and therefore no way to reach a Judge model call, without a Scoring Engine result already computed. `verdicts.deterministic_score` is also `NOT NULL` at the DB layer (belt-and-suspenders, matching the project's usual pattern of pairing an application-layer guarantee with a DB-layer backstop).

Verdicts regenerate in place (upsert on `(application_id, service_type)`), matching `analysis_outputs`' existing convention — no history table. `GET /applications/{id}/verdicts/{service_type}` fetches the current verdict and lazily enqueues regeneration if none exists yet or the existing one is `stale`.

## 4. Chunking

`app.services.chunking.chunk_text(text, chunk_size=500, overlap=50)` — a word-count approximation of tokens, not a real tokenizer. This is a deliberate simplification: [docs/05-data-model.md](docs/05-data-model.md) explicitly leaves chunk size/overlap as "an implementation-detail tuning parameter," and a real tokenizer (tiktoken or similar) is a dependency this session didn't judge necessary to get a working pipeline. If retrieval quality ever demands token-accurate chunking, this is the one function to change — every caller (resume and transcript embedding alike) goes through it.

## 5. Embedding model

Voyage AI `voyage-3`, 1024 dimensions (`app/services/embeddings.py`, `EMBEDDING_MODEL` constant). This is the single place the model ID lives. **Migration risk, carried over from EPIC.md's cross-cutting risks:** Qdrant's vector size is fixed per collection at creation time. Swapping embedding models or dimensions later means provisioning new collections and re-embedding every point, across every organization — not a single-table migration. There is no migration tooling for this today.

## 6. Two swappable vendor defaults chosen this session

Both are documented as **defaults picked to have working code, not final vendor decisions** — [docs/07-technical-stack.md](docs/07-technical-stack.md) explicitly leaves both open.

| | Default chosen | Config | Why swappable |
|---|---|---|---|
| Verdict/Judge model | `openrouter/deepseek/deepseek-chat` (DeepSeek-V3, fits the "200–300B-parameter class" the product brief specifies) | `JUDGE_MODEL` env var, read by `app.crew.models.model_for_role("judge")` | OpenRouter routes model access through one gateway specifically so this is a config change, not a code change (per the 07-technical-stack.md OpenRouter revision) |
| Speech-to-text (audio → text) | OpenAI Whisper (`whisper-1`) | `STT_MODEL` / `OPENAI_API_KEY`, read by `app.services.transcription` | The only STT integration point in the codebase — swapping vendors means rewriting `transcribe_audio`'s body, but nothing else changes (`ingest_transcript_audio` and everything downstream is vendor-agnostic) |

All four crew roles (extraction, summarization, reasoning, judge) resolve their OpenRouter model ID through `app.crew.models.model_for_role`, reading `EXTRACTION_MODEL`/`SUMMARIZATION_MODEL`/`REASONING_MODEL`/`JUDGE_MODEL` — a model swap for any role is an env var change. Note: summarization/reasoning models are configured but this session did not build the Summarizer or Reasoning agents themselves (E9/E10) — only Extraction and Judge exist as of this pivot.

## 7. Multi-tenancy isolation (I2 / I11)

No new isolation mechanism was introduced by adding `source_type`. The collection-per-organization boundary from the original Qdrant pivot is unchanged — resume and transcript points for Org A physically cannot be retrieved by a query scoped to Org B's collection, because there is no shared address space to filter within. The `organization_id` payload field on every point is the existing redundant belt-and-suspenders filter, applied on every `vector_store.search` call regardless of `source_type`. `organization_id` is always resolved server-side from the authenticated request (`app.api.deps`) or task payload (`app.workers.base.org_scoped_session`) — never from a client-supplied field, matching I2/I11 exactly as before.

## 8. What this session did not build

For anyone extending this pipeline, worth knowing what's deliberately absent:

- **Interview Live Proctoring (E21):** biometric/gaze/voice detection, legally gated, out of scope.
- **Assignment submissions (E19's assignment half):** no `assignments`/`assignment_submissions` tables; the Transcript Reviewer verdict scores transcript text only.
- **Standalone HR-initiated search (E10):** the RAG retrieval built here is used internally by verdict generation, scoped to one candidate's own content. There is no `POST /search` endpoint for HR users to query across candidates yet.
- **Summarizer Agent (E9):** `analysis_outputs`/candidate summaries are unbuilt; only the Extraction and Judge agents exist.
- **Token-accurate chunking:** see §4 — word-count approximation only.
