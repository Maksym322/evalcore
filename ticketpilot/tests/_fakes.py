"""Offline test doubles for the pipeline: FakeLLM, FakeEmbedder, FakeStore, recorded hits."""

from dataclasses import dataclass

from pydantic import BaseModel

from app.llm import LLMError


class FakeLLM:
    """Returns pre-recorded model outputs, or raises LLMError to simulate a failed call.

    ``response`` returns the same object for any schema; ``by_schema`` routes by the requested
    schema type (needed when one flow calls structured() with different schemas).
    """

    def __init__(
        self,
        response: BaseModel | None = None,
        *,
        by_schema: dict[type[BaseModel], BaseModel] | None = None,
        fail: bool = False,
    ) -> None:
        self._response = response
        self._by_schema = by_schema or {}
        self._fail = fail
        self.calls: list[tuple[str, str]] = []

    async def structured(self, system: str, user: str, *, schema: type[BaseModel]) -> BaseModel:
        self.calls.append((system, user))
        if self._fail:
            raise LLMError("simulated failure")
        if schema in self._by_schema:
            return self._by_schema[schema]
        if self._response is not None:
            return self._response
        raise LLMError("no recorded response for schema")


class FakeEmbedder:
    """Returns a fixed vector; records the texts it was asked to embed."""

    def __init__(self, vector: list[float] | None = None) -> None:
        self._vector = vector or [0.1, 0.2, 0.3]
        self.calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return self._vector


@dataclass
class FakeChunk:
    id: str
    content: str
    heading_path: str | None = None


class FakeStore:
    """Returns recorded vector/full-text candidates (ranked best-first)."""

    def __init__(self, vector_hits: list[FakeChunk], fulltext_hits: list[FakeChunk]) -> None:
        self._vector_hits = vector_hits
        self._fulltext_hits = fulltext_hits

    async def vector_search(
        self, embedding: list[float], strategy: str, embed_model: str, limit: int
    ) -> list[FakeChunk]:
        return self._vector_hits[:limit]

    async def fulltext_search(
        self, query: str, strategy: str, embed_model: str, limit: int
    ) -> list[FakeChunk]:
        return self._fulltext_hits[:limit]
