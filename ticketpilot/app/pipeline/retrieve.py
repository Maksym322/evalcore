"""Retrieve stage (FR-T5): hybrid vector + full-text, fused with RRF (§3.2).

The concrete pgvector/full-text SQL lives behind ``RetrievalStore``; the real Postgres impl
is a later sub-task, tests inject a fake. ``rrf_merge`` is pure and independently tested.
"""

from typing import Protocol

from app.ingestion.embedder import Embedder
from app.observability.logging import Logger, stage_timer
from app.pipeline.models import Retrieval, RetrievedChunk
from app.settings import Settings

RRF_K = 60
_CANDIDATES = 20


class ScoredChunk(Protocol):
    """A candidate returned by the store (raw search score is unused after fusion)."""

    id: str
    content: str
    heading_path: str | None


class RetrievalStore(Protocol):
    """Backend searches. Each returns candidates ranked best-first."""

    async def vector_search(
        self, embedding: list[float], strategy: str, embed_model: str, limit: int
    ) -> list[ScoredChunk]: ...

    async def fulltext_search(
        self, query: str, strategy: str, embed_model: str, limit: int
    ) -> list[ScoredChunk]: ...


def rrf_merge(ranked_lists: list[list[str]], *, k: int = RRF_K) -> dict[str, float]:
    """Reciprocal Rank Fusion: score(id) = sum 1/(k + rank) over lists (rank is 1-based)."""
    fused: dict[str, float] = {}
    for ids in ranked_lists:
        for rank, doc_id in enumerate(ids, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return fused


async def retrieve(
    body: str, *, embedder: Embedder, store: RetrievalStore, settings: Settings, log: Logger
) -> Retrieval:
    with stage_timer(log, "retrieve"):
        query_embedding = await embedder.embed(body)
        vec_hits = await store.vector_search(
            query_embedding, settings.active_strategy, settings.active_embed_model, _CANDIDATES
        )
        ft_hits = await store.fulltext_search(
            body, settings.active_strategy, settings.active_embed_model, _CANDIDATES
        )

        by_id = {c.id: c for c in [*vec_hits, *ft_hits]}
        fused = rrf_merge([[c.id for c in vec_hits], [c.id for c in ft_hits]])
        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[: settings.top_k]

        chunks = [
            RetrievedChunk(
                id=cid,
                content=by_id[cid].content,
                score=score,
                heading_path=by_id[cid].heading_path,
            )
            for cid, score in ranked
        ]
        max_rrf = chunks[0].score if chunks else 0.0
        log.info("retrieved", retrieved_ids=[c.id for c in chunks], max_rrf_score=max_rrf)
        return Retrieval(chunks=chunks, max_rrf_score=max_rrf)
