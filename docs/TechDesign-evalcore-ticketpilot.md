# Technical Design: EvalCore + TicketPilot

**Version:** 1.0 · **Based on:** PRD v1.0 · **Status:** Ready for implementation
**Stack:** Python 3.11+, Pydantic v2, FastAPI, Postgres 16 + pgvector, Docker, GitHub Actions. LLMs via provider SDKs (OpenAI / Anthropic), judge model pinned per config.

---

## 1. Repository Layout

### 1.1 `evalcore` (PyPI package)

```
evalcore/
├── pyproject.toml               # entry points: evalcore.metrics, evalcore.adapters
├── evalcore/
│   ├── __init__.py
│   ├── cli.py                   # typer CLI: init, run, compare, baseline
│   ├── config.py                # yaml -> pydantic RunConfig
│   ├── schema.py                # DatasetItem, TargetOutput, MetricResult, RunReport
│   ├── runner.py                # orchestration, concurrency, resume
│   ├── gate.py                  # baseline compare + rules
│   ├── adapters/
│   │   ├── base.py              # Target protocol
│   │   ├── python_adapter.py
│   │   ├── http_adapter.py
│   │   └── n8n_adapter.py
│   ├── metrics/
│   │   ├── base.py              # Metric ABC + registry
│   │   ├── deterministic.py     # recall@k, precision@k, exact_match, schema_valid, latency
│   │   └── judged.py            # faithfulness, relevance, custom-prompt
│   ├── judge/
│   │   ├── client.py            # provider-agnostic judge caller
│   │   └── cache.py             # content-hash disk cache
│   └── reporters/
│       ├── json_reporter.py
│       ├── markdown_reporter.py
│       └── github_comment.py
├── action/                      # composite GitHub Action
│   └── action.yml
└── tests/
```

### 1.2 `ticketpilot` (reference consumer)

```
ticketpilot/
├── docker-compose.yml           # api + postgres(pgvector) + (optional) langfuse
├── Makefile                     # ingest, dev, eval, eval-smoke, baseline
├── app/
│   ├── main.py                  # FastAPI app factory, middleware, routes
│   ├── settings.py              # pydantic-settings, env-driven
│   ├── db.py                    # asyncpg pool / SQLAlchemy async
│   ├── ingestion/
│   │   ├── docs_loader.py       # git clone + md parse
│   │   ├── issues_loader.py     # GitHub API pull
│   │   ├── chunkers.py          # FixedSizeChunker, HeadingAwareChunker
│   │   └── embedder.py          # provider-configurable
│   ├── pipeline/
│   │   ├── classify.py
│   │   ├── retrieve.py          # hybrid + RRF
│   │   ├── generate.py
│   │   └── escalate.py
│   ├── api/
│   │   ├── routes_tickets.py
│   │   └── routes_meta.py       # /health /metrics
│   └── observability/
│       ├── logging.py           # structlog JSON, request_id
│       └── tracing.py           # langfuse wrapper (no-op if unset)
├── eval/
│   ├── adapters/ticketpilot.py
│   ├── datasets/golden.jsonl
│   ├── evalcore.yaml
│   └── baselines/main.json
└── .github/workflows/eval.yml
```

---

## 2. EvalCore Design

### 2.1 Core data types (`schema.py`)

```python
class DatasetItem(BaseModel):
    id: str
    input: dict[str, Any]                 # open schema by design
    reference: Reference
    tags: list[str] = []

class Reference(BaseModel):
    answer: str | None = None
    relevant_ids: list[str] = []
    labels: dict[str, Any] = {}

class TargetOutput(BaseModel):
    answer: str
    retrieved_context: list[str] | None = None
    retrieved_ids: list[str] | None = None
    metadata: dict[str, Any] = {}          # latency_ms, cost_usd, trace_id...

class MetricResult(BaseModel):
    metric: str
    item_id: str
    score: float                           # normalized 0..1 where possible
    details: dict[str, Any] = {}

class RunReport(BaseModel):
    project: str
    run_id: str                            # ulid
    started_at: datetime
    config_hash: str                       # sha256 of resolved config
    judge_versions: dict[str, str]         # metric -> "provider/model@prompt_v"
    items: int
    aggregates: dict[str, Aggregate]       # metric -> mean/p50/count/failures
    per_item: list[MetricResult]
```

Design rule: **everything the gate compares lives in `aggregates`; everything a human debugs lives in `per_item`.**

### 2.2 Adapter layer

```python
class Target(Protocol):
    async def respond(self, item: DatasetItem) -> TargetOutput: ...
```

- **PythonAdapter**: dotted-path import from config (`adapter.callable: "my_pkg.eval:answer"`). Wraps sync callables via `anyio.to_thread`.
- **HttpAdapter**: 
  - Request: `POST url` with `{"input": item.input, "id": item.id}` (template overridable).
  - Response mapping via JSONPath in config (`map: {answer: "$.answer", ...}`).
  - Timeout, retries (3, exp backoff, retry on 429/5xx), auth header from env var name (never the value in config).
  - Measures wall-clock latency → `metadata.latency_ms` automatically.
- **N8nWebhookAdapter(HttpAdapter)**: presets — n8n webhook auth header convention, unwrap of n8n's array-wrapped response, sensible default map.

**Extension:** third-party adapters register via entry point group `evalcore.adapters`; config `adapter.type` resolves through the registry first, then built-ins.

### 2.3 Metric layer

```python
class Metric(ABC):
    name: str
    requires: set[str] = set()   # e.g. {"retrieved_ids"} or {"reference.answer"}
    kind: Literal["deterministic", "judged"]

    @abstractmethod
    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult: ...
```

- Registry: built-ins + entry point group `evalcore.metrics`. Config selects by `name`, passes `params`.
- **Precondition check at config-load time**: if a selected metric `requires` fields the adapter/dataset can't provide, fail fast with a clear message (prevents silent zero-scores).

Built-in deterministic: `retrieval_recall_at_k`, `retrieval_precision_at_k` (on `retrieved_ids` vs `reference.relevant_ids`), `exact_label_match` (path into `reference.labels` vs parsed answer field), `json_schema_valid` (answer must parse against provided schema), `latency_budget` (pass/fail vs ms threshold — this is the voice-project hook).

Built-in judged: `faithfulness` (answer vs retrieved_context), `answer_relevance` (answer vs input.question), `custom_judged` (user-supplied prompt file with `{input}/{answer}/{reference}` slots — this is the per-project "special model" mechanism).

### 2.4 Judge client & cache

- Single `JudgeClient` used by all judged metrics. Config pins `{provider, model, prompt_version}`; the resolved triple is recorded in `RunReport.judge_versions`.
- Judge prompts return **strict JSON** (`{"score": 0..1, "reason": str}`); parse failures retried once with a repair instruction, then recorded as `details.judge_error` and excluded from aggregates (counted in `failures`).
- **Cache**: key = `sha256(model + prompt_version + item_id + answer + context_digest)` → `.evalcore_cache/{key}.json`. Cache hit = zero cost. Cache is safe because temperature=0 and inputs are content-addressed.
- Concurrency: judge calls behind a semaphore (config `run.concurrency`), token-bucket rate limiter, 429-aware backoff.

### 2.5 Runner

Flow: load config → validate metric preconditions → load dataset (optionally filter by tags/subset) → for each item (bounded concurrency): adapter.respond → run metrics → append to on-disk journal (`runs/{run_id}.jsonl`) → aggregate → write reports.

- **Resumability**: journal is append-only; `--resume {run_id}` skips completed items. Protects long runs from rate-limit deaths.
- **Determinism knobs**: `seed`, `temperature: 0` passed to adapters via header/param convention (`X-Eval-Run: 1`, documented; consumers may use it to force temp 0).
- Aggregation: mean + p50 per metric; failures counted separately, never averaged in as zeros.

### 2.6 Gate (`compare`)

- Input: current `RunReport` + baseline JSON (a frozen `aggregates` snapshot + config_hash + judge_versions).
- Guards before comparing: warn (or fail with `--strict`) if `config_hash` or judge versions differ from baseline — otherwise deltas are meaningless.
- Rules from config: `max_drop_pct` (relative) and optional `min_value` (absolute floor). Any violation ⇒ exit 1 and a table of violations to stdout/report.
- `baseline update` writes new baseline from a given run; intended to be code-reviewed.

### 2.7 GitHub Action (`action/action.yml`)

Composite action, inputs: `config`, `mode: smoke|full`, `baseline`, `api-key-env`. Steps: setup-python → `pip install evalcore` → `evalcore run` (smoke subset if mode=smoke) → `evalcore compare` → on failure, post markdown violations table as PR comment (uses `github_comment` reporter). Cache action restores `.evalcore_cache/`.

Consumer YAML (~the whole integration):
```yaml
- uses: max/evalcore-action@v1
  with: {config: eval/evalcore.yaml, mode: smoke, baseline: eval/baselines/main.json}
  env: {ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}}
```

---

## 3. TicketPilot Design

### 3.1 Database schema (Postgres + pgvector)

```sql
CREATE TABLE documents (
  id TEXT PRIMARY KEY,            -- repo-relative path
  title TEXT, source_sha TEXT, updated_at TIMESTAMPTZ
);

CREATE TABLE chunks (
  id TEXT PRIMARY KEY,            -- {doc_id}#{ordinal}@{strategy_version}
  doc_id TEXT REFERENCES documents(id),
  heading_path TEXT,              -- "Getting Started > Auth"
  strategy TEXT NOT NULL,         -- 'fixed_512_50' | 'heading_v1'
  embed_model TEXT NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1536),
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks USING gin (tsv);

CREATE TABLE tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT, body TEXT NOT NULL,
  category TEXT, product_area TEXT, confidence REAL,
  status TEXT NOT NULL DEFAULT 'new',   -- new|answered|escalated|resolved
  answer JSONB,                          -- {text, citations[], grounded}
  request_id TEXT, created_at TIMESTAMPTZ DEFAULT now()
);
```

Multiple `(strategy, embed_model)` variants coexist in `chunks`; the active pair is selected by settings — this is what makes the experiment grid a config sweep, not a re-deploy.

### 3.2 Request pipeline (sequence)

```
POST /tickets {title, body}
  → request_id middleware (ulid) → structlog bind
  1. classify.py
     - LLM call, response_format=json_schema (Pydantic TicketClass)
     - on parse failure: one repair retry → else category='other', confidence=0
  2. retrieve.py
     - q_embedding = embed(body)
     - vector top-20 (cosine) WHERE strategy=S AND embed_model=E
     - fulltext top-20 (ts_rank)
     - RRF merge (k=60) → top_k final (settings.TOP_K)
     - log retrieved ids + scores
  3. generate.py
     - prompt: system rules + numbered context blocks + question
     - must cite as [n]; must output {"answer","used_context":[n...],"grounded":bool}
     - grounded=false ⇒ skip to escalate
  4. escalate.py
     - escalate if: confidence < 0.6 OR grounded=false OR max_rrf_score < θ
     - else status=answered
  → persist ticket, return DTO
```

`POST /tickets/eval` runs the same pipeline synchronously and returns `{answer, retrieved_context, retrieved_ids, metadata:{latency_ms, tokens, cost_usd}}` — shaped exactly for EvalCore's HttpAdapter map. Auth: static bearer from env; rate-limited separately.

### 3.3 Ingestion

- `docs_loader`: shallow clone target repo → walk `docs/**/*.md` → strip frontmatter → emit `Document`.
- `issues_loader`: GitHub REST, closed issues with label/heuristic "question" + an accepted-looking maintainer reply (author_association in {MEMBER, OWNER, COLLABORATOR}); store to `raw_issues.jsonl` (this file later seeds the golden dataset).
- `chunkers`: both implement `chunk(doc) -> list[Chunk]`; strategy version string is part of chunk id ⇒ cache-safe re-ingestion.
- `make ingest STRATEGY=heading_v1 EMBED=text-embedding-3-small` — idempotent per (strategy, model) pair.

### 3.4 Observability

- structlog JSON to stdout; every pipeline stage logs `{request_id, stage, duration_ms, ...}`.
- Langfuse spans per stage (classify/retrieve/generate) with token+cost attrs; disabled cleanly when env unset.
- `/metrics`: Prometheus text — request count, latency histogram, escalation_rate, tokens_total, cost_usd_total.
- Rate limiting: slowapi, per-IP on public routes, per-token on /eval.

### 3.5 Configuration & deployment

- All knobs via `pydantic-settings` env: `ACTIVE_STRATEGY`, `ACTIVE_EMBED_MODEL`, `TOP_K`, `CONF_THRESHOLD`, `LLM_MODEL`, keys.
- Docker: multi-stage build, non-root user. `docker-compose` for local (api + pgvector). Prod: Fly.io/Railway, Postgres managed addon, secrets via platform.
- Migrations: alembic, run on release phase.

---

## 4. Eval Integration (the universality proof in practice)

`ticketpilot/eval/evalcore.yaml` (abridged):
```yaml
project: ticketpilot
adapter:
  type: http
  url: ${TICKETPILOT_URL}/tickets/eval
  auth_header_env: TICKETPILOT_EVAL_TOKEN
  map:
    answer: "$.answer"
    retrieved_context: "$.retrieved_context[*]"
    retrieved_ids: "$.retrieved_ids[*]"
metrics:
  - {name: retrieval_recall_at_k, params: {k: 5}}
  - {name: retrieval_precision_at_k, params: {k: 5}}
  - {name: faithfulness, judge: {model: claude-sonnet-4-6, prompt: default}}
  - {name: answer_relevance, judge: {model: claude-sonnet-4-6, prompt: default}}
gate:
  baseline: eval/baselines/main.json
  rules:
    - {metric: faithfulness, max_drop_pct: 5, min_value: 0.75}
    - {metric: retrieval_recall_at_k, max_drop_pct: 5}
run: {concurrency: 8, seed: 42, smoke_subset: {tags: [smoke], max_items: 10}}
```

Second consumer (M6, e.g. an n8n workflow) = `adapter.type: n8n_webhook` + its own dataset + metric selection. Zero package changes — that diff IS the portfolio claim.

### Experiment grid execution
```
for S in fixed_512_50 heading_v1; for E in small openM; for K in 3 5 8:
  restart api with env → evalcore run --out runs/{S}_{E}_{K}.json
evalcore report-matrix runs/ → docs/experiments.md   (v1.1 helper; v1 = small script)
```

---

## 5. Error Handling Matrix (selected)

| Failure | Layer | Behavior |
|---|---|---|
| LLM 429/5xx | pipeline & judge | backoff retry ×3; then: pipeline ⇒ escalate ticket; judge ⇒ record failure, exclude from mean |
| Judge returns non-JSON | judge | one repair retry → judge_error in details |
| Adapter timeout | evalcore | item marked failed, run continues; failures reported |
| Config selects metric lacking required fields | evalcore | fail at load with actionable message |
| Baseline vs run config/judge mismatch | gate | warn; `--strict` ⇒ fail |
| Re-ingest same (strategy, model) | ingestion | idempotent upsert by chunk id |

## 6. Testing Strategy

- **evalcore**: unit tests per metric (golden fixtures), adapter tests against a local httpx MockTransport, gate rule table tests, cache hit/miss tests. A `FakeJudge` (deterministic scorer) makes the whole runner testable offline — CI for evalcore itself never calls a real LLM.
- **ticketpilot**: pipeline unit tests with recorded LLM fixtures (vcr-style), retrieval tests on a seeded mini-corpus (known relevant ids), API tests via httpx AsyncClient.
- **Integration**: docker-compose e2e in CI nightly: ingest mini-corpus → 5 tickets → smoke eval → gate.

## 7. Open Questions / Deferred Decisions

1. RRF vs weighted-score hybrid — start RRF (k=60), revisit only if recall@5 experiments say so.
2. Answer-field parsing for `exact_label_match` — v1: JSONPath into answer if it's JSON; free-text label extraction deferred.
3. Multi-turn schema — deliberately out (PRD non-goal); revisit shape only after voice project onboarding.
4. PyPI name availability — check `evalcore`; fallback candidates: `evalgate`, `goldenrun`.
