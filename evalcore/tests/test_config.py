"""Tests for the config loader: a valid config plus common mistakes (TechDesign §2.2-2.5)."""

from pathlib import Path

import pytest

from evalcore.config import ConfigError, load_config

VALID_FULL = """
project: ticketpilot
adapter:
  type: python
  callable: my_pkg.eval:answer
dataset: eval/datasets/golden.jsonl
metrics:
  - name: retrieval_recall_at_k
    params: {k: 5}
  - name: faithfulness
    judge: {provider: anthropic, model: claude-sonnet-4-6, prompt: default}
gate:
  baseline: eval/baselines/main.json
  rules:
    - {metric: faithfulness, max_drop_pct: 5, min_value: 0.75}
    - {metric: retrieval_recall_at_k, max_drop_pct: 5}
run:
  concurrency: 4
  seed: 7
  temperature: 0
  smoke_subset: {tags: [smoke], max_items: 10}
"""

VALID_MINIMAL = """
project: toy
adapter:
  type: python
  callable: examples.toy.target:answer
dataset: examples/toy/dataset.jsonl
metrics:
  - name: exact_label_match
    params: {label: category}
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "evalcore.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_valid_full_config(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path, VALID_FULL))
    assert cfg.project == "ticketpilot"
    assert cfg.adapter.type == "python"
    assert cfg.adapter.callable == "my_pkg.eval:answer"
    assert cfg.dataset == "eval/datasets/golden.jsonl"
    assert len(cfg.metrics) == 2
    assert cfg.metrics[0].params == {"k": 5}
    assert cfg.metrics[1].judge is not None
    assert cfg.metrics[1].judge.model == "claude-sonnet-4-6"
    assert cfg.gate is not None
    assert cfg.gate.rules[0].min_value == 0.75
    assert cfg.run.concurrency == 4
    assert cfg.run.smoke_subset is not None
    assert cfg.run.smoke_subset.max_items == 10


def test_valid_minimal_applies_defaults(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path, VALID_MINIMAL))
    assert cfg.gate is None
    # run block omitted -> documented defaults
    assert cfg.run.concurrency == 8
    assert cfg.run.seed == 42
    assert cfg.run.temperature == 0.0
    assert cfg.run.smoke_subset is None


def test_unknown_top_level_key(tmp_path: Path) -> None:
    bad = VALID_MINIMAL + "datasett: oops\n"
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, bad))
    assert "datasett" in str(exc.value)


def test_unknown_nested_key(tmp_path: Path) -> None:
    bad = VALID_MINIMAL.replace("callable:", "typo: x\n  callable:")
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, bad))
    assert "typo" in str(exc.value)


def test_missing_required_key(tmp_path: Path) -> None:
    bad = VALID_MINIMAL.replace("project: toy\n", "")
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, bad))
    assert "project" in str(exc.value)


def test_empty_metrics_list_rejected(tmp_path: Path) -> None:
    bad = """
project: toy
adapter: {type: python, callable: a.b:c}
dataset: d.jsonl
metrics: []
"""
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, bad))
    assert "metrics" in str(exc.value)


def test_unknown_adapter_type(tmp_path: Path) -> None:
    bad = VALID_MINIMAL.replace("type: python", "type: grpc")
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, bad))
    assert "grpc" in str(exc.value)


def test_wrong_scalar_type(tmp_path: Path) -> None:
    bad = VALID_MINIMAL + "run: {concurrency: eight}\n"
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, bad))
    assert "run.concurrency" in str(exc.value)


def test_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(tmp_path / "nope.yaml")
    assert "not found" in str(exc.value).lower()


def test_empty_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, "\n"))
    assert "empty" in str(exc.value).lower()


def test_http_adapter_parses(tmp_path: Path) -> None:
    cfg_text = (
        "project: tp\n"
        "adapter:\n"
        "  type: http\n"
        "  url: https://x.test/eval\n"
        '  map: {answer: "$.answer"}\n'
        "  auth_header_env: TP_TOKEN\n"
        "dataset: d.jsonl\n"
        "metrics:\n"
        "  - name: exact_label_match\n"
        "    params: {label: category}\n"
    )
    cfg = load_config(_write(tmp_path, cfg_text))
    assert cfg.adapter.type == "http"
    assert cfg.adapter.url == "https://x.test/eval"


def test_n8n_adapter_parses(tmp_path: Path) -> None:
    cfg_text = (
        "project: tp\n"
        "adapter:\n"
        "  type: n8n_webhook\n"
        "  url: https://x.test/webhook\n"
        "dataset: d.jsonl\n"
        "metrics:\n"
        "  - name: exact_label_match\n"
        "    params: {label: category}\n"
    )
    cfg = load_config(_write(tmp_path, cfg_text))
    assert cfg.adapter.type == "n8n_webhook"
