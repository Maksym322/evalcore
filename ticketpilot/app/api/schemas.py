"""API request/response models (FR-T8). ``EvalOut`` matches EvalCore's HttpAdapter map."""

from typing import Any

from pydantic import BaseModel, Field

from app.pipeline.models import PipelineResult


class TicketCreate(BaseModel):
    title: str | None = None
    body: str = Field(min_length=1, max_length=10_000)


class AnswerOut(BaseModel):
    text: str
    citations: list[int] = []
    grounded: bool


class TicketOut(BaseModel):
    """Persisted ticket view. Also the repository's return type (SQL stays in the repo)."""

    id: str
    title: str | None = None
    body: str
    category: str | None = None
    product_area: str | None = None
    confidence: float | None = None
    status: str
    answer: AnswerOut | None = None
    escalation_reasons: list[str] = []


class EvalRequest(BaseModel):
    """Body EvalCore's HttpAdapter POSTs: ``{"id": ..., "input": {...}}``."""

    id: str
    input: dict[str, Any]

    def ticket_body(self) -> str:
        return str(self.input.get("body") or self.input.get("question") or "")


class EvalOut(BaseModel):
    """Shaped for EvalCore's HttpAdapter map (answer/context/ids/metadata)."""

    answer: str
    retrieved_context: list[str]
    retrieved_ids: list[str]
    metadata: dict[str, Any]

    @classmethod
    def from_result(cls, result: PipelineResult) -> "EvalOut":
        return cls(
            answer=result.generation.answer,
            retrieved_context=[c.content for c in result.retrieval.chunks],
            retrieved_ids=result.retrieval.retrieved_ids,
            metadata={
                "latency_ms": result.latency_ms,
                "category": result.classification.category,
                "confidence": result.classification.confidence,
                "grounded": result.generation.grounded,
                "status": result.escalation.status,
                "reasons": result.escalation.reasons,
            },
        )
