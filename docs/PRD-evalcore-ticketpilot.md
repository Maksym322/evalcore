# PRD: EvalCore + TicketPilot

**Version:** 1.0 · **Owner:** Max · **Status:** Draft for build
**One-liner:** A universal, project-agnostic evaluation framework for LLM systems (EvalCore), shipped together with its first production consumer — a support-ticket resolution engine (TicketPilot) — proving the framework on a real workload.

---

## 1. Problem & Motivation

LLM systems fail silently: retrieval degrades, prompts regress, model upgrades change behavior. Most teams (and nearly all junior portfolios) ship without any way to measure this. Existing tools (RAGAS, DeepEval) provide metrics but not the surrounding system: dataset management, target adapters, baselines, regression gating in CI, cross-project reuse.

**Personal motivation (explicit):** the author maintains several LLM projects (ticket engine, voice agent, n8n automations, multi-tenant SaaS). Each needs quality measurement. Building evals per-project duplicates effort. EvalCore centralizes the machinery; each project supplies only an adapter, a dataset, and a config.

## 2. Goals

1. **G1 — Universality:** onboarding a new project to EvalCore requires ZERO changes to EvalCore itself. Only: (a) an adapter, (b) a dataset file, (c) a config file.
2. **G2 — Regression gating:** any consumer repo can block PR merges when quality drops below a committed baseline, via a reusable GitHub Action.
3. **G3 — Reference proof:** TicketPilot demonstrates the full loop end-to-end with published before/after numbers (chunking, embeddings, top-k experiments).
4. **G4 — Cost control:** a full eval run on an 80-item dataset costs < $1; smoke runs on PRs cost < $0.10.
5. **G5 — Reproducibility:** identical dataset + config + pinned models ⇒ deterministic metric deltas within a documented tolerance.

## 3. Non-Goals (v1)

- No web UI / dashboard for eval results (markdown + JSON reports only; UI is v2).
- No online/production evals (offline test sets only; Langfuse trace ingestion is v2).
- No fine-tuning, no training loops.
- No multi-turn conversation evals in v1 (single input → single output; multi-turn is v1.1).
- EvalCore does not host or run the target system — it only calls it.

## 4. Users & Use Cases

| User | Use case |
|---|---|
| Max (primary) | Evaluate TicketPilot, Voxora flows, voice agent, n8n workflows with one shared toolkit |
| Hiring manager / recruiter | Open the repo, see metrics tables, CI gates, and a live demo — verify engineering maturity |
| OSS user (secondary) | `pip install evalcore`, write an adapter, eval their own LLM app |

**Core scenario (must stay this simple):**
```bash
pip install evalcore
evalcore init                     # scaffolds evalcore.yaml + datasets/ + adapters/
# write adapters/my_project.py (≤ 30 lines)
# fill datasets/golden.jsonl
evalcore run --config evalcore.yaml
evalcore compare --baseline baselines/main.json   # exit code 1 on regression
```

## 5. System Architecture

Two repositories:

```
evalcore/                      # universal framework (PyPI package)
  evalcore/
    adapters/    # Target protocol + built-ins: python, http, n8n_webhook
    datasets/    # loader, JSONL schema validation
    metrics/     # registry + built-ins (deterministic + LLM-judge)
    judge/       # judge client: pinned model, caching, retry
    runner.py    # orchestrates: dataset -> target -> metrics -> report
    gate.py      # baseline compare, thresholds, exit codes
    reporters/   # markdown, json, github-comment
    cli.py
  action/        # reusable GitHub Action (composite) wrapping the CLI
  tests/

ticketpilot/                   # reference consumer (FastAPI app)
  app/           # ingestion, classification, retrieval, generation, escalation
  eval/
    adapters/ticketpilot.py
    datasets/golden.jsonl      # 60–80 hand-verified items
    evalcore.yaml
    baselines/main.json
  .github/workflows/eval.yml   # uses evalcore action
```

### 5.1 The universality contract (heart of the product)

**Adapter protocol.** A target is anything implementing:

```python
class Target(Protocol):
    def respond(self, item: DatasetItem) -> TargetOutput: ...

@dataclass
class TargetOutput:
    answer: str
    retrieved_context: list[str] | None = None   # enables faithfulness/recall metrics
    metadata: dict = field(default_factory=dict) # latency, cost, trace_id, anything
```

Built-in adapters (v1):
1. **PythonAdapter** — wraps a local callable (in-process, fastest).
2. **HttpAdapter** — POSTs to any endpoint; response field mapping declared in config (JSONPath). Covers TicketPilot, Voxora, the voice agent's text layer.
3. **N8nWebhookAdapter** — HttpAdapter specialization with n8n auth/response conventions. Covers all n8n workflows without modifying them.

**Dataset schema** (JSONL, one line per item):
```json
{
  "id": "str",
  "input": {"question": "str", "...": "any project-specific fields"},
  "reference": {"answer": "str|null", "relevant_ids": ["doc paths or chunk ids"], "labels": {"any": "ground truth"}},
  "tags": ["howto", "edge-case"]
}
```
`input` and `reference.labels` are intentionally open dicts — schema flexibility is what makes one format serve tickets, translations, and extraction tasks alike.

**Config (`evalcore.yaml`)** — the per-project "model" the user creates:
```yaml
project: ticketpilot
adapter:
  type: http
  url: https://ticketpilot.fly.dev/tickets/eval
  map: {answer: "$.answer", retrieved_context: "$.citations[*].text"}
dataset: eval/datasets/golden.jsonl
metrics:
  - name: retrieval_recall_at_k    # deterministic
    params: {k: 5}
  - name: retrieval_precision_at_k
    params: {k: 5}
  - name: faithfulness             # LLM-judge
    judge: {model: "claude-sonnet-4-6", prompt: default}
  - name: answer_relevance
    judge: {model: "claude-sonnet-4-6", prompt: prompts/relevance_uk.md}  # custom judge per project
  - name: exact_label_match        # for classification-type projects
    params: {label: category}
gate:
  baseline: eval/baselines/main.json
  rules:
    - {metric: faithfulness, max_drop_pct: 5}
    - {metric: retrieval_recall_at_k, max_drop_pct: 5}
run:
  concurrency: 8
  smoke_subset: {tags: [smoke], max_items: 10}
  seed: 42
  temperature: 0
```

### 5.2 Metric plugin system

- Registry with entry-point discovery: third parties (or Max's other repos) register custom metrics via `pyproject.toml` entry points — no core changes (satisfies G1).
- Two metric classes:
  - **Deterministic** (free, fast): precision@k, recall@k, exact match, regex/schema validity, latency/cost from metadata.
  - **LLM-judge** (costed, cached): faithfulness, relevance, custom-prompt metrics. Judge calls are content-hashed and cached to disk (`.evalcore_cache/`) so re-runs on unchanged items are free (supports G4).
- Judge model + prompt version are pinned and recorded in every report (supports G5).

### 5.3 Regression gate & CI

- `evalcore compare` diffs a run against a committed baseline JSON; applies `gate.rules`; non-zero exit on violation.
- Reusable composite GitHub Action: consumer adds ~5 lines of YAML. Modes:
  - **PR (smoke):** tagged 10-item subset, temperature 0, judge cache warm ⇒ fast + cheap.
  - **Nightly (full):** whole dataset, posts markdown summary as a commit comment, updates trend file.
- Baseline updates are explicit (`evalcore baseline update`) and reviewed like code.

## 6. Reference Consumer: TicketPilot (functional requirements)

**FR-T1 Ingestion:** clone target OSS project docs (markdown) + pull 500–1000 closed GitHub issues with accepted maintainer answers. `make ingest` fully rebuilds.
**FR-T2 Chunking:** pluggable strategies (fixed-size 512/50; heading-aware markdown), version recorded per chunk.
**FR-T3 Indexing:** Postgres + pgvector; embedding model configurable (compare `text-embedding-3-small` vs one open model).
**FR-T4 Classification:** structured output `{category, product_area, confidence}` (Pydantic-validated).
**FR-T5 Retrieval:** hybrid vector + full-text with reciprocal rank fusion; top-k configurable; retrieved chunk IDs logged per request.
**FR-T6 Generation:** grounded answer with inline citations; must abstain when context is insufficient (`grounded: false`).
**FR-T7 Escalation:** low confidence OR ungrounded OR weak retrieval ⇒ `escalated` status.
**FR-T8 API:** `POST /tickets`, `GET /tickets/{id}`, `POST /tickets/{id}/resolve`, plus `POST /tickets/eval` (synchronous variant for the HttpAdapter).
**FR-T9 Observability:** structured JSON logs with request ID; Langfuse tracing; `/metrics` (latency percentiles, escalation rate, token spend); rate limiting.
**FR-T10 Experiments:** 2 chunkers × 2 embedders × top-k ∈ {3,5,8} grid, all runs via EvalCore, results table in README including negative results.
**FR-T11 Post-mortem:** `POSTMORTEM.md` documenting one real failure encountered during the build.

## 7. Non-Functional Requirements

- **Performance:** full 80-item eval completes < 10 min at concurrency 8; TicketPilot p95 answer latency < 8 s.
- **Cost:** see G4; per-request token cost logged.
- **Reliability:** judge calls retried with backoff; rate-limit-aware; partial run results persisted (resumable).
- **Security:** API keys via env only; no secrets in reports; eval endpoint auth-protected in production.
- **DX:** `evalcore init` to first successful run in < 15 minutes for a new project.
- **Docs:** README quickstart + "Onboard your project in 3 files" guide + adapter cookbook (python/http/n8n examples).

## 8. Milestones

| # | Scope | Duration | Exit criteria |
|---|---|---|---|
| M1 | EvalCore skeleton: dataset loader, PythonAdapter, deterministic metrics, runner, JSON/MD reports | 1 wk | eval a toy function end-to-end |
| M2 | Judge metrics + caching + pinning; HttpAdapter; gate + compare | 1 wk | regression gate flips exit codes correctly on synthetic data |
| M3 | TicketPilot core (FR-T1…T8) | 1.5 wk | curl demo of full ticket flow via docker compose |
| M4 | Golden dataset (60–80 verified) + experiment grid + baseline | 1 wk | README results table with real numbers |
| M5 | GitHub Action, CI smoke + nightly, deploy, observability, post-mortem | 1 wk | live URL; a merged PR showing gate in action |
| M6 | N8nWebhookAdapter + onboard ONE existing project (Voxora flow or n8n workflow) | 3–4 d | second project evaluated with zero core changes — G1 proven |

M6 is the universality proof. It is in scope, not "future work," because it is the claim the whole product makes.

## 9. Success Metrics (for the product AND the portfolio)

- G1 verified: second project onboarded with ≤ 3 new files, 0 core edits.
- ≥ 1 PR in ticketpilot history blocked or flagged by the gate, then fixed (visible in CI logs).
- README experiment table with ≥ 12 runs incl. at least one honestly-reported null/negative result.
- EvalCore published to PyPI; TicketPilot deployed with public URL.
- Full-run cost < $1 (receipt in docs).

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LLM-judge flakiness makes the gate noisy | temperature 0, pinned judge, %-drop thresholds instead of absolute values, smoke set curated for stability |
| Judge cost creep during iteration | content-hash cache; smoke subset on PRs; full runs nightly only |
| Over-abstraction of the core ("framework disease") | rule: no abstraction until two consumers need it; TicketPilot + M6 project are the only drivers in v1 |
| Golden dataset takes longer than expected | timebox: 50 verified items is the floor, 80 the target; quality over count |
| Scope creep into dashboards/multi-agent | Non-goals section is binding for v1 |

## 11. Future Work (v2 backlog)

Multi-turn conversation evals · Langfuse trace ingestion (online evals) · results web dashboard (Next.js — doubles as the JS/TS portfolio piece) · pairwise A/B judge mode · dataset synthesis assistant (LLM-generated candidates, human-verified) · voice-specific metrics (latency budget assertions) for the voice agent project.
