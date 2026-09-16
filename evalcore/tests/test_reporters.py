"""Tests for the JSON and Markdown reporters against a sample RunReport."""

import json
import math
from datetime import UTC, datetime

from evalcore.reporters import render_json, render_markdown
from evalcore.schema import Aggregate, MetricResult, RunReport


def _sample_report() -> RunReport:
    return RunReport(
        project="ticketpilot",
        run_id="01J000000000000000000000AB",
        started_at=datetime(2026, 7, 2, 12, 30, 0, tzinfo=UTC),
        config_hash="a" * 64,
        judge_versions={},
        items=3,
        aggregates={
            "retrieval_recall_at_k": Aggregate(mean=0.82, p50=0.9, count=3, failures=0),
            "exact_label_match": Aggregate(mean=0.5, p50=1.0, count=2, failures=1),
        },
        per_item=[
            MetricResult(metric="retrieval_recall_at_k", item_id="i1", score=0.75),
            # A failed item: score is NaN -> must become null in JSON.
            MetricResult(
                metric="exact_label_match",
                item_id="i2",
                score=math.nan,
                details={"error": "reference.labels['category'] missing"},
            ),
        ],
    )


def _empty_report() -> RunReport:
    return RunReport(
        project="empty",
        run_id="01J000000000000000000000ZZ",
        started_at=datetime(2026, 7, 2, tzinfo=UTC),
        config_hash="b" * 64,
        judge_versions={},
        items=0,
        aggregates={},
        per_item=[],
    )


# ---- JSON reporter ---------------------------------------------------------


def test_json_is_valid_and_parseable() -> None:
    parsed = json.loads(render_json(_sample_report()))
    assert parsed["project"] == "ticketpilot"
    assert parsed["items"] == 3
    assert parsed["aggregates"]["retrieval_recall_at_k"]["mean"] == 0.82


def test_json_nan_score_becomes_null() -> None:
    parsed = json.loads(render_json(_sample_report()))
    failed = next(r for r in parsed["per_item"] if r["item_id"] == "i2")
    assert failed["score"] is None
    assert "missing" in failed["details"]["error"]


def test_json_datetime_is_iso_string() -> None:
    parsed = json.loads(render_json(_sample_report()))
    assert parsed["started_at"].startswith("2026-07-02T12:30:00")


def test_json_rejects_no_stray_nan() -> None:
    # allow_nan=False means any leaked non-finite float would raise, not silently emit NaN.
    text = render_json(_sample_report())
    assert "NaN" not in text
    assert "null" in text


# ---- Markdown reporter -----------------------------------------------------


def test_markdown_has_header_and_meta() -> None:
    md = render_markdown(_sample_report())
    assert "# EvalCore report — ticketpilot" in md
    assert "01J000000000000000000000AB" in md
    assert "3 items" in md


def test_markdown_table_rows_and_order() -> None:
    md = render_markdown(_sample_report())
    assert "| Metric | Mean | p50 | Count | Failures |" in md
    # sorted by metric name: exact_label_match before retrieval_recall_at_k
    assert md.index("exact_label_match") < md.index("retrieval_recall_at_k")
    assert "| exact_label_match | 0.500 | 1.000 | 2 | 1 |" in md
    assert "| retrieval_recall_at_k | 0.820 | 0.900 | 3 | 0 |" in md


def test_markdown_empty_aggregates() -> None:
    md = render_markdown(_empty_report())
    assert "_No metrics._" in md
    assert "| Metric |" not in md
