"""CLI tests (Typer CliRunner). `test_run_toy` doubles as the M1 end-to-end check.

These assume pytest runs from the evalcore repo root so `examples.toy.target` imports and
`examples/toy/golden.jsonl` resolves relative to CWD.
"""

from pathlib import Path

from typer.testing import CliRunner

from evalcore.cli import app

runner = CliRunner()


def test_init_scaffolds(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "evalcore.yaml").exists()
    assert (tmp_path / "datasets").is_dir()
    assert (tmp_path / "adapters" / "my_target.py").exists()


def test_init_does_not_clobber(tmp_path: Path) -> None:
    keep = "project: keep_me\n"
    (tmp_path / "evalcore.yaml").write_text(keep, encoding="utf-8")
    result = runner.invoke(app, ["init", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "evalcore.yaml").read_text() == keep


def test_run_toy_end_to_end(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["run", "--config", "examples/toy/evalcore.yaml", "--out-dir", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    md = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "retrieval_recall_at_k" in md
    assert "exact_label_match" in md
    assert (tmp_path / "report.json").exists()
    # recall: q1=1.0,q2=1.0,q3=0.5,q4=0.5,q5=1.0 -> mean 0.800
    assert "| retrieval_recall_at_k | 0.800 |" in md
