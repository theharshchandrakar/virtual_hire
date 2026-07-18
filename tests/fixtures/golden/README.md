# Golden test dataset

Synthetic seed data + hand-verified answer keys, per [TESTING.md](../../../TESTING.md)'s §8. **No real candidate PII** — every resume/transcript here is a fabricated profile, never a real person's data (TESTING.md §8.1's governance rule).

## Layout

- `resumes/*.txt` + `resumes/*.expected.json` — one golden resume per pair. The `.txt` is real resume text (parseable by `app.services.text_extraction.extract_text` as-is — no PDF conversion needed). The `.expected.json` states the hand-verified expected `parsed_data` shape and, per requisition, the expected verdict label band.
- `requisitions/*.json` — sample job requisitions (`title`, `scorecard_template.required_skills`) that the resumes' answer keys reference by `slug`.
- `transcripts/*.txt` + `transcripts/*.expected.json` — one golden interview transcript per pair, with expected Scoring Engine output (`score_transcript`'s shape).
- `audio/` — **not yet populated.** Real or synthesized speech audio requires either a recording or a TTS step neither of which this session produced; needed only by the live-LLM tier's Whisper WER case (TESTING.md's LIVE-007), which is itself deliberately out of the required CI gate. Tracked as an open item, not silently skipped.

## What this dataset is (and isn't) used for today

- **Golden-data integrity check** (`tests/services/test_golden_data.py`) — pure Python, no network, runs in every `pytest` invocation. Confirms every resume/transcript has a well-formed, cross-referenced answer key. This catches a broken fixture, not a broken product.
- **Seeding round-trip test** (`tests/integration/test_golden_data_seeding.py`) — runs against real Postgres + Qdrant (via docker-compose in CI). Seeds this data as real rows/points using **deterministic fake embeddings** (not real Voyage calls), proving the seed → Postgres → Qdrant → retrieval plumbing works end to end. This does **not** validate real embedding quality or real LLM verdict quality — that's what TESTING.md's §7.9 live-LLM/vector tier is for, and this dataset is exactly what that tier is meant to consume once it's built (with real OpenRouter/Voyage calls, gated separately per the cost/determinism tradeoffs TESTING.md already documents).

## Maintenance

Whoever adds a new golden case hand-verifies its answer key once at creation (`verified_by`/`verified_at` fields) — the model being tested never gets to define its own ground truth. If a future prompt/model change causes a live-LLM-tier assertion against this data to start failing, that's a signal to investigate, not to quietly edit the answer key to match new output.
