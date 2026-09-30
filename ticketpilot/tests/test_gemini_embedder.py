"""Embedding dimensions and query/document task types stay compatible with pgvector."""

import httpx
import pytest

from app.ingestion.embedder import EmbedderError
from app.ingestion.gemini_embedder import GeminiEmbedder
from app.models import EMBED_DIM


async def test_query_and_document_embeddings() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"embedding": {"values": [0.1] * EMBED_DIM}})

    client = GeminiEmbedder(
        "fake-key", "gemini-embedding-2", transport=httpx.MockTransport(respond)
    )
    assert len(await client.embed("search")) == EMBED_DIM
    assert len(await client.embed_document("source")) == EMBED_DIM
    assert b"RETRIEVAL_QUERY" in requests[0].content
    assert b"RETRIEVAL_DOCUMENT" in requests[1].content
    assert b"1536" in requests[0].content


async def test_wrong_dimension_fails_before_db_insert() -> None:
    client = GeminiEmbedder(
        "fake-key",
        "gemini-embedding-2",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"embedding": {"values": [0.1, 0.2]}})
        ),
    )
    with pytest.raises(EmbedderError, match="1536"):
        await client.embed("search")
