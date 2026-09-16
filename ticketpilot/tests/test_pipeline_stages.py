"""Stage tests with recorded fixtures — all offline (FakeLLM/FakeEmbedder/FakeStore)."""

from app.observability.logging import get_logger
from app.pipeline.classify import classify
from app.pipeline.escalate import escalate
from app.pipeline.generate import generate
from app.pipeline.models import Generation, Retrieval, RetrievedChunk, TicketClass
from app.pipeline.retrieve import retrieve
from app.settings import Settings
from tests._fakes import FakeChunk, FakeEmbedder, FakeLLM, FakeStore

LOG = get_logger()


# ---- classify --------------------------------------------------------------


async def test_classify_returns_llm_result() -> None:
    recorded = TicketClass(category="billing", product_area="invoices", confidence=0.9)
    result = await classify("I was double charged", llm=FakeLLM(recorded), log=LOG)
    assert result.category == "billing"
    assert result.confidence == 0.9


async def test_classify_falls_back_on_llm_error() -> None:
    result = await classify("???", llm=FakeLLM(fail=True), log=LOG)
    assert result.category == "other"
    assert result.confidence == 0.0


# ---- retrieve --------------------------------------------------------------


def _settings() -> Settings:
    return Settings(_env_file=None, top_k=3)  # type: ignore[call-arg]


async def test_retrieve_fuses_and_takes_top_k() -> None:
    vec = [FakeChunk("a", "alpha"), FakeChunk("b", "beta"), FakeChunk("c", "gamma")]
    ft = [FakeChunk("b", "beta"), FakeChunk("d", "delta")]  # b overlaps -> should rank first
    result = await retrieve(
        "q", embedder=FakeEmbedder(), store=FakeStore(vec, ft), settings=_settings(), log=LOG
    )
    assert result.retrieved_ids[0] == "b"  # overlap wins
    assert len(result.chunks) == 3  # top_k
    assert result.max_rrf_score == result.chunks[0].score


async def test_retrieve_empty_store() -> None:
    result = await retrieve(
        "q", embedder=FakeEmbedder(), store=FakeStore([], []), settings=_settings(), log=LOG
    )
    assert result.chunks == []
    assert result.max_rrf_score == 0.0


# ---- generate --------------------------------------------------------------


async def test_generate_returns_grounded_answer() -> None:
    recorded = Generation(answer="Reset it in Settings [1].", used_context=[1], grounded=True)
    chunks = [RetrievedChunk(id="a", content="Reset via Settings.", score=0.02)]
    result = await generate("how to reset?", chunks, llm=FakeLLM(recorded), log=LOG)
    assert result.grounded is True
    assert result.used_context == [1]


async def test_generate_numbers_context_blocks() -> None:
    llm = FakeLLM(Generation(answer="x", used_context=[], grounded=True))
    chunks = [
        RetrievedChunk(id="a", content="first", score=0.02, heading_path="Guide > A"),
        RetrievedChunk(id="b", content="second", score=0.01),
    ]
    await generate("q", chunks, llm=llm, log=LOG)
    sent_user = llm.calls[0][1]
    assert "[1] (Guide > A) first" in sent_user
    assert "[2] second" in sent_user


async def test_generate_no_chunks_is_ungrounded() -> None:
    result = await generate("q", [], llm=FakeLLM(fail=True), log=LOG)
    assert result.grounded is False


async def test_generate_llm_error_is_ungrounded() -> None:
    chunks = [RetrievedChunk(id="a", content="ctx", score=0.02)]
    result = await generate("q", chunks, llm=FakeLLM(fail=True), log=LOG)
    assert result.grounded is False


# ---- escalate (pure) -------------------------------------------------------


def _cls(conf: float) -> TicketClass:
    return TicketClass(category="x", confidence=conf)


def _ret(score: float) -> Retrieval:
    return Retrieval(chunks=[RetrievedChunk(id="a", content="c", score=score)], max_rrf_score=score)


def _gen(grounded: bool) -> Generation:
    return Generation(answer="a", used_context=[1], grounded=grounded)


def test_escalate_all_clear_answers() -> None:
    out = escalate(_cls(0.9), _gen(True), _ret(0.05), conf_threshold=0.6, rrf_threshold=0.01)
    assert out.status == "answered"
    assert out.reasons == []


def test_escalate_low_confidence() -> None:
    out = escalate(_cls(0.3), _gen(True), _ret(0.05), conf_threshold=0.6, rrf_threshold=0.01)
    assert out.status == "escalated"
    assert "low_confidence" in out.reasons


def test_escalate_ungrounded() -> None:
    out = escalate(_cls(0.9), _gen(False), _ret(0.05), conf_threshold=0.6, rrf_threshold=0.01)
    assert "ungrounded" in out.reasons


def test_escalate_weak_retrieval() -> None:
    out = escalate(_cls(0.9), _gen(True), _ret(0.001), conf_threshold=0.6, rrf_threshold=0.01)
    assert "weak_retrieval" in out.reasons


def test_escalate_multiple_reasons() -> None:
    out = escalate(_cls(0.2), _gen(False), _ret(0.0), conf_threshold=0.6, rrf_threshold=0.01)
    assert set(out.reasons) == {"low_confidence", "ungrounded", "weak_retrieval"}
