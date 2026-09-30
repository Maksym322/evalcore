"""Ticket routes (FR-T8). Routes orchestrate only — no SQL, no prompts.

POST /tickets/eval is the EvalCore HttpAdapter endpoint (sync, bearer-auth, adapter-shaped body).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_embedder,
    get_llm,
    get_repository,
    get_store,
    require_api_token,
    require_eval_token,
)
from app.api.schemas import EvalOut, EvalRequest, TicketCreate, TicketOut
from app.ingestion.embedder import Embedder
from app.llm import LLM
from app.observability.logging import get_logger
from app.pipeline.orchestrator import answer_ticket
from app.pipeline.retrieve import RetrievalStore
from app.repository import TicketRepository
from app.settings import Settings, get_settings

router = APIRouter(prefix="/tickets", tags=["tickets"])

Repo = Annotated[TicketRepository, Depends(get_repository)]
Llm = Annotated[LLM, Depends(get_llm)]
Embed = Annotated[Embedder, Depends(get_embedder)]
Store = Annotated[RetrievalStore, Depends(get_store)]
Config = Annotated[Settings, Depends(get_settings)]


@router.post("", response_model=TicketOut, dependencies=[Depends(require_api_token)])
async def create_ticket(
    payload: TicketCreate, repo: Repo, llm: Llm, embedder: Embed, store: Store, settings: Config
) -> TicketOut:
    ticket = await repo.create(payload.title, payload.body)
    result = await answer_ticket(
        payload.body, llm=llm, embedder=embedder, store=store, settings=settings, log=get_logger()
    )
    updated = await repo.save_result(ticket.id, result)
    if updated is None:  # pragma: no cover - just-created id must exist
        raise HTTPException(500, "ticket vanished after create")
    return updated


@router.post("/eval", response_model=EvalOut, dependencies=[Depends(require_eval_token)])
async def eval_ticket(
    payload: EvalRequest, llm: Llm, embedder: Embed, store: Store, settings: Config
) -> EvalOut:
    body = payload.ticket_body()
    if not body or len(body) > 10_000:
        raise HTTPException(422, "ticket body must be 1 to 10000 characters")
    result = await answer_ticket(
        body,
        llm=llm,
        embedder=embedder,
        store=store,
        settings=settings,
        log=get_logger(),
    )
    return EvalOut.from_result(result)


@router.get("/{ticket_id}", response_model=TicketOut, dependencies=[Depends(require_api_token)])
async def get_ticket(ticket_id: str, repo: Repo) -> TicketOut:
    ticket = await repo.get(ticket_id)
    if ticket is None:
        raise HTTPException(404, "ticket not found")
    return ticket


@router.post(
    "/{ticket_id}/resolve", response_model=TicketOut, dependencies=[Depends(require_api_token)]
)
async def resolve_ticket(ticket_id: str, repo: Repo) -> TicketOut:
    ticket = await repo.set_status(ticket_id, "resolved")
    if ticket is None:
        raise HTTPException(404, "ticket not found")
    return ticket
