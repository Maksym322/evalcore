# Testing Strategy

- **Unit tests:** pytest + pytest-asyncio
- **Lint/type gates:** ruff (lint + format) and mypy --strict — part of every verification loop
- **Pre-commit hooks:** ruff, ruff-format, mypy, pytest (fast subset). Hooks must pass before commits; never bypass without asking.
- **Verification loop:** after EVERY feature → `make test && make lint`; fix failures before moving on; then walk REVIEW-CHECKLIST.md.

## The golden rule
**evalcore's own test suite makes ZERO real LLM calls.** A test suite that costs money per run is a test suite nobody runs.

- **FakeJudge:** deterministic scorer implementing the judge interface (e.g. scores by keyword overlap). All judged-metric and runner tests use it.
- **HTTP tests:** `httpx.MockTransport` for HttpAdapter/N8nWebhookAdapter — assert retries on 429/5xx, timeout handling, JSONPath mapping, auth header from env.

## What to test where

### evalcore (unit)
- Each metric against golden fixtures (known inputs → exact expected scores), including edge cases: empty relevant_ids, k > returned items, NaN handling
- Config loading: unknown metric name fails with available list; metric precondition check aborts before any adapter call
- Gate rule table: max_drop_pct and min_value combinations → correct exit codes; config-hash mismatch → warn / `--strict` fail
- Judge cache: hit/miss by content hash; cache invalidates when model or prompt_version changes
- Runner: journal written per item; `--resume` skips completed; failures counted, never averaged as zeros

### ticketpilot (unit + integration)
- Pipeline stages with recorded LLM fixtures (vcr-style): classification parse-repair path, generation abstention path, escalation thresholds
- Retrieval on a seeded mini-corpus with KNOWN relevant chunk ids → assert recall (deterministic, no LLM)
- API via httpx AsyncClient: happy path, rate limit response, /tickets/eval auth required
- Ingestion idempotency: re-running same (strategy, embed_model) does not duplicate chunks

### E2E (nightly CI, M5)
docker compose up → ingest mini-corpus → submit 5 tickets → smoke eval (10 tagged items, temperature 0) → gate compare. Real LLM calls allowed HERE only, budget-capped.

## Manual checks (vibe-coder friendly)
- `curl` the demo command from README — does a real ticket flow work end to end?
- Open the markdown eval report — do the numbers and failure counts make sense?
- Kill the run mid-way, `--resume` — does it continue from the journal?
