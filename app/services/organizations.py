"""Organization lifecycle: Postgres row + Qdrant collection provisioning.

VHIRE-12 (E3). Organization creation is a two-system operation with no
shared transaction — `create_organization`'s docstring states the
compensating-action design this story resolves (the open question in
docs/06-architecture.md).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization


async def create_organization(session: AsyncSession, *, name: str) -> Organization:
    """Create an Organization row and provision its Qdrant collection.

    Ordering/compensating-action design (resolves docs/06-architecture.md's
    open question): the Qdrant collection is provisioned **first**, then
    the Postgres row is inserted and committed.

    - If Qdrant provisioning fails: no Postgres row is created at all
      (fail closed — an Organization never exists without a working
      collection to search against, per I11). The caller should surface
      this as a 503, not a 500.
    - If Qdrant succeeds but the Postgres insert/commit then fails: this
      function makes a best-effort `vector_store.delete_collection` call
      on the just-created (empty, unreferenced) collection before
      re-raising the original DB error. If that best-effort delete itself
      fails, the result is an orphaned *empty* collection with no
      embedding/PII data in it and no `organization_id` anywhere pointing
      at it — a low-severity cleanup item, never a cross-tenant exposure.
      No reconciliation job for this exists yet (out of scope for this
      story).

    Raises:
        Whatever `app.services.vector_store.provision_collection` raises
            on Qdrant failure (propagated untouched).
        sqlalchemy.exc.SQLAlchemyError: if the Postgres insert/commit
            fails after Qdrant provisioning already succeeded (raised
            after the best-effort compensating delete above).
    """
    raise NotImplementedError("VHIRE-12")


async def get_organization(session: AsyncSession, organization_id: uuid.UUID) -> Organization | None:
    """Fetch an Organization by id, or `None` if it doesn't exist."""
    raise NotImplementedError("VHIRE-12")
