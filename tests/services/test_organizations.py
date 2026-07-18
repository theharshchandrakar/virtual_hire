"""Tests for app.services.organizations (VHIRE-12 / E3): the two-system
(Qdrant-then-Postgres) organization creation flow and its compensating
rollback, plus deactivation teardown. Uses fakes for both the DB session
and app.services.vector_store rather than live Postgres/Qdrant - these
test this module's own ordering/error-handling logic.
"""

import uuid

import pytest

from app.models.enums import OrganizationStatus
from app.models.organization import Organization
from app.services import organizations, vector_store


class _FakeSession:
    def __init__(self, *, fail_commit: bool = False):
        self.added: list[Organization] = []
        self.fail_commit = fail_commit
        self.commit_calls = 0
        self.store: dict[uuid.UUID, Organization] = {}

    def add(self, obj: Organization) -> None:
        self.added.append(obj)
        self.store[obj.id] = obj

    async def commit(self) -> None:
        self.commit_calls += 1
        if self.fail_commit:
            raise RuntimeError("simulated Postgres commit failure")

    async def refresh(self, obj: Organization) -> None:
        return None

    async def get(self, model, obj_id):
        return self.store.get(obj_id)


@pytest.fixture
def track_vector_store_calls(monkeypatch):
    calls = {"provisioned": [], "deleted": []}

    async def _provision(organization_id):
        calls["provisioned"].append(organization_id)

    async def _delete(organization_id):
        calls["deleted"].append(organization_id)

    monkeypatch.setattr(vector_store, "provision_collection", _provision)
    monkeypatch.setattr(vector_store, "delete_collection", _delete)
    return calls


async def test_create_organization_provisions_collection_before_postgres_commit(
    track_vector_store_calls,
):
    session = _FakeSession()

    org = await organizations.create_organization(session, name="Acme Corp")

    assert track_vector_store_calls["provisioned"] == [org.id]
    assert session.commit_calls == 1
    assert org.name == "Acme Corp"


async def test_create_organization_rolls_back_qdrant_on_postgres_commit_failure(
    track_vector_store_calls,
):
    session = _FakeSession(fail_commit=True)

    with pytest.raises(RuntimeError):
        await organizations.create_organization(session, name="Acme Corp")

    assert len(track_vector_store_calls["provisioned"]) == 1
    assert track_vector_store_calls["deleted"] == track_vector_store_calls["provisioned"]


async def test_create_organization_does_not_touch_postgres_if_qdrant_provisioning_fails(
    monkeypatch,
):
    async def _fail_provision(organization_id):
        raise RuntimeError("simulated Qdrant failure")

    monkeypatch.setattr(vector_store, "provision_collection", _fail_provision)
    session = _FakeSession()

    with pytest.raises(RuntimeError):
        await organizations.create_organization(session, name="Acme Corp")

    assert session.added == []
    assert session.commit_calls == 0


async def test_get_organization_returns_none_when_missing():
    session = _FakeSession()

    assert await organizations.get_organization(session, uuid.uuid4()) is None


async def test_deactivate_organization_updates_status_and_deletes_collection(
    track_vector_store_calls,
):
    session = _FakeSession()
    org = Organization(id=uuid.uuid4(), name="Acme Corp")
    session.store[org.id] = org

    result = await organizations.deactivate_organization(session, org.id)

    assert result.status == OrganizationStatus.deactivated
    assert track_vector_store_calls["deleted"] == [org.id]


async def test_deactivate_organization_returns_none_when_missing(track_vector_store_calls):
    session = _FakeSession()

    result = await organizations.deactivate_organization(session, uuid.uuid4())

    assert result is None
    assert track_vector_store_calls["deleted"] == []
