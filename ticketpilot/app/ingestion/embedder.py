"""Embedder interface (TechDesign §3.2)."""

from typing import Protocol


class EmbedderError(Exception):
    """Raised when embedding fails."""


class Embedder(Protocol):
    """Maps text to a fixed-length dense vector (dim must match the DB column, 1536)."""

    async def embed(self, text: str) -> list[float]: ...
