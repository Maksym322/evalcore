"""Tests for the regression gate: rule table + CLI exit codes on synthetic data (§2.6)."""

import json
from pathlib import Path

from typer.testing import CliRunner

from evalcore.cli import app
from evalcore.config import GateRule
from evalcore.gate import Baseline, compare, read_summary, render_violations
from evalcore.schema import Aggregate

runner = CliRunner()


def _bl(
    *, config_hash: str = "h1", judge_versions: dict[str, str] | None = None, **means: float
) -> Baseline:
    aggs = {m: Aggregate(mean=v, p50=v, count=10, failures=0) for m, v in means.items()}
    return Baseline(
        project="p",
        run_id="r",
        config_hash=config_hash,
        judge_versions=judge_versions or {},
        aggregates=aggs,
    )


RULE = GateRule(metric="recall", max_drop_pct=5.0)


# ---- rule table ------------------------------------------------------------


def test_pass_when_stable() -> None:
    result = compare(_bl(recall=0.80), _bl(recall=0.80), [RULE])
    assert result.passed
    assert result.violations == []


def test_max_drop_violation() -> None:
    result = compare(_bl(recall=0.70), _bl(recall=0.80), [RULE])  # 12.5% drop
    assert not result.passed
    assert result.violations[0].rule == "max_drop_pct"


def test_max_drop_within_tolerance() -> None:
    result = compare(_bl(recall=0.79), _bl(recall=0.80), [RULE])  # 1.25% drop
    assert result.passed


def test_improvement_never_violates() -> None:
    result = compare(_bl(recall=0.95), _bl(recall=0.80), [RULE])
    assert result.passed


def test_min_value_violation() -> None:
    rule = GateRule(metric="recall", max_drop_pct=100.0, min_value=0.75)
    result = compare(_bl(recall=0.70), _bl(recall=0.72), [rule])
    assert not result.passed
    assert any(v.rule == "min_value" for v in result.violations)


def test_missing_metric_in_run_is_violation() -> None:
    result = compare(_bl(other=0.9), _bl(recall=0.8), [RULE])
    assert not result.passed
    assert result.violations[0].rule == "missing_metric"


def test_metric_missing_in_baseline_warns_only() -> None:
    result = compare(_bl(recall=0.8), _bl(other=0.9), [RULE])
    assert result.passed  # max_drop skipped
    assert any("not in baseline" in w for w in result.warnings)


def test_config_hash_mismatch_warns_then_fails_strict() -> None:
    cur = _bl(recall=0.8, config_hash="DIFFERENT")
    base = _bl(recall=0.8, config_hash="h1")
    assert compare(cur, base, [RULE]).passed  # warning only
    assert compare(cur, base, [RULE]).warnings
    assert not compare(cur, base, [RULE], strict=True).passed  # strict => fail


def test_judge_version_mismatch_strict() -> None:
    cur = _bl(recall=0.8, judge_versions={"faithfulness": "anthropic/m@v2"})
    base = _bl(recall=0.8, judge_versions={"faithfulness": "anthropic/m@v1"})
    assert not compare(cur, base, [RULE], strict=True).passed


def test_render_violations_table() -> None:
    result = compare(_bl(recall=0.70), _bl(recall=0.80), [RULE])
    table = render_violations(result)
    assert "| Metric | Rule |" in table
    assert "recall" in table


# ---- CLI exit codes --------------------------------------------------------

_CONFIG = """project: p
adapter: {type: python, callable: a.b:c}
dataset: d.jsonl
metrics:
  - {name: retrieval_recall_at_k, params: {k: 3}}
gate:
  baseline: baseline.json
  rules:
    - {metric: recall, max_drop_pct: 5, min_value: 0.5}
"""


def _summary_json(recall: float) -> str:
    return json.dumps(
        {
            "project": "p",
            "run_id": "r",
            "config_hash": "h1",
            "judge_versions": {},
            "aggregates": {"recall": {"mean": recall, "p50": recall, "count": 10, "failures": 0}},
        }
    )


def _setup(
    tmp_path: Path, current_recall: float, baseline_recall: float
) -> tuple[Path, Path, Path]:
    cfg = tmp_path / "evalcore.yaml"
    cfg.write_text(_CONFIG, encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text(_summary_json(current_recall), encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(_summary_json(baseline_recall), encoding="utf-8")
    return cfg, report, baseline


def test_cli_compare_pass_exit_0(tmp_path: Path) -> None:
    cfg, report, baseline = _setup(tmp_path, 0.80, 0.80)
    result = runner.invoke(
        app,
        ["compare", "--config", str(cfg), "--report", str(report), "--baseline", str(baseline)],
    )
    assert result.exit_code == 0, result.output


def test_cli_compare_fail_exit_1(tmp_path: Path) -> None:
    cfg, report, baseline = _setup(tmp_path, 0.60, 0.80)  # 25% drop + below floor
    result = runner.invoke(
        app,
        ["compare", "--config", str(cfg), "--report", str(report), "--baseline", str(baseline)],
    )
    assert result.exit_code == 1
    assert "Gate FAILED" in result.output


def test_cli_baseline_update_writes_file(tmp_path: Path) -> None:
    cfg, report, _ = _setup(tmp_path, 0.80, 0.80)
    out = tmp_path / "new_baseline.json"
    result = runner.invoke(
        app,
        [
            "baseline",
            "update",
            "--config",
            str(cfg),
            "--report",
            str(report),
            "--baseline",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    written = read_summary(out)
    assert written.aggregates["recall"].mean == 0.80
