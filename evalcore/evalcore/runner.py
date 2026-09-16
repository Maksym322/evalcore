"""Runner: orchestrate a full eval run (TechDesign §2.5).

Flow: build adapter + metrics -> load & filter dataset -> check preconditions ->
score every item under bounded concurrency, appending to an append-only journal
(`runs/{run_id}.jsonl`) -> aggregate into a RunReport.

The journal is written with ``allow_nan=True`` so NaN failure scores round-trip on
``--resume``; the public report.json goes through the reporter's NaN->null path instead.
"""

import hashlib
import json
import math
import os
import statistics
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import anyio
from pydantic import ValidationError

from evalcore.adapters.factory import build_adapter
from evalcore.config import RunConfig, SmokeSubset
from evalcore.metrics.base import build, check_preconditions, dataset_reference_fields
from evalcore.schema import Aggregate, DatasetItem, MetricResult, RunReport

# Output-side fields a TargetOutput can carry. The Python callable is opaque, so these are
# treated as available at precondition time and enforced per-item at runtime (metric -> NaN).
_OUTPUT_FIELDS = {
    "answer",
    "retrieved_context",
    "retrieved_ids",
    "metadata.latency_ms",
    "metadata.cost_usd",
}

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class DatasetError(Exception):
    """Raised when a dataset file is missing, empty, or has a malformed line."""


def new_ulid() -> str:
    """A 26-char Crockford base32 ULID: 48-bit ms timestamp + 80 random bits, time-sortable."""
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    value = (ts_ms << 80) | int.from_bytes(os.urandom(10), "big")
    out: list[str] = []
    for _ in range(26):
        value, rem = divmod(value, 32)
        out.append(_CROCKFORD[rem])
    return "".join(reversed(out))


def load_dataset(path: str | Path) -> list[DatasetItem]:
    """Load a JSONL dataset into DatasetItems (one object per line; blank lines skipped)."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise DatasetError(f"Dataset file not found: {p}") from e

    items: list[DatasetItem] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise DatasetError(f"{p}:{lineno}: invalid JSON ({e})") from e
        try:
            items.append(DatasetItem.model_validate(obj))
        except ValidationError as e:
            raise DatasetError(f"{p}:{lineno}: does not match DatasetItem schema:\n{e}") from e

    if not items:
        raise DatasetError(f"Dataset is empty: {p}")
    return items


def _apply_subset(items: list[DatasetItem], subset: SmokeSubset | None) -> list[DatasetItem]:
    if subset is None:
        return items
    if subset.tags:
        wanted = set(subset.tags)
        items = [it for it in items if wanted & set(it.tags)]
    return items[: subset.max_items]


def _available_fields(items: list[DatasetItem]) -> set[str]:
    return dataset_reference_fields(items) | _OUTPUT_FIELDS


def _config_hash(config: RunConfig) -> str:
    return hashlib.sha256(config.model_dump_json().encode("utf-8")).hexdigest()


def _append_journal(path: Path, item: DatasetItem, results: list[MetricResult]) -> None:
    record = {"item_id": item.id, "results": [r.model_dump(mode="json") for r in results]}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, allow_nan=True) + "\n")


def _read_journal(path: Path) -> tuple[set[str], list[MetricResult]]:
    done: set[str] = set()
    results: list[MetricResult] = []
    if not path.exists():
        return done, results
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        record = json.loads(line)  # json.loads restores NaN floats
        done.add(record["item_id"])
        results.extend(MetricResult.model_validate(r) for r in record["results"])
    return done, results


def _aggregate(results: list[MetricResult]) -> dict[str, Aggregate]:
    by_metric: dict[str, list[float]] = defaultdict(list)
    for r in results:
        by_metric[r.metric].append(r.score)

    aggregates: dict[str, Aggregate] = {}
    for name, scores in by_metric.items():
        finite = [s for s in scores if not math.isnan(s)]
        failures = len(scores) - len(finite)
        # count = # successful (finite) scores; failures counted separately, never averaged.
        mean = statistics.fmean(finite) if finite else 0.0
        p50 = statistics.median(finite) if finite else 0.0
        aggregates[name] = Aggregate(mean=mean, p50=p50, count=len(finite), failures=failures)
    return aggregates


async def run_eval(
    config: RunConfig,
    *,
    runs_dir: str | Path = "runs",
    resume: str | None = None,
) -> RunReport:
    """Execute an eval run and return a RunReport. Writes an append-only journal under runs_dir."""
    adapter = build_adapter(config.adapter)
    metrics = [build(m.name, m.params) for m in config.metrics]

    items = _apply_subset(load_dataset(config.dataset), config.run.smoke_subset)
    check_preconditions(metrics, _available_fields(items))

    run_id = resume or new_ulid()
    runs_path = Path(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)
    journal = runs_path / f"{run_id}.jsonl"

    done_ids, prior = _read_journal(journal) if resume else (set(), [])
    started_at = datetime.now(UTC)
    results: list[MetricResult] = list(prior)
    pending = [it for it in items if it.id not in done_ids]

    lock = anyio.Lock()
    limiter = anyio.CapacityLimiter(config.run.concurrency)

    async def process(item: DatasetItem) -> None:
        async with limiter:
            out = await adapter.respond(item)
            item_results = [await metric.score(item, out) for metric in metrics]
        async with lock:
            results.extend(item_results)
            _append_journal(journal, item, item_results)

    async with anyio.create_task_group() as tg:
        for item in pending:
            tg.start_soon(process, item)

    results.sort(key=lambda r: (r.item_id, r.metric))  # deterministic per_item ordering
    return RunReport(
        project=config.project,
        run_id=run_id,
        started_at=started_at,
        config_hash=_config_hash(config),
        judge_versions={},
        items=len(items),
        aggregates=_aggregate(results),
        per_item=results,
    )
