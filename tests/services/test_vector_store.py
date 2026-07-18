"""Tests for app.services.vector_store's collection-naming convention
(VHIRE-2 / E2), provisioning (VHIRE-12 / E3), and point-level operations
(VHIRE-21 / E7). See docs/05-data-model.md's "Vector store (Qdrant)"
section. Uses a fake AsyncQdrantClient rather than a live Qdrant instance -
these test this module's own logic, not Qdrant itself.
"""

import uuid
from types import SimpleNamespace

import pytest
from qdrant_client import models

from app.services import vector_store
from app.services.vector_store import ChunkPoint, collection_name_for_org


def test_collection_name_is_deterministic_from_org_id():
    org_id = uuid.uuid4()

    assert collection_name_for_org(org_id) == f"resumechunks_{org_id}"


def test_collection_name_differs_per_organization():
    assert collection_name_for_org(uuid.uuid4()) != collection_name_for_org(uuid.uuid4())


class _FakeQdrantClient:
    def __init__(self, existing_collections: set[str] | None = None):
        self.existing_collections = existing_collections or set()
        self.created: list[tuple[str, models.VectorParams]] = []
        self.deleted: list[str] = []
        self.upserted: list[tuple[str, list]] = []
        self.delete_calls: list[tuple[str, object]] = []
        self.query_calls: list[dict] = []
        self.query_result_points: list = []

    async def collection_exists(self, name: str) -> bool:
        return name in self.existing_collections

    async def create_collection(self, collection_name: str, vectors_config) -> None:
        self.created.append((collection_name, vectors_config))
        self.existing_collections.add(collection_name)

    async def delete_collection(self, collection_name: str) -> None:
        self.deleted.append(collection_name)
        self.existing_collections.discard(collection_name)

    async def upsert(self, collection_name: str, points: list) -> None:
        self.upserted.append((collection_name, points))

    async def delete(self, collection_name: str, points_selector) -> None:
        self.delete_calls.append((collection_name, points_selector))

    async def query_points(self, collection_name: str, query, query_filter, limit):
        self.query_calls.append(
            {
                "collection_name": collection_name,
                "query": query,
                "query_filter": query_filter,
                "limit": limit,
            }
        )
        return SimpleNamespace(points=self.query_result_points)


@pytest.fixture
def fake_client(monkeypatch) -> _FakeQdrantClient:
    client = _FakeQdrantClient()
    vector_store.get_qdrant_client.cache_clear()
    monkeypatch.setattr(vector_store, "get_qdrant_client", lambda: client)
    return client


async def test_provision_collection_creates_when_missing(fake_client):
    org_id = uuid.uuid4()

    await vector_store.provision_collection(org_id)

    assert fake_client.created[0][0] == collection_name_for_org(org_id)


async def test_provision_collection_is_idempotent(fake_client):
    org_id = uuid.uuid4()
    fake_client.existing_collections.add(collection_name_for_org(org_id))

    await vector_store.provision_collection(org_id)

    assert fake_client.created == []


async def test_delete_collection_deletes_when_present(fake_client):
    org_id = uuid.uuid4()
    fake_client.existing_collections.add(collection_name_for_org(org_id))

    await vector_store.delete_collection(org_id)

    assert fake_client.deleted == [collection_name_for_org(org_id)]


async def test_delete_collection_is_a_noop_when_absent(fake_client):
    org_id = uuid.uuid4()

    await vector_store.delete_collection(org_id)

    assert fake_client.deleted == []


async def test_upsert_points_writes_deterministic_point_ids(fake_client):
    org_id = uuid.uuid4()
    resume_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    point = ChunkPoint(
        organization_id=org_id,
        source_type="resume",
        source_id=resume_id,
        candidate_id=candidate_id,
        chunk_index=0,
        chunk_text="chunk text",
        vector=[0.1] * 4,
    )

    await vector_store.upsert_points(org_id, [point])
    await vector_store.upsert_points(org_id, [point])

    assert len(fake_client.upserted) == 2
    first_id = fake_client.upserted[0][1][0].id
    second_id = fake_client.upserted[1][1][0].id
    assert first_id == second_id


async def test_upsert_points_payload_includes_source_discriminator(fake_client):
    org_id = uuid.uuid4()
    point = ChunkPoint(
        organization_id=org_id,
        source_type="transcript",
        source_id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        chunk_index=2,
        chunk_text="hello",
        vector=[0.0] * 4,
    )

    await vector_store.upsert_points(org_id, [point])

    payload = fake_client.upserted[0][1][0].payload
    assert payload["source_type"] == "transcript"
    assert payload["organization_id"] == str(org_id)
    assert payload["chunk_index"] == 2


async def test_upsert_points_is_a_noop_for_empty_list(fake_client):
    await vector_store.upsert_points(uuid.uuid4(), [])

    assert fake_client.upserted == []


async def test_search_applies_organization_filter(fake_client):
    org_id = uuid.uuid4()

    await vector_store.search(org_id, [0.1] * 4)

    call = fake_client.query_calls[0]
    conditions = call["query_filter"].must
    assert any(c.key == "organization_id" and c.match.value == str(org_id) for c in conditions)


async def test_search_optionally_filters_by_source_type(fake_client):
    org_id = uuid.uuid4()

    await vector_store.search(org_id, [0.1] * 4, source_type="resume")

    conditions = fake_client.query_calls[0]["query_filter"].must
    assert any(c.key == "source_type" and c.match.value == "resume" for c in conditions)


async def test_delete_points_by_source_filters_by_source_type_and_id(fake_client):
    org_id = uuid.uuid4()
    resume_id = uuid.uuid4()

    await vector_store.delete_points_by_source(org_id, source_type="resume", source_id=resume_id)

    collection_name, points_selector = fake_client.delete_calls[0]
    assert collection_name == collection_name_for_org(org_id)
    conditions = points_selector.filter.must
    assert any(c.key == "source_id" and c.match.value == str(resume_id) for c in conditions)
