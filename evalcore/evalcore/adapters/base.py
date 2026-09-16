"""The adapter contract: any system under evaluation is a ``Target`` (code_patterns §1).

EvalCore never knows what's behind a Target — only that it maps a DatasetItem to a
TargetOutput. New target types are new adapter files; nothing else changes.
"""

from typing import Protocol

from evalcore.schema import DatasetItem, TargetOutput


class AdapterError(Exception):
    """Raised when an adapter cannot produce a TargetOutput (e.g. transport exhausted)."""


class Target(Protocol):
    """A system that answers a dataset item. Latency is measured by the adapter, always."""

    async def respond(self, item: DatasetItem) -> TargetOutput: ...
