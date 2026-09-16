"""PythonAdapter: evaluate an in-process callable named by a dotted path (TechDesign §2.2).

The callable receives ``item.input`` (only — never the reference) and returns a
``TargetOutput`` or a dict validated into one. Sync callables run in a worker thread via
anyio; the adapter always records wall-clock latency into ``metadata["latency_ms"]``.
"""

import importlib
import inspect
import time
from collections.abc import Callable
from typing import Any

import anyio

from evalcore.adapters.base import Target
from evalcore.config import ConfigError
from evalcore.schema import DatasetItem, TargetOutput


def load_callable(dotted: str) -> Callable[..., Any]:
    """Resolve a ``"module.path:attribute"`` string to a callable.

    Raises ConfigError (config-time, fail-fast) on any resolution problem.
    """
    module_path, sep, attr_path = dotted.partition(":")
    if not sep or not module_path or not attr_path:
        raise ConfigError(f"adapter.callable must be 'module.path:attribute', got {dotted!r}")

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        raise ConfigError(f"adapter.callable: cannot import module {module_path!r} ({e})") from e

    obj: Any = module
    try:
        for part in attr_path.split("."):
            obj = getattr(obj, part)
    except AttributeError as e:
        raise ConfigError(
            f"adapter.callable: {attr_path!r} not found in module {module_path!r}"
        ) from e

    if not callable(obj):
        raise ConfigError(f"adapter.callable: {dotted!r} resolved to a non-callable")

    fn: Callable[..., Any] = obj
    return fn


def _to_output(result: Any) -> TargetOutput:
    if isinstance(result, TargetOutput):
        return result
    if isinstance(result, dict):
        return TargetOutput.model_validate(result)
    raise TypeError(
        f"Python adapter callable must return TargetOutput or dict, got {type(result).__name__}"
    )


class PythonAdapter(Target):
    """Adapts a user callable to the Target protocol."""

    def __init__(self, callable_path: str) -> None:
        self._fn = load_callable(callable_path)
        self._is_async = inspect.iscoroutinefunction(self._fn)

    async def respond(self, item: DatasetItem) -> TargetOutput:
        t0 = time.perf_counter()
        if self._is_async:
            result = await self._fn(item.input)
        else:
            result = await anyio.to_thread.run_sync(self._fn, item.input)
        out = _to_output(result)
        out.metadata["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return out
