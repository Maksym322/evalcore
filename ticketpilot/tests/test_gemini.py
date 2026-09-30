"""Gemini provider contract tests; requests stay offline."""

import httpx
import pytest

from app.gemini import GeminiLLM
from app.llm import LLMError
from app.pipeline.models import TicketClass


async def test_structured_output_and_request_shape() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": '{"category":"billing","confidence":0.9}'}]}}
                ]
            },
        )

    llm = GeminiLLM("fake-key", "gemini-3.5-flash-lite", transport=httpx.MockTransport(respond))
    result = await llm.structured("Classify", "double charge", schema=TicketClass)
    assert result.category == "billing"
    assert len(requests) == 1
    assert requests[0].headers["x-goog-api-key"] == "fake-key"
    assert requests[0].url.path.endswith("/gemini-3.5-flash-lite:generateContent")
    assert requests[0].content.find(b'"responseFormat"') > 0


async def test_invalid_json_gets_one_repair_retry() -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        answer = "oops" if calls == 1 else '{"category":"other","confidence":0.4}'
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": answer}]}}]}
        )

    llm = GeminiLLM("fake-key", "model", transport=httpx.MockTransport(respond))
    result = await llm.structured("Classify", "body", schema=TicketClass)
    assert result.category == "other"
    assert calls == 2


async def test_provider_error_is_typed() -> None:
    llm = GeminiLLM(
        "fake-key", "model", transport=httpx.MockTransport(lambda _: httpx.Response(429))
    )
    with pytest.raises(LLMError, match="request failed"):
        await llm.structured("Classify", "body", schema=TicketClass)
