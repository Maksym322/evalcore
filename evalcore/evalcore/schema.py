"""Core data types for EvalCore (TechDesign §2.1).

Design rule: everything the gate compares lives in a RunReport's ``aggregates``;
everything a human debugs lives in ``per_item``.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Reference(BaseModel):
    """Ground truth for a dataset item: expected answer and/or relevant chunk ids."""

    answer: str | None = None
    relevant_ids: list[str] = []
    # ``Any`` by design: label schema is open per project (e.g. category, priority).
    labels: dict[str, Any] = {}


class DatasetItem(BaseModel):
    """One evaluation case: an open-schema input plus its reference."""

    id: str
    # ``Any`` by design: input schema is project-defined (open by design).
    input: dict[str, Any]
    reference: Reference
    tags: list[str] = []


class TargetOutput(BaseModel):
    """What the system under test returned for a DatasetItem."""

    answer: str
    retrieved_context: list[str] | None = None
    retrieved_ids: list[str] | None = None
    # ``Any`` by design: free-form run metadata (latency_ms, cost_usd, trace_id, ...).
    metadata: dict[str, Any] = {}


class MetricResult(BaseModel):
    """A single metric's score for a single item (normalized 0..1 where possible)."""

    metric: str
    item_id: str
    score: float
    # ``Any`` by design: metric-specific debug payload (hits, judge_error, ...).
    details: dict[str, Any] = {}


class Aggregate(BaseModel):
    """Per-metric summary the gate compares. Failures are counted, never averaged as zeros."""

    mean: float
    p50: float
    count: int
    failures: int


class RunReport(BaseModel):
    """The full result of one eval run: gate-facing aggregates + per-item detail."""

    project: str
    run_id: str  # ulid
    started_at: datetime
    config_hash: str  # sha256 of resolved config
    judge_versions: dict[str, str]  # metric -> "provider/model@prompt_v"
    items: int
    aggregates: dict[str, Aggregate]  # metric -> mean/p50/count/failures
    per_item: list[MetricResult]
