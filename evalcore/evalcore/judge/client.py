"""Provider-agnostic judge client over httpx (TechDesign §2.4).

Calls Anthropic (/v1/messages) or OpenAI (/v1/chat/completions) directly — no vendor SDKs —
so tests can drive it through httpx.MockTransport. Verdicts are cached by content hash;
transport errors get 429/5xx-aware backoff; a non-JSON reply gets exactly one repair retry.

Concurrency semaphore / token-bucket rate limiting (§2.4) are added when the judge is wired
into the runner (run.concurrency lives there).
"""

import os
import random
from typing import Any

import anyio
import httpx

from evalcore.judge.base import (
    JudgeError,
    JudgeRequest,
    JudgeResult,
    JudgeVerdict,
)
from evalcore.judge.cache import JudgeCache, cache_key, context_digest

_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAX_OUTPUT_TOKENS = 512
_ENV_KEY = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
_REPAIR = (
    '\n\nReturn ONLY a JSON object {"score": <number 0..1>, "reason": <string>}. '
    "No prose, no code fences."
)


def _parse_verdict(text: str) -> JudgeVerdict | None:
    """Extract the JSON object from a model reply and validate it; None if unparseable."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return JudgeVerdict.model_validate_json(text[start : end + 1])
    except ValueError:
        return None


class JudgeClient:
    """A judge pinned to ``{provider, model, prompt_version}`` with a content-hash cache."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        prompt_version: str,
        cache: JudgeCache,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = 4,
        backoff_base: float = 0.5,
        backoff_cap: float = 30.0,
        timeout: float = 30.0,
    ) -> None:
        if provider not in _ENV_KEY:
            raise ValueError(
                f"Unknown judge provider {provider!r}; expected one of {sorted(_ENV_KEY)}"
            )
        self._provider = provider
        self._model = model
        self._prompt_version = prompt_version
        self._cache = cache
        self._api_key = api_key or os.environ.get(_ENV_KEY[provider], "")
        self._http = http_client
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._timeout = timeout

    @property
    def version(self) -> str:
        return f"{self._provider}/{self._model}@{self._prompt_version}"

    async def evaluate(self, request: JudgeRequest) -> JudgeResult:
        key = cache_key(
            model=self._model,
            prompt_version=self._prompt_version,
            item_id=request.item_id,
            answer=request.answer,
            ctx_digest=context_digest(request.context),
        )
        hit = self._cache.get(key)
        if hit is not None:
            return hit

        if not self._api_key:
            raise JudgeError(f"missing API key: set {_ENV_KEY[self._provider]}")

        verdict = _parse_verdict(await self._call(request.prompt))
        if verdict is None:  # one repair retry
            verdict = _parse_verdict(await self._call(request.prompt + _REPAIR))
        if verdict is None:
            raise JudgeError("judge did not return valid JSON after one repair attempt")

        result = JudgeResult(score=verdict.score, reason=verdict.reason)
        self._cache.set(key, result)
        return result

    def _build_request(self, prompt: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        message = {"role": "user", "content": prompt}
        if self._provider == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01"}
            payload: dict[str, Any] = {
                "model": self._model,
                "max_tokens": _MAX_OUTPUT_TOKENS,
                "temperature": 0,
                "messages": [message],
            }
        else:  # openai
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"authorization": f"Bearer {self._api_key}"}
            payload = {"model": self._model, "temperature": 0, "messages": [message]}
        return url, headers, payload

    def _extract(self, data: Any) -> str:
        # ``Any``: provider JSON is external/untyped; we validate the shape defensively.
        try:
            if self._provider == "anthropic":
                value = data["content"][0]["text"]
            else:
                value = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise JudgeError(f"unexpected judge response shape: {e}") from e
        if not isinstance(value, str):
            raise JudgeError("judge response text is not a string")
        return value

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return min(float(retry_after), self._backoff_cap)
            except ValueError:
                pass
        base = min(self._backoff_base * (1 << attempt), self._backoff_cap)
        return base + random.uniform(0, self._backoff_base)

    async def _post(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> httpx.Response:
        if self._http is not None:
            return await self._http.post(url, headers=headers, json=payload, timeout=self._timeout)
        async with httpx.AsyncClient() as client:
            return await client.post(url, headers=headers, json=payload, timeout=self._timeout)

    async def _call(self, prompt: str) -> str:
        url, headers, payload = self._build_request(prompt)
        last_error: str = "unknown error"
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._post(url, headers, payload)
            except httpx.TransportError as e:
                last_error = f"transport error: {e}"
                if attempt >= self._max_retries:
                    break
                await anyio.sleep(self._delay(attempt, None))
                continue

            if resp.status_code in _RETRY_STATUS:
                last_error = f"HTTP {resp.status_code}"
                if attempt >= self._max_retries:
                    break
                await anyio.sleep(self._delay(attempt, resp.headers.get("retry-after")))
                continue
            if resp.status_code >= 400:
                raise JudgeError(f"judge HTTP {resp.status_code}: {resp.text[:200]}")
            return self._extract(resp.json())

        raise JudgeError(
            f"judge transport failed after {self._max_retries + 1} attempts ({last_error})"
        )
