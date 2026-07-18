"""Qdrant collection-naming convention and client wrapper. See the "Vector
store (Qdrant)" section of docs/05-data-model.md: one collection per
Organization, named deterministically from the org's UUID and resolved
server-side from the authenticated session's org context — never a
client-supplied parameter (I11).

VHIRE-2 (E2) added the naming helper. VHIRE-12 (E3) adds the provisioning
half of the client wrapper (needed by Organization creation). VHIRE-21
(E7) adds the point-level operations (upsert/delete/search) — generalized
over a `source_type` payload discriminator (`"resume"` or `"transcript"`)
rather than a second collection, so resumes and interview transcripts
(including transcripts generated from interview audio via STT) share one
collection per organization and one code path — see vector.md for the
full pipeline. Centralizing all of it here is what lets a future
embedding-model/dimension migration stay a one-file change, per EPIC.md's
cross-cutting risks.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from qdrant_client import AsyncQdrantClient, models

from app.core.config import get_settings

_COLLECTION_PREFIX = "resumechunks_"

# Fixed namespace for deriving deterministic Qdrant point IDs via uuid5.
# Any stable UUID works here; it never changes once chosen, since changing
# it would silently orphan every previously-upserted point (re-embedding
# would create new points instead of replacing the old ones).
_POINT_ID_NAMESPACE = uuid.UUID("2f6a6f6e-6368-4b3e-9c5e-8b1a6f0a2d10")

EMBEDDING_VECTOR_SIZE = 1024
"""Voyage `voyage-3` embedding dimension — see docs/07-technical-stack.md."""

EMBEDDING_DISTANCE = models.Distance.COSINE


def collection_name_for_org(organization_id: uuid.UUID) -> str:
    """Return the deterministic Qdrant collection name for `organization_id`."""
    return f"{_COLLECTION_PREFIX}{organization_id}"


@lru_cache
def get_qdrant_client() -> AsyncQdrantClient:
    """Return the process-wide `AsyncQdrantClient`, constructed once and cached.

    Reads `QDRANT_URL`/`QDRANT_API_KEY` from `app.core.config.get_settings`.
    Construction itself doesn't touch the network — connection failures
    surface on the first real call (`provision_collection`, etc.), not here.
    """
    settings = get_settings()
    return AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


async def provision_collection(organization_id: uuid.UUID) -> None:
    """Idempotently create `organization_id`'s Qdrant collection (I11).

    Safe to call multiple times for the same `organization_id` — an
    already-existing collection is left untouched, never recreated (must
    check existence first; Qdrant's `create_collection` is not itself
    idempotent). Called by `app.services.organizations.create_organization`
    as the first half of org creation's compensating-action flow — see
    that function's docstring for the ordering/rollback design.

    Raises:
        Whatever the underlying `qdrant_client` call raises on a Qdrant-side
        failure (connection, timeout, non-2xx) — propagated as-is; the
        caller decides the compensating action.
    """
    client = get_qdrant_client()
    name = collection_name_for_org(organization_id)
    if await client.collection_exists(name):
        return
    await client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(size=EMBEDDING_VECTOR_SIZE, distance=EMBEDDING_DISTANCE),
    )


async def delete_collection(organization_id: uuid.UUID) -> None:
    """Delete `organization_id`'s Qdrant collection if it exists (idempotent).

    A missing collection is not an error. Used both as VHIRE-12's
    compensating rollback (Qdrant provisioning succeeded, the Postgres
    insert then failed) and by org-deactivation teardown.

    Raises:
        Same as `provision_collection`, for any failure other than "the
        collection already doesn't exist".
    """
    client = get_qdrant_client()
    name = collection_name_for_org(organization_id)
    if not await client.collection_exists(name):
        return
    await client.delete_collection(name)


@dataclass(frozen=True)
class ChunkPoint:
    """One chunk of source content, ready to embed and upsert.

    `source_type`/`source_id` is the payload discriminator that lets one
    collection/one set of functions serve both resumes (`source_id` =
    `resumes.id`) and interview transcripts (`source_id` = `transcripts.id`,
    regardless of whether the transcript came from a platform-provided
    transcript or was generated via STT from an interview audio
    recording — by the time it reaches this layer it's just text, per
    vector.md's "same RAG pipeline" design).
    """

    organization_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    candidate_id: uuid.UUID
    chunk_index: int
    chunk_text: str
    vector: list[float]


def _point_id(source_type: str, source_id: uuid.UUID, chunk_index: int) -> str:
    """Deterministic point ID from `(source_type, source_id, chunk_index)`.

    Makes re-embedding a plain upsert (replaces the prior point for the
    same chunk position) rather than requiring a separate delete-then-insert.
    """
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, f"{source_type}:{source_id}:{chunk_index}"))


async def upsert_points(organization_id: uuid.UUID, points: list[ChunkPoint]) -> None:
    """Upsert `points` into `organization_id`'s collection.

    Every payload carries a redundant `organization_id` field (belt-and-
    suspenders filter per I2/I11) even though the collection itself is
    already org-scoped — matches the design in docs/05-data-model.md.
    """
    if not points:
        return
    client = get_qdrant_client()
    collection = collection_name_for_org(organization_id)
    embedded_at = datetime.now(UTC).isoformat()
    qdrant_points = [
        models.PointStruct(
            id=_point_id(p.source_type, p.source_id, p.chunk_index),
            vector=p.vector,
            payload={
                "organization_id": str(p.organization_id),
                "source_type": p.source_type,
                "source_id": str(p.source_id),
                "candidate_id": str(p.candidate_id),
                "chunk_index": p.chunk_index,
                "chunk_text": p.chunk_text,
                "embedded_at": embedded_at,
            },
        )
        for p in points
    ]
    await client.upsert(collection_name=collection, points=qdrant_points)


async def delete_points_by_source(
    organization_id: uuid.UUID, *, source_type: str, source_id: uuid.UUID
) -> None:
    """Delete every point for one `(source_type, source_id)` (e.g. one Resume
    or one Transcript's chunks) — used on re-parse/re-embed and on I9
    candidate deletion.
    """
    client = get_qdrant_client()
    collection = collection_name_for_org(organization_id)
    await client.delete(
        collection_name=collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_type", match=models.MatchValue(value=source_type)
                    ),
                    models.FieldCondition(
                        key="source_id", match=models.MatchValue(value=str(source_id))
                    ),
                ]
            )
        ),
    )


async def search(
    organization_id: uuid.UUID,
    query_vector: list[float],
    *,
    source_type: str | None = None,
    source_id: uuid.UUID | None = None,
    limit: int = 10,
) -> list[models.ScoredPoint]:
    """Similarity search against `organization_id`'s collection only (I11).

    `organization_id` must always be resolved server-side from the
    authenticated session/task context (see app.api.deps and
    app.workers.base), never from client input — this function trusts its
    caller on that point and applies the redundant `organization_id`
    payload filter regardless, per I11's belt-and-suspenders design.
    Optionally narrows to one `source_type` (e.g. only resume chunks) and/or
    one `source_id` (e.g. only this candidate's own resume, for verdict
    generation rather than cross-candidate search).
    """
    client = get_qdrant_client()
    collection = collection_name_for_org(organization_id)
    must = [
        models.FieldCondition(
            key="organization_id", match=models.MatchValue(value=str(organization_id))
        )
    ]
    if source_type is not None:
        must.append(
            models.FieldCondition(key="source_type", match=models.MatchValue(value=source_type))
        )
    if source_id is not None:
        must.append(
            models.FieldCondition(key="source_id", match=models.MatchValue(value=str(source_id)))
        )

    result = await client.query_points(
        collection_name=collection,
        query=query_vector,
        query_filter=models.Filter(must=must),
        limit=limit,
    )
    return result.points
