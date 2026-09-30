"""Tests for JudgeClient using httpx.MockTransport — NO real LLM calls (testing.md golden rule).

Covers: happy path, cache hit (no 2nd call), repair retry, unrecoverable parse, 429 retry,
5xx exhaustion, provider payload/headers, out-of-range score rejection, version string.
"""

import httpx
import pytest

from evalcore.judge.base import JudgeError, JudgeRequest
from evalcore.judge.cache import JudgeCache
from evalcore.judge.client import JudgeClient


def _anthropic_body(text: str) -> dict[str, object]:
    return {"content": [{"type": "text", "text": text}]}


def _openai_body(text: str) -> dict[str, object]:
    return {"choices": [{"message": {"content": text}}]}


def _client(
    handler: httpx.MockTransport, cache: JudgeCache, *, provider: str = "anthropic", **kw: object
) -> JudgeClient:
    http = httpx.AsyncClient(transport=handler)
    return JudgeClient(
        provider=provider,
        model="m",
        prompt_version="v1",
        cache=cache,
        api_key="test-key",
        http_client=http,
        backoff_base=0.0,
        **kw,  # type: ignore[arg-type]
    )


def _req() -> JudgeRequest:
    return JudgeRequest(item_id="i1", prompt="judge this", answer="a", context="c")


async def test_happy_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_anthropic_body('{"score": 0.9, "reason": "ok"}'))

    client = _client(httpx.MockTransport(handler), JudgeCache(tmp_path))
    result = await client.evaluate(_req())
    assert result.score == 0.9
    assert result.reason == "ok"
    assert calls["n"] == 1


async def test_cache_hit_skips_second_call(tmp_path) -> None:  # type: ignore[no-untyped-def]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_anthropic_body('{"score": 0.5, "reason": "x"}'))

    cache = JudgeCache(tmp_path)
    client = _client(httpx.MockTransport(handler), cache)
    await client.evaluate(_req())
    await client.evaluate(_req())  # identical -> cache hit
    assert calls["n"] == 1


async def test_repair_retry_recovers(tmp_path) -> None:  # type: ignore[no-untyped-def]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json=_anthropic_body("no json here"))
        return httpx.Response(200, json=_anthropic_body('{"score": 0.7, "reason": "fixed"}'))

    client = _client(httpx.MockTransport(handler), JudgeCache(tmp_path))
    result = await client.evaluate(_req())
    assert result.score == 0.7
    assert calls["n"] == 2  # original + one repair


async def test_unrecoverable_parse_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_anthropic_body("still not json"))

    client = _client(httpx.MockTransport(handler), JudgeCache(tmp_path))
    with pytest.raises(JudgeError):
        await client.evaluate(_req())
    assert calls["n"] == 2  # original + one repair, then give up


async def test_429_is_retried(tmp_path) -> None:  # type: ignore[no-untyped-def]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=_anthropic_body('{"score": 1.0, "reason": "ok"}'))

    client = _client(httpx.MockTransport(handler), JudgeCache(tmp_path))
    result = await client.evaluate(_req())
    assert result.score == 1.0
    assert calls["n"] == 2


async def test_5xx_exhausts_and_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    client = _client(httpx.MockTransport(handler), JudgeCache(tmp_path), max_retries=2)
    with pytest.raises(JudgeError):
        await client.evaluate(_req())
    assert calls["n"] == 3  # attempts = max_retries + 1


async def test_anthropic_request_shape(tmp_path) -> None:  # type: ignore[no-untyped-def]
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["x-api-key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json=_anthropic_body('{"score": 0.5, "reason": "x"}'))

    client = _client(httpx.MockTransport(handler), JudgeCache(tmp_path), provider="anthropic")
    await client.evaluate(_req())
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["x-api-key"] == "test-key"


async def test_openai_request_shape(tmp_path) -> None:  # type: ignore[no-untyped-def]
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=_openai_body('{"score": 0.5, "reason": "x"}'))

    client = _client(httpx.MockTransport(handler), JudgeCache(tmp_path), provider="openai")
    await client.evaluate(_req())
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen["auth"] == "Bearer test-key"


async def test_out_of_range_score_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_anthropic_body('{"score": 1.5, "reason": "too high"}'))

    client = _client(httpx.MockTransport(handler), JudgeCache(tmp_path))
    with pytest.raises(JudgeError):
        await client.evaluate(_req())


def test_version_string(tmp_path) -> None:  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_anthropic_body('{"score": 0.5, "reason": "x"}'))

    client = _client(httpx.MockTransport(handler), JudgeCache(tmp_path))
    assert client.version == "anthropic/m@v1"


def test_unknown_provider_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError):
        JudgeClient(provider="grok", model="m", prompt_version="v1", cache=JudgeCache(tmp_path))


async def test_gemini_request_shape(tmp_path) -> None:  # type: ignore[no-untyped-def]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": '{"score": 0.8, "reason": "ok"}'}]}}]
            },
        )

    client = _client(httpx.MockTransport(handler), JudgeCache(tmp_path), provider="gemini")
    await client.evaluate(JudgeRequest(item_id="x", prompt="grade", answer="a", context="c"))
    assert requests[0].headers["x-goog-api-key"] == "test-key"
    assert requests[0].url.path.endswith("/m:generateContent")
