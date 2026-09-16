"""Metric contract, registry, and config-load precondition check (code_patterns §2).

A Metric maps (DatasetItem, TargetOutput) -> MetricResult with a normalized 0..1 score.
When a metric genuinely cannot compute (missing inputs, empty ground truth), it returns
score = NaN with a ``details["error"]`` note; the runner counts NaN under ``failures`` and
never averages it as a zero. ``json_schema_valid`` is the deliberate exception: a bad answer
is a real 0.0 verdict, not a failure.
"""

import math
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Literal

from evalcore.config import ConfigError
from evalcore.judge.base import Judge
from evalcore.schema import DatasetItem, MetricResult, TargetOutput

FAILURE_SCORE = math.nan


def is_failure(score: float) -> bool:
    """A metric result counts as a failure (excluded from means) iff its score is NaN."""
    return math.isnan(score)


class Metric(ABC):
    """Base class for all metrics. Subclasses set ``name``/``kind`` and populate ``requires``."""

    name: ClassVar[str]
    kind: ClassVar[Literal["deterministic", "judged"]]

    def __init__(self) -> None:
        # Fields the metric needs from the adapter output and/or dataset reference.
        # Reference-side keys are dotted ("reference.relevant_ids"); output-side are bare.
        self.requires: set[str] = set()

    @abstractmethod
    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult:
        """Score a single item. Return score=NaN (via ``_fail``) when uncomputable."""

    def _result(self, item_id: str, score: float, **details: Any) -> MetricResult:
        return MetricResult(metric=self.name, item_id=item_id, score=score, details=details)

    def _fail(self, item_id: str, error: str, **details: Any) -> MetricResult:
        return self._result(item_id, FAILURE_SCORE, error=error, **details)


_REGISTRY: dict[str, type[Metric]] = {}


def register(cls: type[Metric]) -> type[Metric]:
    """Class decorator: add a metric to the built-in registry, keyed by ``cls.name``."""
    if cls.name in _REGISTRY:
        raise ValueError(f"Duplicate metric name {cls.name!r} in registry")
    _REGISTRY[cls.name] = cls
    return cls


def build(name: str, params: dict[str, Any], *, judge: Judge | None = None) -> Metric:
    """Instantiate a registered metric by name, passing ``params`` as kwargs.

    Judged metrics also receive ``judge``; building one without a judge is a ConfigError.
    Fails loudly (ConfigError) on an unknown name or bad params — before any adapter call.
    """
    if name not in _REGISTRY:
        raise ConfigError(f"Unknown metric {name!r}. Available: {sorted(_REGISTRY)}")
    cls = _REGISTRY[name]
    try:
        if cls.kind == "judged":
            if judge is None:
                raise ConfigError(f"Metric {name!r} is judged and requires a judge")
            # Merge into a dict so mypy doesn't check `judge=` against Metric.__init__.
            return cls(**{"judge": judge, **params})
        return cls(**params)
    except (TypeError, ValueError) as e:
        raise ConfigError(f"Invalid params for metric {name!r}: {e}") from e


def available_metrics() -> list[str]:
    return sorted(_REGISTRY)


def dataset_reference_fields(items: list[DatasetItem]) -> set[str]:
    """Reference-side fields the dataset can supply, ALL-items semantics.

    A field counts as available only if EVERY item populates it — conservative, so a
    metric can't silently score zeros on the items that happen to lack ground truth.
    """
    if not items:
        return set()

    def populated(item: DatasetItem) -> set[str]:
        fields: set[str] = set()
        ref = item.reference
        if ref.answer is not None:
            fields.add("reference.answer")
        if ref.relevant_ids:
            fields.add("reference.relevant_ids")
        for key in ref.labels:
            fields.add(f"reference.labels.{key}")
        return fields

    common = populated(items[0])
    for item in items[1:]:
        common &= populated(item)
    return common


def check_preconditions(metrics: list[Metric], available: set[str]) -> None:
    """Abort (ConfigError) if any metric requires a field the run cannot produce.

    ``available`` = adapter-producible output fields ∪ dataset_reference_fields(...).
    Runs at config-load, before any adapter/API call, to prevent silent zero-scores.
    """
    problems: list[str] = []
    for metric in metrics:
        missing = sorted(metric.requires - available)
        if missing:
            problems.append(f"  - {metric.name}: needs {missing}")
    if problems:
        raise ConfigError(
            "Metric preconditions not met (fields not producible by adapter+dataset):\n"
            + "\n".join(problems)
            + f"\nAvailable fields: {sorted(available)}"
        )
