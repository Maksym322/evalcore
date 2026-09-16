"""Tests for HttpAdapter + N8nWebhookAdapter via httpx.MockTransport — NO real network."""

import httpx
import pytest

from evalcore.adapters.base import AdapterError
from evalcore.adapters.http_adapter import HttpAdapter, N8nWebhookAdapter
from evalcore.config import ConfigError, HttpAdapterConfig, N8nWebhookAdapterConfig
from evalcore.schema import DatasetItem, Reference

BODY = {
    "answer": "the reset link",
    "retrieved_context": ["ctx one", "ctx two"],
    "retrieved_ids": ["d1", "d2"],
}


def _item() -> DatasetItem:
    return DatasetItem(id="i1", input={"question": "how?"}, reference=Reference())


def _http_config(**kw: object) -> HttpAdapterConfig:
    base: dict[str, object] = {
        "type": "http",
        "url": "https://x.test/eval",
        "map": {
            "answer": "$.answer",
            "retrieved_context": "$.retrieved_context[*]",
            "retrieved_ids": "$.retrieved_ids[*]",
        },
    }
    base.update(kw)
    return HttpAdapterConfig(**base)  # type: ignore[arg-type]


def _adapter(handler: httpx.MockTransport, config: HttpAdapterConfig) -> HttpAdapter:
    return HttpAdapter(config, http_client=httpx.AsyncClient(transport=handler))


async def test_happy_path_maps_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=BODY)

    adapter = _adapter(httpx.MockTransport(handler), _http_config())
    out = await adapter.respond(_item())
    assert out.answer == "the reset link"
    assert out.retrieved_context == ["ctx one", "ctx two"]
    assert out.retrieved_ids == ["d1", "d2"]
    assert isinstance(out.metadata["latency_ms"], int)


async def test_request_body_and_default_headers() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        seen["x_eval_run"] = request.headers.get("X-Eval-Run")
        return httpx.Response(200, json=BODY)

    adapter = _adapter(httpx.MockTransport(handler), _http_config())
    await adapter.respond(_item())
    assert '"id": "i1"' in str(seen["body"]) or '"id":"i1"' in str(seen["body"])
    assert seen["x_eval_run"] == "1"


async def test_auth_header_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TP_TOKEN", "secret123")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=BODY)

    adapter = _adapter(httpx.MockTransport(handler), _http_config(auth_header_env="TP_TOKEN"))
    await adapter.respond(_item())
    assert seen["auth"] == "Bearer secret123"


async def test_missing_auth_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TP_TOKEN", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=BODY)

    adapter = _adapter(httpx.MockTransport(handler), _http_config(auth_header_env="TP_TOKEN"))
    with pytest.raises(AdapterError):
        await adapter.respond(_item())


async def test_429_is_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=BODY)

    adapter = _adapter(httpx.MockTransport(handler), _http_config(max_retries=3))
    out = await adapter.respond(_item())
    assert out.answer == "the reset link"
    assert calls["n"] == 2


async def test_5xx_exhausts_and_raises() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    adapter = _adapter(httpx.MockTransport(handler), _http_config(max_retries=2))
    with pytest.raises(AdapterError):
        await adapter.respond(_item())
    assert calls["n"] == 3


def test_env_expansion_in_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TP_HOST", "https://real.host")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=BODY)

    adapter = _adapter(httpx.MockTransport(handler), _http_config(url="${TP_HOST}/eval"))
    assert adapter._url == "https://real.host/eval"


def test_missing_env_in_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOPE_HOST", raising=False)
    with pytest.raises(ConfigError):
        HttpAdapter(_http_config(url="${NOPE_HOST}/eval"))


def test_map_without_answer_rejected() -> None:
    with pytest.raises(ConfigError):
        HttpAdapter(_http_config(map={"retrieved_ids": "$.ids[*]"}))


def test_unknown_map_field_rejected() -> None:
    with pytest.raises(ConfigError):
        HttpAdapter(_http_config(map={"answer": "$.answer", "bogus": "$.x"}))


async def test_n8n_unwraps_array_and_default_map() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # n8n wraps the payload in a single-element array
        return httpx.Response(200, json=[BODY])

    config = N8nWebhookAdapterConfig(type="n8n_webhook", url="https://x.test/webhook")
    adapter = N8nWebhookAdapter(
        config, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    out = await adapter.respond(_item())
    assert out.answer == "the reset link"  # default map + array unwrap
    assert out.retrieved_ids == ["d1", "d2"]
