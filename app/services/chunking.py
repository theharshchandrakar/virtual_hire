"""Chunking strategy shared by every RAG content type (resumes, interview
transcripts - including transcripts generated from interview audio via
STT) - the "same RAG pipeline" design described in vector.md. Word-count-
based approximation of tokens (not a real tokenizer): simple, dependency-
free, and precise enough for a chunk-size tuning parameter that
docs/05-data-model.md itself frames as an implementation detail, not a
schema decision.

VHIRE-2x (E7).
"""

DEFAULT_CHUNK_SIZE = 500
"""Approximate chunk size in words - see docs/05-data-model.md's open
question on this being an implementation-detail tuning parameter."""

DEFAULT_CHUNK_OVERLAP = 50


def chunk_text(
    text: str, *, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP
) -> list[str]:
    """Split `text` into overlapping chunks of ~`chunk_size` words each.

    Returns an empty list for empty/whitespace-only input.

    Raises:
        ValueError: if `overlap >= chunk_size` (the chunk window would
            never advance).
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = chunk_size - overlap
    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break
    return chunks
