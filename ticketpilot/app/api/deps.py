"""FastAPI dependencies (FR-T8).

LLM/Embedder/Store providers raise until the real impls are wired (Gemini client, embedder,
PgRetrievalStore) — tests override all of these. Bearer auth guards /tickets/eval.
"""

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.db import get_session
from app.gemini import GeminiLLM
from app.ingestion.embedder import Embedder
from app.ingestion.gemini_embedder import GeminiEmbedder
from app.llm import LLM
from app.pipeline.pg_store import PgRetrievalStore
from app.pipeline.retrieve import RetrievalStore
from app.repository import SqlTicketRepository, TicketRepository
from app.settings import Settings, get_settings


def get_llm(settings: Annotated[Settings, Depends(get_settings)]) -> LLM:
    if not settings.gemini_api_key:
        raise HTTPException(503, "Gemini provider not configured")
    return GeminiLLM(settings.gemini_api_key, settings.llm_model)


def get_embedder(settings: Annotated[Settings, Depends(get_settings)]) -> Embedder:
    if not settings.gemini_api_key:
        raise HTTPException(503, "Gemini embedder not configured")
    return GeminiEmbedder(settings.gemini_api_key, settings.active_embed_model)


async def get_store(session: Annotated[object, Depends(get_session)]) -> RetrievalStore:
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(session, AsyncSession)
    return PgRetrievalStore(session)


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
    if not expected or not hmac.compare_digest(authorization or "", f"Bearer {expected}"):
        raise HTTPException(401, "invalid or missing bearer token")


async def require_api_token(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.api_token
    if not expected or not hmac.compare_digest(authorization or "", f"Bearer {expected}"):
        raise HTTPException(401, "invalid or missing bearer token")
