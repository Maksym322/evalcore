"""LLM interface for structured (JSON) generation (TechDesign §3.2).

Stages depend on this protocol, not a concrete client. The real httpx-based client (with the
one repair retry and provider selection) is a separate sub-task; tests inject a FakeLLM.
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMError(Exception):
    """Raised when the model call fails or returns unparseable JSON after its repair retry."""


class LLM(Protocol):
    """Calls a chat model and validates the reply into ``schema``. Repair retry lives inside."""

    async def structured(self, system: str, user: str, *, schema: type[ModelT]) -> ModelT: ...
