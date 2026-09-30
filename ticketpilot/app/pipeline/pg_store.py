"""Postgres hybrid retrieval for the active chunk strategy and embedding model."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EMBED_DIM, Chunk
from app.pipeline.retrieve import ScoredChunk


@dataclass
class Candidate:
    id: str
    content: str
    heading_path: str | None


class PgRetrievalStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def vector_search(
        self, embedding: list[float], strategy: str, embed_model: str, limit: int
    ) -> list[ScoredChunk]:
        if len(embedding) != EMBED_DIM:
            raise ValueError(f"embedding must have {EMBED_DIM} dimensions")
        distance = Chunk.embedding.cosine_distance(embedding)
        stmt = (
            select(Chunk.id, Chunk.content, Chunk.heading_path)
            .where(
                Chunk.strategy == strategy,
                Chunk.embed_model == embed_model,
                Chunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [Candidate(*row) for row in result.all()]

    async def fulltext_search(
        self, query: str, strategy: str, embed_model: str, limit: int
    ) -> list[ScoredChunk]:
        tsquery = func.plainto_tsquery("english", query)
        stmt = (
            select(Chunk.id, Chunk.content, Chunk.heading_path)
            .where(
                Chunk.strategy == strategy,
                Chunk.embed_model == embed_model,
                Chunk.tsv.op("@@")(tsquery),
            )
            .order_by(func.ts_rank_cd(Chunk.tsv, tsquery).desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [Candidate(*row) for row in result.all()]
