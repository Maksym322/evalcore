"""Fixture callables for adapter/runner tests. Underscore prefix => pytest won't collect it.

Referenced by dotted path (e.g. ``tests._fake_target:sync_dict``) so the real import
resolution path is exercised end-to-end.
"""

from typing import Any

from evalcore.schema import TargetOutput

not_callable = 3


def sync_dict(input: dict[str, Any]) -> dict[str, Any]:
    # Echo an input field to prove the target sees `input` (and only input).
    return {"answer": f"echo:{input.get('question', '')}", "retrieved_ids": ["doc-1"]}


def sync_output(input: dict[str, Any]) -> TargetOutput:
    return TargetOutput(answer="typed", retrieved_ids=["doc-2"])


async def async_dict(input: dict[str, Any]) -> dict[str, Any]:
    return {"answer": "async-answer"}


def returns_int(input: dict[str, Any]) -> int:
    return 42


def retrieval(input: dict[str, Any]) -> dict[str, Any]:
    # Category + retrieved ids come from item input. Missing "docs" -> None (a NaN failure).
    return {"answer": input.get("cat", ""), "retrieved_ids": input.get("docs")}


def grounded(input: dict[str, Any]) -> dict[str, Any]:
    answer = str(input.get("answer", ""))
    return {"answer": answer, "retrieved_context": [answer]}
