"""Offline CI regression gate tests (EC-001).

Validates deterministic regression gates for CI:
1. Synthetic gate pass with a genuine gate configuration (exit code 0).
2. Deliberate regression failure with violations table (exit code 1).
3. Missing gate configuration in toy config (exit code 2).
4. Missing baseline file error handling (exit code 2).
5. Strict gate evaluation on configuration hash mismatches.
6. Deterministic toy evaluation pipeline execution producing bounded JSON reports.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from evalcore.cli import app
from evalcore.gate import read_summary

runner = CliRunner()

_CI_GATE_CONFIG = """project: ci_gate_project
adapter:
  type: python
  callable: examples.toy.target:answer
dataset: examples/toy/golden.jsonl
metrics:
  - name: retrieval_recall_at_k
    params: {k: 3}
  - name: exact_label_match
    params: {label: category}
gate:
  baseline: baseline.json
  rules:
    - metric: retrieval_recall_at_k
      max_drop_pct: 5.0
      min_value: 0.70
    - metric: exact_label_match
      max_drop_pct: 10.0
      min_value: 0.60
"""


def _make_report_json(
    *,
    recall: float,
    label_match: float,
    config_hash: str = "cfg_hash_v1",
    judge_versions: dict[str, str] | None = None,
) -> str:
    return json.dumps(
        {
            "project": "ci_gate_project",
            "run_id": "test_run_123",
            "config_hash": config_hash,
            "judge_versions": judge_versions or {},
            "aggregates": {
                "retrieval_recall_at_k": {
                    "mean": recall,
                    "p50": recall,
                    "count": 10,
                    "failures": 0,
                },
                "exact_label_match": {
                    "mean": label_match,
                    "p50": label_match,
                    "count": 10,
                    "failures": 0,
                },
            },
        },
        indent=2,
    )


def test_ci_gate_synthetic_pass_exit_0(tmp_path: Path) -> None:
    """A run matching or exceeding the baseline passes the gate with exit code 0."""
    cfg_path = tmp_path / "evalcore.yaml"
    cfg_path.write_text(_CI_GATE_CONFIG, encoding="utf-8")

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        _make_report_json(recall=0.80, label_match=0.85),
        encoding="utf-8",
    )

    # Current report has identical metrics -> 0% drop
    report_path = tmp_path / "report.json"
    report_path.write_text(
        _make_report_json(recall=0.80, label_match=0.85),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "compare",
            "--config",
            str(cfg_path),
            "--report",
            str(report_path),
            "--baseline",
            str(baseline_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Gate passed." in result.output


def test_ci_gate_deliberate_regression_fail_exit_1(tmp_path: Path) -> None:
    """A deliberate regression exceeding max_drop_pct fails the gate with exit code 1."""
    cfg_path = tmp_path / "evalcore.yaml"
    cfg_path.write_text(_CI_GATE_CONFIG, encoding="utf-8")

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        _make_report_json(recall=0.80, label_match=0.85),
        encoding="utf-8",
    )

    # Regress recall from 0.80 to 0.60 (25% drop > 5% allowed, and 0.60 < 0.70 min_value)
    regressed_report = tmp_path / "regressed_report.json"
    regressed_report.write_text(
        _make_report_json(recall=0.60, label_match=0.85),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "compare",
            "--config",
            str(cfg_path),
            "--report",
            str(regressed_report),
            "--baseline",
            str(baseline_path),
        ],
    )
    assert result.exit_code == 1
    assert "Gate FAILED" in result.output
    assert "retrieval_recall_at_k" in result.output
    assert "max_drop_pct" in result.output or "min_value" in result.output


def test_ci_gate_toy_config_missing_gate_section_exit_2(tmp_path: Path) -> None:
    """Toy config has no gate section; compare exits with code 2."""
    toy_cfg = Path("examples/toy/evalcore.yaml")
    assert toy_cfg.is_file()

    dummy_report = tmp_path / "report.json"
    dummy_report.write_text(_make_report_json(recall=0.80, label_match=0.80), encoding="utf-8")

    result = runner.invoke(
        app,
        ["compare", "--config", str(toy_cfg), "--report", str(dummy_report)],
    )
    assert result.exit_code == 2
    assert "No gate configured in evalcore.yaml." in result.output


def test_ci_gate_missing_baseline_file_exit_2(tmp_path: Path) -> None:
    """If baseline file does not exist, compare exits with code 2."""
    cfg_path = tmp_path / "evalcore.yaml"
    cfg_path.write_text(_CI_GATE_CONFIG, encoding="utf-8")

    report_path = tmp_path / "report.json"
    report_path.write_text(_make_report_json(recall=0.80, label_match=0.80), encoding="utf-8")

    non_existent_baseline = tmp_path / "non_existent_baseline.json"

    result = runner.invoke(
        app,
        [
            "compare",
            "--config",
            str(cfg_path),
            "--report",
            str(report_path),
            "--baseline",
            str(non_existent_baseline),
        ],
    )
    assert result.exit_code == 2
    assert (
        "not found" in result.output
        or "No such file" in result.output
        or "Baseline" in result.output
    )


def test_ci_gate_strict_config_hash_mismatch(tmp_path: Path) -> None:
    """Config hash mismatch warns normally, but fails under --strict mode."""
    cfg_path = tmp_path / "evalcore.yaml"
    cfg_path.write_text(_CI_GATE_CONFIG, encoding="utf-8")

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        _make_report_json(recall=0.80, label_match=0.85, config_hash="hash_a"),
        encoding="utf-8",
    )

    report_path = tmp_path / "report.json"
    report_path.write_text(
        _make_report_json(recall=0.80, label_match=0.85, config_hash="hash_b"),
        encoding="utf-8",
    )

    # Without --strict: warning only, passes with exit code 0
    non_strict_res = runner.invoke(
        app,
        [
            "compare",
            "--config",
            str(cfg_path),
            "--report",
            str(report_path),
            "--baseline",
            str(baseline_path),
        ],
    )
    assert non_strict_res.exit_code == 0
    assert "warning:" in non_strict_res.output

    # With --strict: fails with exit code 1
    strict_res = runner.invoke(
        app,
        [
            "compare",
            "--config",
            str(cfg_path),
            "--report",
            str(report_path),
            "--baseline",
            str(baseline_path),
            "--strict",
        ],
    )
    assert strict_res.exit_code == 1
    assert "Gate FAILED" in strict_res.output


def test_ci_toy_deterministic_eval_and_baseline_flow(tmp_path: Path) -> None:
    """Full deterministic flow: run toy evaluation, update baseline, gate passes."""
    toy_cfg = Path("examples/toy/evalcore.yaml")
    out_dir = tmp_path / "eval_out"

    # 1. Run deterministic toy eval
    run_res = runner.invoke(
        app,
        ["run", "--config", str(toy_cfg), "--out-dir", str(out_dir)],
    )
    assert run_res.exit_code == 0, run_res.output
    report_file = out_dir / "report.json"
    assert report_file.is_file(), "report.json must be generated"

    # Verify report is valid and has expected aggregates
    summary = read_summary(report_file)
    assert summary.project == "toy"
    assert "retrieval_recall_at_k" in summary.aggregates
    assert summary.aggregates["retrieval_recall_at_k"].mean == 0.80

    # 2. Use report as baseline for a genuine gate config
    baseline_file = tmp_path / "baseline.json"
    gate_cfg_file = tmp_path / "gate_evalcore.yaml"
    gate_cfg_content = f"""project: toy
adapter:
  type: python
  callable: examples.toy.target:answer
dataset: examples/toy/golden.jsonl
metrics:
  - name: retrieval_recall_at_k
    params: {{k: 3}}
gate:
  baseline: {baseline_file.name}
  rules:
    - metric: retrieval_recall_at_k
      max_drop_pct: 1.0
      min_value: 0.75
"""
    gate_cfg_file.write_text(gate_cfg_content, encoding="utf-8")

    # Update baseline from report
    update_res = runner.invoke(
        app,
        [
            "baseline",
            "update",
            "--config",
            str(gate_cfg_file),
            "--report",
            str(report_file),
            "--baseline",
            str(baseline_file),
        ],
    )
    assert update_res.exit_code == 0
    assert baseline_file.is_file()

    # Compare against self -> passes gate
    compare_res = runner.invoke(
        app,
        [
            "compare",
            "--config",
            str(gate_cfg_file),
            "--report",
            str(report_file),
            "--baseline",
            str(baseline_file),
        ],
    )
    assert compare_res.exit_code == 0
    assert "Gate passed." in compare_res.output
