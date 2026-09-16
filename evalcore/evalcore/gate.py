"""Regression gate: compare a run's aggregates against a committed baseline (TechDesign §2.6).

A Baseline is a frozen snapshot of ``aggregates`` + ``config_hash`` + ``judge_versions`` — the
same fields a RunReport carries, so a report.json loads straight into one (extra keys ignored).
Rules come from config: ``max_drop_pct`` (relative) and optional ``min_value`` (absolute floor).
Config-hash / judge-version mismatches are warnings, or violations under ``strict``.
"""

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from evalcore.config import GateRule
from evalcore.schema import Aggregate


class GateError(Exception):
    """Raised when a report or baseline file is missing or malformed."""


class Baseline(BaseModel):
    """Frozen comparison snapshot. Loads from a baseline.json or a full report.json."""

    model_config = ConfigDict(extra="ignore")

    project: str
    run_id: str
    config_hash: str
    judge_versions: dict[str, str] = {}
    aggregates: dict[str, Aggregate]


@dataclass
class Violation:
    metric: str
    rule: str  # max_drop_pct | min_value | missing_metric | mismatch
    baseline: float | None
    current: float | None
    threshold: float
    detail: str


@dataclass
class GateResult:
    violations: list[Violation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


def read_summary(path: str | Path) -> Baseline:
    """Load a report.json or baseline.json into a Baseline (per_item etc. ignored)."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise GateError(f"file not found: {p}") from e
    try:
        return Baseline.model_validate_json(text)
    except ValidationError as e:
        raise GateError(f"invalid report/baseline ({p}): {e}") from e


def compare(
    current: Baseline, baseline: Baseline, rules: list[GateRule], *, strict: bool = False
) -> GateResult:
    """Apply gate rules; gating is on each metric's ``mean``. Any violation => not passed."""
    result = GateResult()

    def _mismatch(msg: str) -> None:
        if strict:
            result.violations.append(Violation("-", "mismatch", None, None, 0.0, msg))
        else:
            result.warnings.append(msg)

    if current.config_hash != baseline.config_hash:
        _mismatch(
            f"config_hash differs: baseline {baseline.config_hash[:12]} vs run "
            f"{current.config_hash[:12]} — deltas may be meaningless"
        )
    if current.judge_versions != baseline.judge_versions:
        _mismatch("judge_versions differ between baseline and run")

    for rule in rules:
        cur = current.aggregates.get(rule.metric)
        if cur is None:
            result.violations.append(
                Violation(rule.metric, "missing_metric", None, None, 0.0, "metric not in the run")
            )
            continue

        base = baseline.aggregates.get(rule.metric)
        if base is None:
            result.warnings.append(f"{rule.metric}: not in baseline; skipping max_drop_pct")
        elif base.mean > 0:
            drop_pct = (base.mean - cur.mean) / base.mean * 100.0
            if drop_pct > rule.max_drop_pct:
                result.violations.append(
                    Violation(
                        rule.metric,
                        "max_drop_pct",
                        base.mean,
                        cur.mean,
                        rule.max_drop_pct,
                        f"dropped {drop_pct:.1f}% (limit {rule.max_drop_pct}%)",
                    )
                )

        if rule.min_value is not None and cur.mean < rule.min_value:
            result.violations.append(
                Violation(
                    rule.metric,
                    "min_value",
                    base.mean if base else None,
                    cur.mean,
                    rule.min_value,
                    f"{cur.mean:.3f} below floor {rule.min_value}",
                )
            )

    return result


def render_violations(result: GateResult) -> str:
    """Markdown table of violations for stdout / PR comment."""
    lines = [
        "| Metric | Rule | Baseline | Current | Threshold | Detail |",
        "|--------|------|---------:|--------:|----------:|--------|",
    ]
    for v in result.violations:
        b = f"{v.baseline:.3f}" if v.baseline is not None else "—"
        c = f"{v.current:.3f}" if v.current is not None else "—"
        lines.append(f"| {v.metric} | {v.rule} | {b} | {c} | {v.threshold} | {v.detail} |")
    return "\n".join(lines) + "\n"
