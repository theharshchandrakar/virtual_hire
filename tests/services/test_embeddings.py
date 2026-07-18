"""Tests for app.services.embeddings (VHIRE-2x / E7): the Voyage AI
client wrapper. Uses a fake client rather than live Voyage API calls.
"""

from types import SimpleNamespace

import pytest

from app.services import embeddings


class _FakeVoyageClient:
    def __init__(self):
        self.embed_calls: list[dict] = []

    async def embed(self, texts, model=None, input_type=None, truncation=True):
        self.embed_calls.append({"texts": texts, "model": model, "input_type": input_type})
        return SimpleNamespace(embeddings=[[0.1, 0.2] for _ in texts])


@pytest.fixture
def fake_client(monkeypatch) -> _FakeVoyageClient:
    client = _FakeVoyageClient()
    embeddings.get_voyage_client.cache_clear()
    monkeypatch.setattr(embeddings, "get_voyage_client", lambda: client)
    return client


async def test_embed_chunks_returns_empty_list_without_a_network_call(fake_client):
    result = await embeddings.embed_chunks([])

    assert result == []
    assert fake_client.embed_calls == []


async def test_embed_chunks_returns_one_vector_per_chunk_in_order(fake_client):
    result = await embeddings.embed_chunks(["chunk one", "chunk two"])

    assert result == [[0.1, 0.2], [0.1, 0.2]]
    assert fake_client.embed_calls[0]["texts"] == ["chunk one", "chunk two"]
    assert fake_client.embed_calls[0]["model"] == embeddings.EMBEDDING_MODEL
