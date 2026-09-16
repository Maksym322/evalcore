"""Markdown reporter: a readable summary of a RunReport (TechDesign §2.5).

Header + one aggregate table (metric, mean, p50, count, failures), metrics sorted by
name for deterministic output.
"""

from evalcore.schema import RunReport


def render_markdown(report: RunReport) -> str:
    lines = [
        f"# EvalCore report — {report.project}",
        "",
        f"run `{report.run_id}` · {report.started_at.isoformat()} · {report.items} items",
        "",
    ]

    if not report.aggregates:
        lines.append("_No metrics._")
        return "\n".join(lines) + "\n"

    lines += [
        "| Metric | Mean | p50 | Count | Failures |",
        "|--------|-----:|----:|------:|---------:|",
    ]
    for name in sorted(report.aggregates):
        agg = report.aggregates[name]
        lines.append(f"| {name} | {agg.mean:.3f} | {agg.p50:.3f} | {agg.count} | {agg.failures} |")
    return "\n".join(lines) + "\n"
