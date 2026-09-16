"""EvalCore CLI (Typer): ``init``, ``run``, ``compare``, ``baseline update``.

No console script yet (deferred to M6), so invoke as ``python -m evalcore.cli ...``.
Exit codes: 0 ok, 1 gate violation, 2 usage/IO error.
"""

import functools
from pathlib import Path
from typing import Annotated

import anyio
import typer

from evalcore.config import load_config
from evalcore.gate import GateError, read_summary, render_violations
from evalcore.gate import compare as gate_compare
from evalcore.reporters import render_json, render_markdown
from evalcore.runner import run_eval

app = typer.Typer(add_completion=False, help="EvalCore — LLM evaluation runner.")
baseline_app = typer.Typer(help="Manage committed baselines.")
app.add_typer(baseline_app, name="baseline")

_INIT_YAML = """project: my_project
adapter:
  type: python
  callable: adapters.my_target:answer
dataset: datasets/golden.jsonl
metrics:
  - name: exact_label_match
    params: {label: category}
run:
  concurrency: 8
"""

_INIT_TARGET = '''"""Your target: receives item.input (a dict); return a dict or TargetOutput."""

from typing import Any


def answer(input: dict[str, Any]) -> dict[str, Any]:
    # TODO: call your system and map its output to these fields.
    return {"answer": "TODO", "metadata": {}}
'''


@app.command()
def init(
    path: Annotated[Path, typer.Option("--path", help="Directory to scaffold into.")] = Path("."),
) -> None:
    """Scaffold evalcore.yaml + datasets/ + adapters/ (never overwrites existing files)."""
    path.mkdir(parents=True, exist_ok=True)
    (path / "datasets").mkdir(exist_ok=True)
    (path / "adapters").mkdir(exist_ok=True)

    targets = {
        path / "evalcore.yaml": _INIT_YAML,
        path / "datasets" / "golden.jsonl": "",
        path / "adapters" / "my_target.py": _INIT_TARGET,
    }
    created: list[str] = []
    for dest, content in targets.items():
        if dest.exists():
            typer.echo(f"exists, skipping: {dest}")
            continue
        dest.write_text(content, encoding="utf-8")
        created.append(str(dest))

    if created:
        typer.echo("Scaffolded:\n  " + "\n  ".join(created))


@app.command()
def run(
    config: Annotated[Path, typer.Option("--config", help="evalcore.yaml path.")],
    out_dir: Annotated[Path, typer.Option("--out-dir", help="Output directory.")] = Path("."),
    resume: Annotated[str | None, typer.Option("--resume", help="Resume a run_id.")] = None,
) -> None:
    """Execute a run and write report.json + report.md; prints the markdown summary."""
    cfg = load_config(config)
    report = anyio.run(functools.partial(run_eval, cfg, runs_dir=out_dir / "runs", resume=resume))

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(render_json(report), encoding="utf-8")
    markdown = render_markdown(report)
    (out_dir / "report.md").write_text(markdown, encoding="utf-8")

    typer.echo(markdown)
    typer.echo(f"Wrote {out_dir / 'report.json'} and {out_dir / 'report.md'}")


@app.command()
def compare(
    config: Annotated[Path, typer.Option("--config", help="evalcore.yaml path.")],
    report: Annotated[Path, typer.Option("--report", help="Run report JSON.")] = Path(
        "report.json"
    ),
    baseline: Annotated[
        Path | None, typer.Option("--baseline", help="Baseline JSON (overrides config).")
    ] = None,
    strict: Annotated[
        bool, typer.Option("--strict", help="Treat config/judge mismatch as failure.")
    ] = False,
) -> None:
    """Diff a run against a baseline and apply gate rules. Exit 1 on any violation."""
    cfg = load_config(config)
    if cfg.gate is None:
        typer.echo("No gate configured in evalcore.yaml.")
        raise typer.Exit(2)
    baseline_path = baseline or Path(cfg.gate.baseline)
    try:
        current = read_summary(report)
        base = read_summary(baseline_path)
    except GateError as e:
        typer.echo(str(e))
        raise typer.Exit(2) from e

    result = gate_compare(current, base, cfg.gate.rules, strict=strict)
    for warning in result.warnings:
        typer.echo(f"warning: {warning}")
    if not result.passed:
        typer.echo(render_violations(result))
        typer.echo(f"Gate FAILED: {len(result.violations)} violation(s).")
        raise typer.Exit(1)
    typer.echo("Gate passed.")


@baseline_app.command("update")
def baseline_update(
    config: Annotated[Path, typer.Option("--config", help="evalcore.yaml path.")],
    report: Annotated[Path, typer.Option("--report", help="Run report JSON.")] = Path(
        "report.json"
    ),
    baseline: Annotated[
        Path | None, typer.Option("--baseline", help="Baseline JSON (overrides config).")
    ] = None,
) -> None:
    """Write a new baseline from a run report (commit it, review it like code)."""
    cfg = load_config(config)
    target = baseline or (Path(cfg.gate.baseline) if cfg.gate else None)
    if target is None:
        typer.echo("No baseline path (config has no gate, and --baseline not given).")
        raise typer.Exit(2)
    try:
        summary = read_summary(report)
    except GateError as e:
        typer.echo(str(e))
        raise typer.Exit(2) from e
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Wrote baseline {target}")


if __name__ == "__main__":
    app()
