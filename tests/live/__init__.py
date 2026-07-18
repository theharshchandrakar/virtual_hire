"""Live-vendor test tier (TESTING.md §7.9): real OpenRouter + Voyage +
Qdrant calls against the golden dataset. Never mocked, never part of
the default `pytest` invocation elsewhere in this repo - opt in via
`pytest -m live_llm` (or the dedicated CI job that sets the real
OPENROUTER_API_KEY/VOYAGE_API_KEY secrets)."""
