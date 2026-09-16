"""Pipeline orchestrator: run the four stages in order (TechDesign §3.2).

Routes call this; it wires classify -> retrieve -> generate -> escalate and times the whole
thing. No SQL, no HTTP — just stage composition against injected dependencies.
"""

import time

from app.ingestion.embedder import Embedder
from app.llm import LLM
from app.observability.logging import Logger
from app.pipeline.classify import classify
from app.pipeline.escalate import escalate
from app.pipeline.generate import generate
from app.pipeline.models import PipelineResult
from app.pipeline.retrieve import RetrievalStore, retrieve
from app.settings import Settings


async def answer_ticket(
    body: str,
    *,
    llm: LLM,
    embedder: Embedder,
    store: RetrievalStore,
    settings: Settings,
    log: Logger,
) -> PipelineResult:
    start = time.perf_counter()
    classification = await classify(body, llm=llm, log=log)
    retrieval = await retrieve(body, embedder=embedder, store=store, settings=settings, log=log)
    generation = await generate(body, retrieval.chunks, llm=llm, log=log)
    escalation = escalate(
        classification,
        generation,
        retrieval,
        conf_threshold=settings.conf_threshold,
        rrf_threshold=settings.rrf_threshold,
    )
    return PipelineResult(
        classification=classification,
        retrieval=retrieval,
        generation=generation,
        escalation=escalation,
        latency_ms=int((time.perf_counter() - start) * 1000),
    )
