"""Escalate stage (FR-T7): pure decision — low confidence OR ungrounded OR weak retrieval (§3.2)."""

from app.pipeline.models import Escalation, Generation, Retrieval, TicketClass


def escalate(
    classification: TicketClass,
    generation: Generation,
    retrieval: Retrieval,
    *,
    conf_threshold: float,
    rrf_threshold: float,
) -> Escalation:
    reasons: list[str] = []
    if classification.confidence < conf_threshold:
        reasons.append("low_confidence")
    if not generation.grounded:
        reasons.append("ungrounded")
    if retrieval.max_rrf_score < rrf_threshold:
        reasons.append("weak_retrieval")
    return Escalation(status="escalated" if reasons else "answered", reasons=reasons)
