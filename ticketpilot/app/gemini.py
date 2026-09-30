"""Gemini REST implementation of the LLM protocol."""

import httpx
from pydantic import ValidationError

from app.llm import LLMError, ModelT

_API = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiLLM:
    def __init__(
        self, api_key: str, model: str, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._transport = transport

    async def structured(self, system: str, user: str, *, schema: type[ModelT]) -> ModelT:
        instructions = system
        for attempt in range(2):
            payload = {
                "systemInstruction": {"parts": [{"text": instructions}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"responseFormat": {"text": {"mimeType": "application/json"}}},
            }
            try:
                async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
                    response = await client.post(
                        f"{_API}/{self._model}:generateContent",
                        headers={"x-goog-api-key": self._api_key},
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise LLMError("Gemini request failed") from exc

            try:
                parts = data["candidates"][0]["content"]["parts"]
                content = "".join(part["text"] for part in parts if "text" in part)
                return schema.model_validate_json(content)
            except (KeyError, IndexError, TypeError, ValidationError, ValueError) as exc:
                if attempt == 1:
                    raise LLMError("Gemini returned invalid structured output") from exc
                instructions = (
                    f"{system}\nReturn only a JSON object matching this schema: "
                    f"{schema.model_json_schema()}. Your previous response was invalid."
                )
        raise AssertionError("unreachable")
