"""Generate stage (FR-T6): grounded answer with [n] citations; abstain -> grounded=False (§3.2)."""

from app.llm import LLM, LLMError
from app.observability.logging import Logger, stage_timer
from app.pipeline.models import Generation, RetrievedChunk
from app.prompts import load_prompt


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Number the retrieved chunks as [1], [2], ... so the model can cite them."""
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        header = f"[{i}]"
        if chunk.heading_path:
            header += f" ({chunk.heading_path})"
        blocks.append(f"{header} {chunk.content}")
    return "\n\n".join(blocks)


async def generate(
    question: str, chunks: list[RetrievedChunk], *, llm: LLM, log: Logger
) -> Generation:
    with stage_timer(log, "generate"):
        if not chunks:
            return Generation(answer="", used_context=[], grounded=False)
        user = f"CONTEXT:\n{format_context(chunks)}\n\nQUESTION:\n{question}"
        try:
            return await llm.structured(load_prompt("generate"), user, schema=Generation)
        except LLMError as e:
            log.warning("generate_failed", error=str(e))
            return Generation(answer="", used_context=[], grounded=False)
