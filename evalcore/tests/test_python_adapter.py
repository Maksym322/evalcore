"""Tests for PythonAdapter + load_callable (TechDesign §2.2, code_patterns §1)."""

import pytest

from evalcore.adapters.python_adapter import PythonAdapter, load_callable
from evalcore.config import ConfigError
from evalcore.schema import DatasetItem, Reference, TargetOutput

FAKE = "tests._fake_target"


def _item(question: str = "hi") -> DatasetItem:
    # Reference is populated to confirm the adapter never passes it to the callable.
    return DatasetItem(
        id="item-1",
        input={"question": question},
        reference=Reference(answer="SECRET-GROUND-TRUTH"),
    )


async def test_sync_dict_callable_maps_to_output() -> None:
    adapter = PythonAdapter(f"{FAKE}:sync_dict")
    out = await adapter.respond(_item("ping"))
    assert isinstance(out, TargetOutput)
    assert out.answer == "echo:ping"  # target saw input.question
    assert out.retrieved_ids == ["doc-1"]


async def test_callable_returning_target_output_passthrough() -> None:
    adapter = PythonAdapter(f"{FAKE}:sync_output")
    out = await adapter.respond(_item())
    assert out.answer == "typed"
    assert out.retrieved_ids == ["doc-2"]


async def test_async_callable_awaited() -> None:
    adapter = PythonAdapter(f"{FAKE}:async_dict")
    out = await adapter.respond(_item())
    assert out.answer == "async-answer"


async def test_latency_recorded_as_int_ms() -> None:
    adapter = PythonAdapter(f"{FAKE}:sync_dict")
    out = await adapter.respond(_item())
    assert isinstance(out.metadata["latency_ms"], int)
    assert out.metadata["latency_ms"] >= 0


async def test_wrong_return_type_raises_type_error() -> None:
    adapter = PythonAdapter(f"{FAKE}:returns_int")
    with pytest.raises(TypeError):
        await adapter.respond(_item())


def test_load_callable_missing_colon() -> None:
    with pytest.raises(ConfigError) as exc:
        load_callable("tests._fake_target.sync_dict")
    assert "module.path:attribute" in str(exc.value)


def test_load_callable_missing_module() -> None:
    with pytest.raises(ConfigError) as exc:
        load_callable("no.such.module:fn")
    assert "cannot import module" in str(exc.value)


def test_load_callable_missing_attribute() -> None:
    with pytest.raises(ConfigError) as exc:
        load_callable(f"{FAKE}:nope")
    assert "not found" in str(exc.value)


def test_load_callable_not_callable() -> None:
    with pytest.raises(ConfigError) as exc:
        load_callable(f"{FAKE}:not_callable")
    assert "non-callable" in str(exc.value)
