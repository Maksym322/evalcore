"""Classify stage (FR-T4): LLM structured output, fallback to 'other' on failure (§3.2)."""

from app.llm import LLM, LLMError
from app.observability.logging import Logger, stage_timer
from app.pipeline.models import TicketClass
from app.prompts import load_prompt


async def classify(body: str, *, llm: LLM, log: Logger) -> TicketClass:
    with stage_timer(log, "classify"):
        try:
            result = await llm.structured(load_prompt("classify"), body, schema=TicketClass)
        except LLMError as e:
            log.warning("classify_failed", error=str(e))
            return TicketClass(category="other", product_area=None, confidence=0.0)
        return result
