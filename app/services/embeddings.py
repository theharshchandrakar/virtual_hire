"""Voyage AI embeddings client wrapper. See docs/07-technical-stack.md:
`voyage-3`, 1024-dim - unchanged by the OpenRouter LLM-gateway pivot
(OpenRouter is an LLM gateway, not an embeddings provider, so Voyage stays
a direct integration).

VHIRE-2x (E7). Centralized here (one function, one model constant) so a
future embedding-model/dimension migration - flagged as a cross-cutting
risk in EPIC.md - stays a one-file change alongside app.services.vector_store.
"""

from functools import lru_cache

import voyageai

from app.core.config import get_settings

EMBEDDING_MODEL = "voyage-3"
"""Must match `app.services.vector_store.EMBEDDING_VECTOR_SIZE`'s dimension (1024)."""


@lru_cache
def get_voyage_client() -> voyageai.AsyncClient:
    """Return the process-wide Voyage AsyncClient, constructed once and cached."""
    settings = get_settings()
    return voyageai.AsyncClient(api_key=settings.voyage_api_key or None)


async def embed_chunks(texts: list[str]) -> list[list[float]]:
    """Embed a batch of text chunks, returning one 1024-dim vector per chunk,
    in the same order as `texts`. Returns `[]` for an empty input list
    without making a network call.
    """
    if not texts:
        return []
    client = get_voyage_client()
    result = await client.embed(texts, model=EMBEDDING_MODEL, input_type="document")
    return result.embeddings
