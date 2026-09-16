"""FastAPI dependencies (FR-T8).

LLM/Embedder/Store providers raise until the real impls are wired (Gemini client, embedder,
PgRetrievalStore) — tests override all of these. Bearer auth guards /tickets/eval.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.db import get_session
from app.ingestion.embedder import Embedder
from app.llm import LLM
from app.pipeline.retrieve import RetrievalStore
from app.repository import SqlTicketRepository, TicketRepository
from app.settings import Settings, get_settings


def get_llm() -> LLM:
    raise HTTPException(503, "LLM provider not configured")


def get_embedder() -> Embedder:
    raise HTTPException(503, "embedder not configured")


def get_store() -> RetrievalStore:
    raise HTTPException(503, "retrieval store not configured")


async def get_repository(
    session: Annotated[object, Depends(get_session)],
) -> TicketRepository:
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(session, AsyncSession)
    return SqlTicketRepository(session)


async def require_eval_token(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.eval_token
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(401, "invalid or missing bearer token")
