"""API route tests via httpx AsyncClient + ASGITransport — all offline (deps overridden)."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_embedder, get_llm, get_repository, get_store
from app.api.schemas import AnswerOut, TicketOut
from app.main import create_app
from app.pipeline.models import Generation, PipelineResult, TicketClass
from app.settings import Settings, get_settings
from tests._fakes import FakeChunk, FakeEmbedder, FakeLLM, FakeStore


class FakeRepo:
    def __init__(self) -> None:
        self._store: dict[str, TicketOut] = {}

    async def create(self, title: str | None, body: str) -> TicketOut:
        tid = str(uuid4())
        t = TicketOut(id=tid, title=title, body=body, status="new")
        self._store[tid] = t
        return t

    async def get(self, ticket_id: str) -> TicketOut | None:
        return self._store.get(ticket_id)

    async def save_result(self, ticket_id: str, result: PipelineResult) -> TicketOut | None:
        t = self._store.get(ticket_id)
        if t is None:
            return None
        updated = t.model_copy(
            update={
                "category": result.classification.category,
                "confidence": result.classification.confidence,
                "status": result.escalation.status,
                "answer": AnswerOut(
                    text=result.generation.answer,
                    citations=result.generation.used_context,
                    grounded=result.generation.grounded,
                ),
                "escalation_reasons": result.escalation.reasons,
            }
        )
        self._store[ticket_id] = updated
        return updated

    async def set_status(self, ticket_id: str, status: str) -> TicketOut | None:
        t = self._store.get(ticket_id)
        if t is None:
            return None
        updated = t.model_copy(update={"status": status})
        self._store[ticket_id] = updated
        return updated


def _fake_llm() -> FakeLLM:
    return FakeLLM(
        by_schema={
            TicketClass: TicketClass(category="billing", product_area="invoices", confidence=0.9),
            Generation: Generation(answer="Pay via Settings [1].", used_context=[1], grounded=True),
        }
    )


def _fake_store() -> FakeStore:
    hits = [FakeChunk("d1", "Pay via Settings.", "Billing")]
    return FakeStore(hits, hits)


def _make_app(repo: "FakeRepo", *, eval_token: str | None = None):  # type: ignore[no-untyped-def]
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_llm] = _fake_llm
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    app.dependency_overrides[get_store] = _fake_store
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, eval_token=eval_token)  # type: ignore[call-arg]
    return app


def _client(app):  # type: ignore[no-untyped-def]
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def repo() -> FakeRepo:
    return FakeRepo()


async def test_create_ticket_runs_pipeline(repo: FakeRepo) -> None:
    async with _client(_make_app(repo)) as client:
        resp = await client.post("/tickets", json={"body": "How do I pay?"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["category"] == "billing"
    assert data["status"] == "answered"
    assert data["answer"]["grounded"] is True


async def test_get_ticket_roundtrip(repo: FakeRepo) -> None:
    async with _client(_make_app(repo)) as client:
        created = (await client.post("/tickets", json={"body": "q"})).json()
        got = await client.get(f"/tickets/{created['id']}")
        missing = await client.get("/tickets/does-not-exist")
    assert got.status_code == 200
    assert got.json()["id"] == created["id"]
    assert missing.status_code == 404


async def test_resolve_ticket(repo: FakeRepo) -> None:
    async with _client(_make_app(repo)) as client:
        created = (await client.post("/tickets", json={"body": "q"})).json()
        resolved = await client.post(f"/tickets/{created['id']}/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


async def test_eval_requires_bearer_token(repo: FakeRepo) -> None:
    async with _client(_make_app(repo, eval_token="secret")) as client:
        no_auth = await client.post("/tickets/eval", json={"id": "i1", "input": {"body": "q"}})
        bad = await client.post(
            "/tickets/eval",
            json={"id": "i1", "input": {"body": "q"}},
            headers={"Authorization": "Bearer wrong"},
        )
    assert no_auth.status_code == 401
    assert bad.status_code == 401


async def test_eval_returns_adapter_shape(repo: FakeRepo) -> None:
    async with _client(_make_app(repo, eval_token="secret")) as client:
        resp = await client.post(
            "/tickets/eval",
            json={"id": "i1", "input": {"body": "How do I pay?"}},
            headers={"Authorization": "Bearer secret"},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert set(data) == {"answer", "retrieved_context", "retrieved_ids", "metadata"}
    assert data["retrieved_ids"] == ["d1"]
    assert data["metadata"]["category"] == "billing"
    assert isinstance(data["metadata"]["latency_ms"], int)
