"""HttpAdapter + N8nWebhookAdapter (TechDesign §2.2).

POSTs ``{"input": item.input, "id": item.id}`` to a configured URL, maps the JSON response
to a TargetOutput via JSONPath, and records wall-clock latency. Auth is an env var NAME
(the secret is never in config). Retries on 429/5xx with exponential backoff.
"""

import os
import random
import re
import time
from typing import Any

import anyio
import httpx
from jsonpath_ng.parser import parse as jsonpath_parse

from evalcore.adapters.base import AdapterError, Target
from evalcore.config import ConfigError, HttpAdapterConfig, N8nWebhookAdapterConfig
from evalcore.schema import DatasetItem, TargetOutput

_RETRY_STATUS = {429, 500, 502, 503, 504}
_MAP_FIELDS = {"answer", "retrieved_context", "retrieved_ids"}
_LIST_FIELDS = {"retrieved_context", "retrieved_ids"}
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_N8N_DEFAULT_MAP = {
    "answer": "$.answer",
    "retrieved_context": "$.retrieved_context[*]",
    "retrieved_ids": "$.retrieved_ids[*]",
}


def _expand_env(url: str) -> str:
    """Replace ``${VAR}`` in a URL from the environment; missing var -> ConfigError."""

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        value = os.environ.get(name)
        if value is None:
            raise ConfigError(f"env var {name!r} referenced in adapter.url is not set")
        return value

    return _ENV_PATTERN.sub(repl, url)


class HttpAdapter(Target):
    """POST target with JSONPath response mapping."""

    def __init__(
        self,
        config: HttpAdapterConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = _expand_env(config.url)
        self._map = config.map
        unknown = set(self._map) - _MAP_FIELDS
        if unknown:
            raise ConfigError(f"http adapter map has unknown fields: {sorted(unknown)}")
        if "answer" not in self._map:
            raise ConfigError("http adapter 'map' must include an 'answer' entry")
        self._compiled = {field: jsonpath_parse(expr) for field, expr in self._map.items()}
        self._auth_header_env = config.auth_header_env
        self._auth_header = config.auth_header
        self._auth_scheme = config.auth_scheme
        self._timeout = config.timeout
        self._max_retries = config.max_retries
        self._http = http_client

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json", "X-Eval-Run": "1"}
        if self._auth_header_env:
            token = os.environ.get(self._auth_header_env)
            if not token:
                raise AdapterError(f"auth env var {self._auth_header_env!r} is not set")
            headers[self._auth_header] = f"{self._auth_scheme} {token}".strip()
        return headers

    def _payload(self, data: Any) -> Any:
        """Hook for subclasses to reshape the raw response before mapping (n8n unwraps here)."""
        return data

    def _to_output(self, data: Any) -> TargetOutput:
        root = self._payload(data)
        fields: dict[str, Any] = {}
        for field, expr in self._compiled.items():
            matches = expr.find(root)
            if field in _LIST_FIELDS:
                fields[field] = [str(m.value) for m in matches]
            else:  # answer: first match or empty string
                fields["answer"] = str(matches[0].value) if matches else ""
        return TargetOutput(**fields)

    def _delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return min(float(retry_after), 30.0)
            except ValueError:
                pass
        return min(0.5 * (1 << attempt), 30.0) + random.uniform(0, 0.5)

    async def _post(self, item: DatasetItem) -> httpx.Response:
        body = {"input": item.input, "id": item.id}
        headers = self._headers()
        if self._http is not None:
            return await self._http.post(
                self._url, json=body, headers=headers, timeout=self._timeout
            )
        async with httpx.AsyncClient() as client:
            return await client.post(self._url, json=body, headers=headers, timeout=self._timeout)

    async def respond(self, item: DatasetItem) -> TargetOutput:
        t0 = time.perf_counter()
        last_error = "unknown error"
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._post(item)
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
                raise AdapterError(f"target HTTP {resp.status_code}: {resp.text[:200]}")

            out = self._to_output(resp.json())
            out.metadata["latency_ms"] = int((time.perf_counter() - t0) * 1000)
            return out

        raise AdapterError(f"target failed after {self._max_retries + 1} attempts ({last_error})")


class N8nWebhookAdapter(HttpAdapter):
    """HttpAdapter preset for n8n: unwraps the array-wrapped response, default map."""

    def __init__(
        self,
        config: N8nWebhookAdapterConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not config.map:
            config = config.model_copy(update={"map": dict(_N8N_DEFAULT_MAP)})
        super().__init__(config, http_client=http_client)

    def _payload(self, data: Any) -> Any:
        # n8n webhooks return a single-element array wrapping the actual body.
        if isinstance(data, list) and data:
            return data[0]
        return data
