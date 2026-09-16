"""Golden + edge-case tests for the deterministic metrics, registry, and precondition check."""

import math

import pytest

from evalcore.config import ConfigError
from evalcore.metrics.base import (
    build,
    check_preconditions,
    dataset_reference_fields,
    is_failure,
)
from evalcore.schema import DatasetItem, Reference, TargetOutput


def _item(
    *,
    relevant_ids: list[str] | None = None,
    labels: dict[str, object] | None = None,
    answer: str | None = None,
) -> DatasetItem:
    return DatasetItem(
        id="i1",
        input={},
        reference=Reference(
            answer=answer,
            relevant_ids=relevant_ids or [],
            labels=labels or {},
        ),
    )


def _out(
    *,
    answer: str = "",
    retrieved_ids: list[str] | None = None,
    latency_ms: int | None = None,
) -> TargetOutput:
    md = {"latency_ms": latency_ms} if latency_ms is not None else {}
    return TargetOutput(answer=answer, retrieved_ids=retrieved_ids, metadata=md)


# ---- retrieval_recall_at_k -------------------------------------------------


async def test_recall_basic() -> None:
    m = build("retrieval_recall_at_k", {"k": 3})
    r = await m.score(_item(relevant_ids=["a", "b"]), _out(retrieved_ids=["a", "x", "b", "c"]))
    assert r.score == 1.0  # both relevant in top-3


async def test_recall_partial() -> None:
    m = build("retrieval_recall_at_k", {"k": 2})
    r = await m.score(_item(relevant_ids=["a", "b"]), _out(retrieved_ids=["a", "x"]))
    assert r.score == 0.5


async def test_recall_k_greater_than_items() -> None:
    m = build("retrieval_recall_at_k", {"k": 10})
    r = await m.score(_item(relevant_ids=["a", "b"]), _out(retrieved_ids=["a", "b"]))
    assert r.score == 1.0


async def test_recall_empty_relevant_is_failure() -> None:
    m = build("retrieval_recall_at_k", {"k": 3})
    r = await m.score(_item(relevant_ids=[]), _out(retrieved_ids=["a"]))
    assert is_failure(r.score)
    assert "relevant_ids" in r.details["error"]


async def test_recall_missing_retrieved_is_failure() -> None:
    m = build("retrieval_recall_at_k", {"k": 3})
    r = await m.score(_item(relevant_ids=["a"]), _out(retrieved_ids=None))
    assert is_failure(r.score)


async def test_recall_duplicate_ids_do_not_inflate() -> None:
    m = build("retrieval_recall_at_k", {"k": 3})
    # duplicates of a non-relevant id shouldn't push 'b' out of / into top-k spuriously
    r = await m.score(_item(relevant_ids=["a", "b"]), _out(retrieved_ids=["a", "a", "a"]))
    assert r.score == 0.5


# ---- retrieval_precision_at_k ---------------------------------------------


async def test_precision_basic() -> None:
    m = build("retrieval_precision_at_k", {"k": 4})
    r = await m.score(_item(relevant_ids=["a", "b"]), _out(retrieved_ids=["a", "b", "x", "y"]))
    assert r.score == 0.5  # 2 hits / 4 considered


async def test_precision_denominator_is_min_k_unique() -> None:
    m = build("retrieval_precision_at_k", {"k": 5})
    # only 2 unique retrieved -> denominator 2, not 5
    r = await m.score(_item(relevant_ids=["a"]), _out(retrieved_ids=["a", "b", "b", "b"]))
    assert r.score == 0.5


async def test_precision_empty_retrieved_is_failure() -> None:
    m = build("retrieval_precision_at_k", {"k": 3})
    r = await m.score(_item(relevant_ids=["a"]), _out(retrieved_ids=[]))
    assert is_failure(r.score)


# ---- exact_label_match -----------------------------------------------------


async def test_label_match() -> None:
    m = build("exact_label_match", {"label": "category"})
    r = await m.score(_item(labels={"category": "billing"}), _out(answer=" billing "))
    assert r.score == 1.0


async def test_label_mismatch() -> None:
    m = build("exact_label_match", {"label": "category"})
    r = await m.score(_item(labels={"category": "billing"}), _out(answer="refund"))
    assert r.score == 0.0


async def test_label_missing_is_failure() -> None:
    m = build("exact_label_match", {"label": "category"})
    r = await m.score(_item(labels={}), _out(answer="billing"))
    assert is_failure(r.score)


# ---- json_schema_valid (never NaN) ----------------------------------------

SCHEMA = {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}


async def test_schema_valid() -> None:
    m = build("json_schema_valid", {"schema": SCHEMA})
    r = await m.score(_item(), _out(answer='{"name": "Max"}'))
    assert r.score == 1.0


async def test_schema_violation_is_zero_not_failure() -> None:
    m = build("json_schema_valid", {"schema": SCHEMA})
    r = await m.score(_item(), _out(answer='{"name": 5}'))
    assert r.score == 0.0
    assert not is_failure(r.score)


async def test_schema_non_json_is_zero() -> None:
    m = build("json_schema_valid", {"schema": SCHEMA})
    r = await m.score(_item(), _out(answer="not json at all"))
    assert r.score == 0.0


def test_schema_invalid_schema_rejected_at_build() -> None:
    with pytest.raises(ConfigError):
        build("json_schema_valid", {"schema": {"type": "not-a-real-type"}})


# ---- latency_budget --------------------------------------------------------


async def test_latency_within_budget() -> None:
    m = build("latency_budget", {"max_ms": 1000})
    r = await m.score(_item(), _out(latency_ms=800))
    assert r.score == 1.0


async def test_latency_over_budget() -> None:
    m = build("latency_budget", {"max_ms": 500})
    r = await m.score(_item(), _out(latency_ms=800))
    assert r.score == 0.0


async def test_latency_missing_is_failure() -> None:
    m = build("latency_budget", {"max_ms": 500})
    r = await m.score(_item(), _out(latency_ms=None))
    assert is_failure(r.score)


# ---- registry --------------------------------------------------------------


def test_build_unknown_metric() -> None:
    with pytest.raises(ConfigError) as exc:
        build("does_not_exist", {})
    assert "Unknown metric" in str(exc.value)


def test_build_bad_params() -> None:
    with pytest.raises(ConfigError):
        build("retrieval_recall_at_k", {"k": 0})
    with pytest.raises(ConfigError):
        build("retrieval_recall_at_k", {"k": "three"})


# ---- preconditions ---------------------------------------------------------


def test_dataset_reference_fields_all_items_semantics() -> None:
    items = [
        _item(relevant_ids=["a"], labels={"category": "x"}),
        _item(relevant_ids=["b"], labels={}),  # no category here
    ]
    fields = dataset_reference_fields(items)
    assert "reference.relevant_ids" in fields
    assert "reference.labels.category" not in fields  # not in ALL items


def test_check_preconditions_passes() -> None:
    metrics = [build("retrieval_recall_at_k", {"k": 3})]
    available = {"retrieved_ids", "reference.relevant_ids"}
    check_preconditions(metrics, available)  # no raise


def test_check_preconditions_lists_gaps() -> None:
    metrics = [build("exact_label_match", {"label": "category"})]
    available = {"answer"}  # missing reference.labels.category
    with pytest.raises(ConfigError) as exc:
        check_preconditions(metrics, available)
    assert "reference.labels.category" in str(exc.value)
    assert "exact_label_match" in str(exc.value)


def test_failure_sentinel_is_nan() -> None:
    assert is_failure(math.nan)
    assert not is_failure(0.0)
