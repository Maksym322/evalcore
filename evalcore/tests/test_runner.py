"""Tests for the runner: dataset loading, subset filter, ULID, aggregation, journal, resume."""

import json
import math
from pathlib import Path

import pytest

from evalcore.config import (
    ConfigError,
    JudgeConfig,
    MetricConfig,
    PythonAdapterConfig,
    RunConfig,
    RunSettings,
    SmokeSubset,
)
from evalcore.runner import (
    DatasetError,
    _apply_subset,
    load_dataset,
    new_ulid,
    run_eval,
)
from evalcore.schema import DatasetItem, Reference
from tests._fake_judge import FakeJudge

FAKE = "tests._fake_target:retrieval"


# ---- load_dataset ----------------------------------------------------------


def _write_jsonl(tmp_path: Path, lines: list[str]) -> Path:
    p = tmp_path / "data.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_load_dataset_valid_and_skips_blank(tmp_path: Path) -> None:
    p = _write_jsonl(
        tmp_path,
        [
            '{"id": "a", "input": {}, "reference": {"answer": "x"}}',
            "",
            '{"id": "b", "input": {}, "reference": {}}',
        ],
    )
    items = load_dataset(p)
    assert [it.id for it in items] == ["a", "b"]


def test_load_dataset_malformed_line(tmp_path: Path) -> None:
    p = _write_jsonl(tmp_path, ['{"id": "a", "input": {}, "reference": {}}', "{not json"])
    with pytest.raises(DatasetError) as exc:
        load_dataset(p)
    assert ":2:" in str(exc.value)


def test_load_dataset_schema_violation(tmp_path: Path) -> None:
    p = _write_jsonl(tmp_path, ['{"input": {}, "reference": {}}'])  # missing id
    with pytest.raises(DatasetError):
        load_dataset(p)


def test_load_dataset_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DatasetError) as exc:
        load_dataset(tmp_path / "nope.jsonl")
    assert "not found" in str(exc.value).lower()


def test_load_dataset_empty(tmp_path: Path) -> None:
    p = _write_jsonl(tmp_path, ["", "  "])
    with pytest.raises(DatasetError) as exc:
        load_dataset(p)
    assert "empty" in str(exc.value).lower()


# ---- subset + ulid ---------------------------------------------------------


def _item(item_id: str, tags: list[str]) -> DatasetItem:
    return DatasetItem(id=item_id, input={}, reference=Reference(), tags=tags)


def test_apply_subset_filters_and_caps() -> None:
    items = [
        _item("a", ["smoke"]),
        _item("b", ["full"]),
        _item("c", ["smoke"]),
        _item("d", ["smoke"]),
    ]
    out = _apply_subset(items, SmokeSubset(tags=["smoke"], max_items=2))
    assert [it.id for it in out] == ["a", "c"]


def test_apply_subset_none_returns_all() -> None:
    items = [_item("a", []), _item("b", [])]
    assert _apply_subset(items, None) == items


def test_new_ulid_shape() -> None:
    u = new_ulid()
    assert len(u) == 26
    assert set(u) <= set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    assert new_ulid() != new_ulid()


# ---- run_eval end to end ---------------------------------------------------

RECALL = MetricConfig(name="retrieval_recall_at_k", params={"k": 3})
LABEL = MetricConfig(name="exact_label_match", params={"label": "category"})
LATENCY = MetricConfig(name="latency_budget", params={"max_ms": 1000})


def _dataset_for_run(tmp_path: Path) -> Path:
    # i3 has empty relevant_ids -> recall is a NaN failure (not a zero).
    return _write_jsonl(
        tmp_path,
        [
            json.dumps(
                {
                    "id": "i1",
                    "input": {"docs": ["a", "b"], "cat": "x"},
                    "reference": {"relevant_ids": ["a", "b"], "labels": {"category": "x"}},
                }
            ),
            json.dumps(
                {
                    "id": "i2",
                    "input": {"docs": ["a"], "cat": "y"},
                    "reference": {"relevant_ids": ["a", "b"], "labels": {"category": "y"}},
                }
            ),
            json.dumps(
                {
                    "id": "i3",
                    "input": {"cat": "z"},
                    "reference": {"relevant_ids": ["a"], "labels": {"category": "q"}},
                }
            ),
        ],
    )


def _config(dataset: Path) -> RunConfig:
    return RunConfig(
        project="rt",
        adapter=PythonAdapterConfig(type="python", callable=FAKE),
        dataset=str(dataset),
        metrics=[RECALL, LABEL, LATENCY],
        run=RunSettings(concurrency=2),
    )


async def test_run_eval_aggregates_and_failures(tmp_path: Path) -> None:
    report = await run_eval(_config(_dataset_for_run(tmp_path)), runs_dir=tmp_path / "runs")

    assert report.items == 3
    recall = report.aggregates["retrieval_recall_at_k"]
    # i1=1.0, i2=0.5, i3=NaN -> finite mean 0.75, count 2, failures 1
    assert recall.count == 2
    assert recall.failures == 1
    assert recall.mean == pytest.approx(0.75)

    label = report.aggregates["exact_label_match"]
    # i1 match, i2 match, i3 mismatch -> mean 2/3, no failures
    assert label.failures == 0
    assert label.mean == pytest.approx(2 / 3)

    assert report.aggregates["latency_budget"].mean == pytest.approx(1.0)
    assert len(report.config_hash) == 64


async def test_run_eval_writes_journal(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    report = await run_eval(_config(_dataset_for_run(tmp_path)), runs_dir=runs)
    journal = runs / f"{report.run_id}.jsonl"
    lines = [line for line in journal.read_text().splitlines() if line.strip()]
    assert len(lines) == 3  # one record per item


async def test_run_eval_resume_uses_journal(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    cfg = _config(_dataset_for_run(tmp_path))
    first = await run_eval(cfg, runs_dir=runs)

    # Resume the same run_id: all items already journaled -> identical aggregates, no dup lines.
    second = await run_eval(cfg, runs_dir=runs, resume=first.run_id)
    assert second.aggregates["retrieval_recall_at_k"].mean == pytest.approx(0.75)
    assert second.items == 3

    journal = runs / f"{first.run_id}.jsonl"
    lines = [line for line in journal.read_text().splitlines() if line.strip()]
    assert len(lines) == 3  # resume did not re-append


def test_journal_nan_round_trips(tmp_path: Path) -> None:
    # The internal journal keeps NaN (allow_nan) so resume restores failures faithfully.
    from evalcore.runner import _append_journal, _read_journal
    from evalcore.schema import MetricResult

    journal = tmp_path / "j.jsonl"
    item = _item("i1", [])
    _append_journal(journal, item, [MetricResult(metric="m", item_id="i1", score=math.nan)])
    _done, results = _read_journal(journal)
    assert math.isnan(results[0].score)


async def test_run_eval_wires_judged_metric_and_pins_version(tmp_path: Path) -> None:
    dataset = _write_jsonl(
        tmp_path,
        ['{"id":"i1","input":{"answer":"Reset password"},"reference":{}}'],
    )
    config = RunConfig(
        project="judged",
        adapter=PythonAdapterConfig(type="python", callable="tests._fake_target:grounded"),
        dataset=str(dataset),
        metrics=[
            MetricConfig(
                name="faithfulness",
                judge=JudgeConfig(provider="gemini", model="gemini-3.5-flash-lite", prompt="v1"),
            )
        ],
    )
    report = await run_eval(
        config,
        runs_dir=tmp_path / "runs",
        judge_factory=lambda _pin, _cache: FakeJudge("fake/fake@v1"),
    )
    assert report.judge_versions == {"faithfulness": "fake/fake@v1"}
    assert report.aggregates["faithfulness"].mean == 1.0


async def test_judged_metric_requires_pin(tmp_path: Path) -> None:
    dataset = _write_jsonl(
        tmp_path,
        ['{"id":"i1","input":{"answer":"x"},"reference":{}}'],
    )
    config = RunConfig(
        project="judged",
        adapter=PythonAdapterConfig(type="python", callable="tests._fake_target:grounded"),
        dataset=str(dataset),
        metrics=[MetricConfig(name="faithfulness")],
    )
    with pytest.raises(ConfigError, match="requires a judge"):
        await run_eval(config, runs_dir=tmp_path / "runs")
