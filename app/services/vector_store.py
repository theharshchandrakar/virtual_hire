"""Qdrant collection-naming convention and client wrapper. See the "Vector
store (Qdrant)" section of docs/05-data-model.md: one collection per
Organization, named deterministically from the org's UUID and resolved
server-side from the authenticated session's org context — never a
client-supplied parameter (I11).

VHIRE-2 (E2) added the naming helper, since app.api.deps needs it to build
the second half of the request-scoped context (Postgres RLS + Qdrant
collection). VHIRE-12 (E3) adds the provisioning half of the client
wrapper (needed by Organization creation); VHIRE-21 (E7) extends this same
module with point upsert/delete-by-resume/search — centralizing all of it
here is what lets a future embedding-model/dimension migration stay a
one-file change, per EPIC.md's cross-cutting risks.
"""

import uuid
from functools import lru_cache

from qdrant_client import AsyncQdrantClient, models

_COLLECTION_PREFIX = "resumechunks_"

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
    raise NotImplementedError("VHIRE-12")


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
    raise NotImplementedError("VHIRE-12")


async def delete_collection(organization_id: uuid.UUID) -> None:
    """Delete `organization_id`'s Qdrant collection if it exists (idempotent).

    A missing collection is not an error. Used both as VHIRE-12's
    compensating rollback (Qdrant provisioning succeeded, the Postgres
    insert then failed) and by VHIRE-25's future org-deactivation teardown.

    Raises:
        Same as `provision_collection`, for any failure other than "the
        collection already doesn't exist".
    """
    raise NotImplementedError("VHIRE-12")
