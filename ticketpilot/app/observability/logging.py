"""Structured logging + a stage timer (code_patterns §3). Full JSON config lands in M3.8.

Stages take a ``Logger`` (structural) and wrap their body in ``stage_timer`` so every stage
emits its own duration. structlog loggers satisfy the protocol; tests can pass ``get_logger()``.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

import structlog


class Logger(Protocol):
    """Minimal structured-logger surface the pipeline depends on."""

    def info(self, event: str, **kw: Any) -> Any: ...
    def warning(self, event: str, **kw: Any) -> Any: ...


def get_logger(**initial: Any) -> Logger:
    """Return a bound structlog logger (unconfigured default is fine for now)."""
    logger: Logger = structlog.get_logger(**initial)
    return logger


@contextmanager
def stage_timer(log: Logger, stage: str, **fields: Any) -> Iterator[None]:
    """Time a pipeline stage and emit ``stage_complete`` with its duration."""
    start = time.perf_counter()
    try:
        yield
    finally:
        log.info(
            "stage_complete",
            stage=stage,
            duration_ms=int((time.perf_counter() - start) * 1000),
            **fields,
        )
