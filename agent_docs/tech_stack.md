# Tech Stack & Tools

## Languages & Runtimes
- **Python 3.11+** — everything (framework + app)
- **YAML** — evalcore configs; **JSONL** — datasets and run journals

## EvalCore (package)
- **Pydantic v2** — all schemas (DatasetItem, TargetOutput, MetricResult, RunReport)
- **typer** — CLI (`init`, `run`, `compare`, `baseline`)
- **httpx** — HttpAdapter / N8nWebhookAdapter (timeouts, retries with backoff on 429/5xx)
- **anyio** — run sync callables in threads; bounded concurrency
- **jsonpath-ng** — response field mapping for HttpAdapter
- Judge calls via provider SDKs (Anthropic / OpenAI), pinned model per config, content-hash disk cache in `.evalcore_cache/`

## TicketPilot (app)
- **FastAPI** (async) + **uvicorn**
- **Postgres 16 + pgvector** (HNSW index) — vectors + full-text (tsvector) in one DB
- **SQLAlchemy async / asyncpg**, **alembic** for migrations
- **structlog** — JSON logs with request_id; **slowapi** — rate limiting
- **Langfuse** SDK — tracing per pipeline stage (no-op if env unset)
- **Docker + docker-compose** (api + postgres); deploy target: Fly.io or Railway

## Dev tooling
- **pytest** (+ pytest-asyncio), **ruff** (lint + format), **mypy --strict**, **pre-commit**
- **GitHub Actions** — lint+tests on PR; smoke eval on PR; full eval nightly (M5)

## Setup Commands

```bash
# evalcore
cd evalcore
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -e ".[dev]"
make test && make lint

# ticketpilot
cd ticketpilot
copy .env.example .env                              # fill keys
docker compose up -d                                # api + pgvector
make ingest                                         # build the index
make dev
```

## Environment Variables (never hardcode)
- `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` — LLM + judge
- `DATABASE_URL` — postgres
- `TICKETPILOT_EVAL_TOKEN` — auth for POST /tickets/eval
- `ACTIVE_STRATEGY`, `ACTIVE_EMBED_MODEL`, `TOP_K`, `CONF_THRESHOLD` — experiment knobs
- `LANGFUSE_*` — optional tracing

## Example: a Metric (the pattern to copy)

```python
# evalcore/metrics/deterministic.py
class RetrievalRecallAtK(Metric):
    """Did the target retrieve the chunks we know are relevant?"""
    name = "retrieval_recall_at_k"
    kind = "deterministic"
    requires = {"retrieved_ids", "reference.relevant_ids"}  # checked at config load

    def __init__(self, k: int = 5):
        self.k = k

    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult:
        relevant = set(item.reference.relevant_ids)
        got = set((out.retrieved_ids or [])[: self.k])
        score = len(relevant & got) / len(relevant) if relevant else 0.0
        return MetricResult(metric=self.name, item_id=item.id, score=score,
                            details={"hit": sorted(relevant & got)})
```

## Error Handling Pattern

```python
# Retry LLM/judge calls; NEVER let one bad item kill a run
try:
    result = await judge.call(prompt)          # retries 429/5xx internally
except JudgeError as e:
    return MetricResult(metric=self.name, item_id=item.id,
                        score=float("nan"), details={"judge_error": str(e)})
# runner: NaN results are counted as failures, excluded from means
```

## Naming Conventions
- Modules/functions/vars: `snake_case`; classes: `PascalCase`
- Chunk ids: `{doc_id}#{ordinal}@{strategy_version}` (e.g. `docs/auth.md#3@heading_v1`)
- Run ids: ULID; baselines: `eval/baselines/{branch}.json`
- Metric names in config = the `Metric.name` string, exactly
