"""Round-trip tests for the core schema models (TechDesign §2.1).

Each test builds an instance and asserts equality across a dict round-trip and a
JSON round-trip, so both serialization paths are exercised.
"""

from datetime import UTC, datetime

from evalcore.schema import (
    Aggregate,
    DatasetItem,
    MetricResult,
    Reference,
    RunReport,
    TargetOutput,
)


def test_reference_round_trip() -> None:
    m = Reference(answer="yes", relevant_ids=["docs/a.md#1"], labels={"category": "billing"})
    assert m == Reference.model_validate(m.model_dump())
    assert m == Reference.model_validate_json(m.model_dump_json())


def test_reference_defaults() -> None:
    m = Reference()
    assert m.answer is None
    assert m.relevant_ids == []
    assert m.labels == {}
    assert m == Reference.model_validate(m.model_dump())


def test_dataset_item_round_trip() -> None:
    m = DatasetItem(
        id="item-1",
        input={"question": "How do I reset my password?"},
        reference=Reference(answer="Use the reset link", relevant_ids=["docs/auth.md#3"]),
        tags=["auth", "smoke"],
    )
    assert m == DatasetItem.model_validate(m.model_dump())
    assert m == DatasetItem.model_validate_json(m.model_dump_json())


def test_target_output_round_trip() -> None:
    m = TargetOutput(
        answer="Use the reset link on the login page.",
        retrieved_context=["To reset, click ..."],
        retrieved_ids=["docs/auth.md#3"],
        metadata={"latency_ms": 812, "cost_usd": 0.0004},
    )
    assert m == TargetOutput.model_validate(m.model_dump())
    assert m == TargetOutput.model_validate_json(m.model_dump_json())


def test_target_output_optional_none() -> None:
    m = TargetOutput(answer="escalated")
    assert m.retrieved_context is None
    assert m.retrieved_ids is None
    assert m.metadata == {}
    assert m == TargetOutput.model_validate_json(m.model_dump_json())


def test_metric_result_round_trip() -> None:
    m = MetricResult(
        metric="retrieval_recall_at_k",
        item_id="item-1",
        score=0.75,
        details={"hit": ["docs/auth.md#3"]},
    )
    assert m == MetricResult.model_validate(m.model_dump())
    assert m == MetricResult.model_validate_json(m.model_dump_json())


def test_aggregate_round_trip() -> None:
    m = Aggregate(mean=0.82, p50=0.9, count=40, failures=2)
    assert m == Aggregate.model_validate(m.model_dump())
    assert m == Aggregate.model_validate_json(m.model_dump_json())


def test_run_report_round_trip() -> None:
    m = RunReport(
        project="ticketpilot",
        run_id="01J000000000000000000000AB",
        started_at=datetime(2026, 7, 2, 12, 30, 0, tzinfo=UTC),
        config_hash="a" * 64,
        judge_versions={"faithfulness": "anthropic/claude@prompt_v1"},
        items=42,
        aggregates={"retrieval_recall_at_k": Aggregate(mean=0.82, p50=0.9, count=40, failures=2)},
        per_item=[
            MetricResult(
                metric="retrieval_recall_at_k",
                item_id="item-1",
                score=0.75,
                details={"hit": ["docs/auth.md#3"]},
            )
        ],
    )
    assert m == RunReport.model_validate(m.model_dump())
    assert m == RunReport.model_validate_json(m.model_dump_json())
