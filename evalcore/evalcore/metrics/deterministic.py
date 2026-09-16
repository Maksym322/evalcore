"""Built-in deterministic metrics (TechDesign §2.3). Registered on import.

Score conventions: normalized 0..1; NaN (via ``_fail``) means "uncomputable" and is
excluded from aggregates by the runner. ``json_schema_valid`` never fails — a bad answer
is a real 0.0.
"""

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from evalcore.metrics.base import Metric, register
from evalcore.schema import DatasetItem, MetricResult, TargetOutput


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer, got {value!r}")
    return value


def _dedup_topk(ids: list[str], k: int) -> list[str]:
    """First ``k`` unique ids, order preserved — duplicates cannot inflate a score."""
    seen: set[str] = set()
    top: list[str] = []
    for x in ids:
        if x not in seen:
            seen.add(x)
            top.append(x)
        if len(top) >= k:
            break
    return top


@register
class RetrievalRecallAtK(Metric):
    name = "retrieval_recall_at_k"
    kind = "deterministic"

    def __init__(self, k: int) -> None:
        super().__init__()
        self.k = _positive_int(k, "k")
        self.requires = {"retrieved_ids", "reference.relevant_ids"}

    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult:
        relevant = set(item.reference.relevant_ids)
        if not relevant:
            return self._fail(item.id, "reference.relevant_ids is empty")
        if out.retrieved_ids is None:
            return self._fail(item.id, "retrieved_ids not produced")
        top = _dedup_topk(out.retrieved_ids, self.k)
        hits = len(set(top) & relevant)
        return self._result(item.id, hits / len(relevant), hits=hits, relevant=len(relevant))


@register
class RetrievalPrecisionAtK(Metric):
    name = "retrieval_precision_at_k"
    kind = "deterministic"

    def __init__(self, k: int) -> None:
        super().__init__()
        self.k = _positive_int(k, "k")
        self.requires = {"retrieved_ids", "reference.relevant_ids"}

    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult:
        relevant = set(item.reference.relevant_ids)
        if not relevant:
            return self._fail(item.id, "reference.relevant_ids is empty")
        if out.retrieved_ids is None:
            return self._fail(item.id, "retrieved_ids not produced")
        top = _dedup_topk(out.retrieved_ids, self.k)
        if not top:
            return self._fail(item.id, "retrieved_ids is empty")
        hits = len(set(top) & relevant)
        # Denominator = min(k, unique retrieved) = len(top): don't understate when < k returned.
        return self._result(item.id, hits / len(top), hits=hits, considered=len(top))


@register
class ExactLabelMatch(Metric):
    name = "exact_label_match"
    kind = "deterministic"

    def __init__(self, label: str) -> None:
        super().__init__()
        if not isinstance(label, str) or not label:
            raise ValueError(f"label must be a non-empty string, got {label!r}")
        self.label = label
        self.requires = {"answer", f"reference.labels.{label}"}

    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult:
        if self.label not in item.reference.labels:
            return self._fail(item.id, f"reference.labels[{self.label!r}] missing")
        expected = str(item.reference.labels[self.label]).strip()
        got = out.answer.strip()
        return self._result(item.id, 1.0 if got == expected else 0.0, expected=expected, got=got)


@register
class JsonSchemaValid(Metric):
    name = "json_schema_valid"
    kind = "deterministic"

    def __init__(self, schema: dict[str, Any]) -> None:
        super().__init__()
        if not isinstance(schema, dict):
            raise ValueError("schema must be a mapping (a JSON Schema)")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as e:
            raise ValueError(f"invalid JSON schema: {e.message}") from e
        self._validator = Draft202012Validator(schema)
        self.requires = {"answer"}

    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult:
        # A malformed / non-conforming answer is a real 0.0 verdict, never a NaN failure.
        try:
            data = json.loads(out.answer)
        except (json.JSONDecodeError, TypeError):
            return self._result(item.id, 0.0, reason="answer is not valid JSON")
        errors = sorted(self._validator.iter_errors(data), key=str)
        if errors:
            return self._result(item.id, 0.0, reason=errors[0].message)
        return self._result(item.id, 1.0)


@register
class LatencyBudget(Metric):
    name = "latency_budget"
    kind = "deterministic"

    def __init__(self, max_ms: float) -> None:
        super().__init__()
        if isinstance(max_ms, bool) or not isinstance(max_ms, int | float) or max_ms <= 0:
            raise ValueError(f"max_ms must be a positive number, got {max_ms!r}")
        self.max_ms = float(max_ms)
        self.requires = {"metadata.latency_ms"}

    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult:
        latency = out.metadata.get("latency_ms")
        if not isinstance(latency, int | float) or isinstance(latency, bool):
            return self._fail(item.id, "metadata.latency_ms not produced")
        within = latency <= self.max_ms
        return self._result(item.id, 1.0 if within else 0.0, latency_ms=latency, budget=self.max_ms)
