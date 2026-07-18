"""Organization lifecycle: Postgres row + Qdrant collection provisioning.

VHIRE-12 (E3). Organization creation is a two-system operation with no
shared transaction — `create_organization`'s docstring states the
compensating-action design this story resolves (the open question in
docs/06-architecture.md).
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrganizationStatus
from app.models.organization import Organization
from app.services import vector_store

logger = logging.getLogger(__name__)


async def create_organization(session: AsyncSession, *, name: str) -> Organization:
    """Create an Organization row and provision its Qdrant collection.

    Ordering/compensating-action design (resolves docs/06-architecture.md's
    open question): the Qdrant collection is provisioned **first**, then
    the Postgres row is inserted and committed. The Organization's id is
    generated here in application code (rather than left to Postgres's
    `gen_random_uuid()` default) specifically so the same id can name the
    Qdrant collection before any Postgres row exists at all.

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
    organization_id = uuid.uuid4()

    await vector_store.provision_collection(organization_id)

    organization = Organization(id=organization_id, name=name)
    session.add(organization)
    try:
        await session.commit()
    except Exception:
        try:
            await vector_store.delete_collection(organization_id)
        except Exception:
            logger.exception(
                "compensating Qdrant collection delete failed for org %s after Postgres "
                "commit failure; collection is orphaned but empty (no PII)",
                organization_id,
            )
        raise

    await session.refresh(organization)
    return organization


async def get_organization(session: AsyncSession, organization_id: uuid.UUID) -> Organization | None:
    """Fetch an Organization by id, or `None` if it doesn't exist."""
    return await session.get(Organization, organization_id)


async def deactivate_organization(
    session: AsyncSession, organization_id: uuid.UUID
) -> Organization | None:
    """Deactivate an Organization and tear down its Qdrant collection.

    Returns `None` if no Organization with this id exists. Postgres side
    is updated first (status=deactivated), then the Qdrant collection is
    deleted — the reverse order from creation, since a deactivated org
    with a lingering collection is a low-severity cleanup item, while a
    deleted collection whose org row failed to update would leave that
    org's data unsearchable with no record of why.
    """
    organization = await session.get(Organization, organization_id)
    if organization is None:
        return None

    organization.status = OrganizationStatus.deactivated
    await session.commit()
    await session.refresh(organization)

    await vector_store.delete_collection(organization_id)
    return organization
