"""Gemini embedding REST client; index and query use the same 1536 dimensional space."""

import math

import httpx

from app.ingestion.embedder import EmbedderError
from app.models import EMBED_DIM

_API = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiEmbedder:
    def __init__(
        self, api_key: str, model: str, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._transport = transport

    async def embed(self, text: str) -> list[float]:
        return await self._embed(text, "RETRIEVAL_QUERY")

    async def embed_document(self, text: str) -> list[float]:
        return await self._embed(text, "RETRIEVAL_DOCUMENT")

    async def _embed(self, text: str, task_type: str) -> list[float]:
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
                response = await client.post(
                    f"{_API}/{self._model}:embedContent",
                    headers={"x-goog-api-key": self._api_key},
                    json={
                        "content": {"parts": [{"text": text}]},
                        "embedContentConfig": {
                            "taskType": task_type,
                            "outputDimensionality": EMBED_DIM,
                        },
                    },
                )
                response.raise_for_status()
                values = response.json()["embedding"]["values"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise EmbedderError("Gemini embedding request failed") from exc
        if not isinstance(values, list) or len(values) != EMBED_DIM:
            raise EmbedderError(f"Gemini embedding must have {EMBED_DIM} dimensions")
        try:
            vector = [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise EmbedderError("Gemini embedding contained a nonnumeric value") from exc
        if not all(math.isfinite(value) for value in vector):
            raise EmbedderError("Gemini embedding contained a nonfinite value")
        return vector
