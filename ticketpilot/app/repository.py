"""Ticket persistence (FR-T8). Protocol + SQLAlchemy impl; routes never touch SQL.

``SqlTicketRepository`` is integration-tested against a live DB later; route tests use a fake.
"""

from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AnswerOut, TicketOut
from app.models import Ticket
from app.pipeline.models import PipelineResult


class TicketRepository(Protocol):
    async def create(self, title: str | None, body: str) -> TicketOut: ...
    async def get(self, ticket_id: str) -> TicketOut | None: ...
    async def save_result(self, ticket_id: str, result: PipelineResult) -> TicketOut | None: ...
    async def set_status(self, ticket_id: str, status: str) -> TicketOut | None: ...


def _to_out(t: Ticket) -> TicketOut:
    answer = None
    if t.answer is not None:
        answer = AnswerOut(
            text=str(t.answer.get("text", "")),
            citations=list(t.answer.get("citations", [])),
            grounded=bool(t.answer.get("grounded", False)),
        )
    return TicketOut(
        id=str(t.id),
        title=t.title,
        body=t.body,
        category=t.category,
        product_area=t.product_area,
        confidence=t.confidence,
        status=t.status,
        answer=answer,
    )


class SqlTicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _parse_id(self, ticket_id: str) -> UUID | None:
        try:
            return UUID(ticket_id)
        except ValueError:
            return None

    async def create(self, title: str | None, body: str) -> TicketOut:
        ticket = Ticket(title=title, body=body, status="new")
        self._session.add(ticket)
        await self._session.flush()
        await self._session.commit()
        return _to_out(ticket)

    async def get(self, ticket_id: str) -> TicketOut | None:
        pk = self._parse_id(ticket_id)
        if pk is None:
            return None
        ticket = await self._session.get(Ticket, pk)
        return _to_out(ticket) if ticket is not None else None

    async def save_result(self, ticket_id: str, result: PipelineResult) -> TicketOut | None:
        pk = self._parse_id(ticket_id)
        if pk is None:
            return None
        ticket = await self._session.get(Ticket, pk)
        if ticket is None:
            return None
        ticket.category = result.classification.category
        ticket.product_area = result.classification.product_area
        ticket.confidence = result.classification.confidence
        ticket.status = result.escalation.status
        ticket.answer = {
            "text": result.generation.answer,
            "citations": result.generation.used_context,
            "grounded": result.generation.grounded,
        }
        await self._session.commit()
        return _to_out(ticket)

    async def set_status(self, ticket_id: str, status: str) -> TicketOut | None:
        pk = self._parse_id(ticket_id)
        if pk is None:
            return None
        ticket = await self._session.get(Ticket, pk)
        if ticket is None:
            return None
        ticket.status = status
        await self._session.commit()
        return _to_out(ticket)
