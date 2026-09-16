"""Skeleton tests: app factory, /health, settings, models import — all offline."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Base, Chunk, Document, Ticket
from app.settings import Settings


def test_health_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_settings_defaults() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.top_k == 5
    assert s.conf_threshold == 0.6
    assert s.active_strategy == "fixed_512_50"
    assert s.database_url.startswith("postgresql+asyncpg://")


def test_settings_env_override(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TOP_K", "8")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.top_k == 8
    assert s.llm_model == "gpt-4o"


def test_models_have_expected_tables() -> None:
    tables = set(Base.metadata.tables)
    assert {"documents", "chunks", "tickets"} <= tables
    assert Document.__tablename__ == "documents"
    assert Chunk.__tablename__ == "chunks"
    assert Ticket.__tablename__ == "tickets"
