"""Shared judge types and the Judge protocol (TechDesign §2.4).

Kept separate from client/cache so those modules don't import-cycle. A Judge maps a
JudgeRequest to a JudgeResult; both the real JudgeClient and the test FakeJudge implement it.
"""

from typing import Protocol

from pydantic import BaseModel, Field


class JudgeRequest(BaseModel):
    """Everything a judge needs for one verdict (and to build a cache key)."""

    item_id: str
    prompt: str  # the fully rendered judge prompt actually sent to the model
    answer: str  # the system answer under evaluation (part of the cache key)
    context: str = ""  # judged-metric context (digested into the cache key)


class JudgeResult(BaseModel):
    """A judge verdict: normalized score plus a short rationale."""

    score: float
    reason: str


class JudgeVerdict(BaseModel):
    """Strict-JSON contract the judge model must return: ``{"score": 0..1, "reason": str}``."""

    score: float = Field(ge=0.0, le=1.0)
    reason: str


class JudgeError(Exception):
    """Raised when a judge call fails irrecoverably (transport exhausted, or non-JSON after repair).

    The judged metric converts this into a NaN MetricResult with ``details.judge_error``.
    """


class Judge(Protocol):
    """The interface judged metrics depend on."""

    @property
    def version(self) -> str:
        """Pinned identity recorded in RunReport.judge_versions, e.g. 'anthropic/claude@v1'."""
        ...

    async def evaluate(self, request: JudgeRequest) -> JudgeResult: ...
