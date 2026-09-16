"""Pipeline data types (TechDesign §3.2). Pydantic so LLM structured output validates directly."""

from typing import Literal

from pydantic import BaseModel, Field


class TicketClass(BaseModel):
    """Classifier output (FR-T4)."""

    category: str
    product_area: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class RetrievedChunk(BaseModel):
    """A chunk surfaced by retrieval, with its fused RRF score."""

    id: str
    content: str
    score: float
    heading_path: str | None = None


class Retrieval(BaseModel):
    """Retrieve stage output: the top-k chunks plus the best fused score (for escalation)."""

    chunks: list[RetrievedChunk]
    max_rrf_score: float

    @property
    def retrieved_ids(self) -> list[str]:
        return [c.id for c in self.chunks]


class Generation(BaseModel):
    """Generator output (FR-T6). ``grounded=False`` means abstain -> escalate."""

    answer: str
    used_context: list[int] = []
    grounded: bool


class Escalation(BaseModel):
    """Escalate stage output (FR-T7)."""

    status: Literal["answered", "escalated"]
    reasons: list[str] = []


class PipelineResult(BaseModel):
    """Everything the four stages produced for one ticket, plus wall-clock latency."""

    classification: TicketClass
    retrieval: Retrieval
    generation: Generation
    escalation: Escalation
    latency_ms: int
