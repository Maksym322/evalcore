# PROMPTS.md — Copy-Paste Prompt Playbook

> How to use: paste one prompt at a time into Claude Code (or Gemini CLI) from the project root.
> The agent is configured to **propose a plan and wait** before coding. Read the plan, then reply
> `approved` (or ask for a change). After it finishes, it should run `make test && make lint` and
> update `MEMORY.md`. If it forgets, use the **Verify** prompt at the bottom.
>
> Golden loop for EVERY task: **plan → you approve → code → test+lint → update MEMORY.md → commit.**

---

## SESSION START (paste at the beginning of every new session)

```
Read CLAUDE.md, AGENTS.md, and MEMORY.md. Confirm the current phase and the next
unchecked task in one short paragraph. Do not write code yet.
```

---

## MILESTONE 1 — EvalCore skeleton

**M1.1 — Scaffold the package**
```
Start M1 task 1. Propose a plan to scaffold the `evalcore/` Python package:
pyproject.toml (typer, pydantic v2, pyyaml, httpx, anyio, jsonpath-ng; dev: pytest,
pytest-asyncio, ruff, mypy), the package layout from docs/TechDesign §1.1, a Makefile
with dev/test/lint targets, .gitignore, .pre-commit-config.yaml, and an empty pytest
setup. Follow agent_docs/tech_stack.md. Wait for my approval before creating files.
```

**M1.2 — Core schemas**
```
Implement evalcore/schema.py: DatasetItem, Reference, TargetOutput, MetricResult,
RunReport (+ Aggregate) as Pydantic v2 models exactly as described in
docs/TechDesign §2.1. Add unit tests that round-trip each model. Plan first.
```

**M1.3 — Config loader**
```
Implement evalcore/config.py: parse evalcore.yaml into a typed RunConfig
(adapter, dataset, metrics[], gate, run). Validate and fail with a clear message on
unknown keys. Add tests for a valid config and for common mistakes. Plan first.
```

**M1.4 — Python adapter + Target protocol**
```
Implement evalcore/adapters/base.py (Target protocol) and python_adapter.py
(imports a dotted-path callable from config, wraps sync callables via anyio, measures
latency into metadata). Follow the adapter pattern in agent_docs/code_patterns.md.
Test with a fake in-memory callable. Plan first.
```

**M1.5 — Deterministic metrics + registry**
```
Implement evalcore/metrics/base.py (Metric ABC + register/build registry) and
deterministic.py with: retrieval_recall_at_k, retrieval_precision_at_k,
exact_label_match, json_schema_valid, latency_budget. Add the config-load precondition
check: every metric.requires field must be producible, else abort before any adapter
call. Unit-test each metric with golden fixtures incl. edge cases (empty relevant_ids,
k > items). Plan first.
```

**M1.6 — Runner**
```
Implement evalcore/runner.py: load config -> validate metric preconditions -> load
dataset -> for each item under bounded concurrency call adapter.respond then metrics ->
append to journal runs/{run_id}.jsonl -> aggregate (mean + p50; failures counted
separately, NEVER averaged as zeros) -> return RunReport. Add --resume support.
Test the journal + resume + failure-handling paths. Plan first.
```

**M1.7 — Reporters**
```
Implement evalcore/reporters/json_reporter.py and markdown_reporter.py. JSON = full
RunReport; markdown = a readable summary table (metric, mean, p50, failures). Test both
against a sample report. Plan first.
```

**M1.8 — CLI + toy example (M1 exit)**
```
Implement evalcore/cli.py with typer commands `init` (scaffold evalcore.yaml +
datasets/ + adapters/) and `run` (execute a run, write reports). Add examples/toy/ :
a trivial callable, a 5-item golden.jsonl, and an evalcore.yaml. Then run it end to end
and show me the markdown report. This closes M1. Plan first.
```

**M1 wrap**
```
Run make test && make lint. Fix anything red. Walk REVIEW-CHECKLIST.md, update MEMORY.md
(check off M1 tasks, set phase to M2, log decisions), and create a git commit "M1: evalcore skeleton".
```

---

## MILESTONE 2 — Judge metrics + gate

**M2.1 — Judge client + cache**
```
Implement evalcore/judge/client.py (provider-agnostic judge call: Anthropic/OpenAI,
pinned model+prompt_version, strict-JSON response {score, reason}, one repair retry,
backoff on 429/5xx) and judge/cache.py (content-hash disk cache in .evalcore_cache/).
Add a FakeJudge for tests per agent_docs/testing.md. NO real LLM calls in tests. Plan first.
```

**M2.2 — Judged metrics**
```
Implement evalcore/metrics/judged.py: faithfulness (answer vs retrieved_context),
answer_relevance (answer vs input.question), custom_judged (user prompt file with
{input}/{answer}/{reference} slots). Record provider/model@prompt_version in each result.
Test with FakeJudge. Plan first.
```

**M2.3 — HTTP adapter**
```
Implement evalcore/adapters/http_adapter.py (POST target, JSONPath response mapping from
config, auth header from env var NAME, timeout, retries on 429/5xx, latency into metadata)
and n8n_adapter.py as a thin specialization. Test with httpx.MockTransport. Plan first.
```

**M2.4 — Gate + compare (M2 exit)**
```
Implement evalcore/gate.py and CLI `compare` + `baseline update`: diff a run against a
baseline JSON, apply rules (max_drop_pct, min_value), warn (or fail with --strict) on
config-hash / judge-version mismatch, exit 1 on violation with a violations table.
Test the rule table and exit codes on synthetic data. Then wrap M2 (test+lint, MEMORY.md,
commit "M2: judge + gate"). Plan first.
```

---

## MILESTONE 3 — TicketPilot core

**M3.1 — App skeleton + DB**
```
Scaffold ticketpilot/: FastAPI app factory, pydantic-settings, docker-compose (api +
postgres/pgvector), alembic, the schema from docs/TechDesign §3.1 (documents, chunks with
hnsw + gin indexes, tickets). Provide .env.example. Plan first.
```

**M3.2 — Ingestion**
```
Implement ticketpilot ingestion (FR-T1..T3): docs_loader (git clone + markdown parse),
issues_loader (GitHub API, closed question-issues with maintainer answers -> raw_issues.jsonl),
two chunkers (fixed_512_50, heading_v1) with strategy version in the chunk id, configurable
embedder, and `make ingest` (idempotent per strategy+model). Test idempotency + retrieval
on a seeded mini-corpus with known relevant ids. Plan first.
```

**M3.3 — Pipeline**
```
Implement the pipeline (FR-T4..T7) as stage functions per agent_docs/code_patterns.md:
classify (structured output), retrieve (hybrid vector + fulltext, RRF, log retrieved ids),
generate (grounded answer with citations, abstain -> grounded:false), escalate (low
confidence OR ungrounded OR weak retrieval). Test each stage with recorded fixtures. Plan first.
```

**M3.4 — API (M3 exit)**
```
Implement routes (FR-T8): POST /tickets, GET /tickets/{id}, POST /tickets/{id}/resolve,
POST /tickets/eval (sync, bearer auth from env, response shaped for EvalCore's HttpAdapter:
answer, retrieved_context, retrieved_ids, metadata). Routes orchestrate only, no SQL/prompts.
Test via httpx AsyncClient. Give me one curl that demos the full flow, then wrap M3
(test+lint, MEMORY.md, commit "M3: ticketpilot core"). Plan first.
```

---

## MILESTONE 4 — Golden dataset + experiments

**M4.1 — Golden dataset**
```
Help me build ticketpilot/eval/datasets/golden.jsonl from raw_issues.jsonl: draft 80
candidate items (question, reference.answer, reference.relevant_ids) and flag the ~30 you're
least sure about for me to verify by hand. Tag 10 stable ones as "smoke". Plan first.
```

**M4.2 — Wire EvalCore + baseline**
```
Create ticketpilot/eval/evalcore.yaml (http adapter -> /tickets/eval, metrics:
recall@5, precision@5, faithfulness, answer_relevance; gate rules) per docs/TechDesign §4.
Run one full eval, save it as eval/baselines/main.json. Show me the markdown report. Plan first.
```

**M4.3 — Experiment grid (M4 exit)**
```
Run the grid: chunkers {fixed_512_50, heading_v1} x embedders {small, openM} x top-k {3,5,8}
(restart api with env between runs), collect results into docs/experiments.md as a table,
and write 2-3 honest sentences incl. any case where the "better" option did NOT help. Then
wrap M4 (MEMORY.md, commit "M4: dataset + experiments"). Plan first.
```

---

## MILESTONE 5 — CI, deploy, observability

**M5.1 — GitHub Action**
```
Build the composite action in evalcore/action/action.yml and ticketpilot's
.github/workflows/eval.yml: PR = smoke subset (temp 0, cached judge) + gate compare;
nightly = full run posting the markdown summary as a commit comment. Plan first.
```

**M5.2 — Observability**
```
Add ticketpilot observability (FR-T9): structlog JSON with request_id, Langfuse spans per
stage (no-op if env unset), /metrics (latency percentiles, escalation_rate, tokens, cost),
slowapi rate limiting. Test the /metrics shape and that tracing is a clean no-op unset. Plan first.
```

**M5.3 — Deploy + post-mortem (M5 exit)**
```
Prepare deployment to Fly.io (Dockerfile multi-stage non-root, alembic on release, managed
postgres, secrets). Give me the exact step-by-step commands to run myself (I deploy, you
don't). After deploy, make one PR that improves retrieval so the gate visibly fires, then
write POSTMORTEM.md about one real failure we hit. Wrap M5 (MEMORY.md, commit "M5: ci + deploy").
Plan first.
```

---

## MILESTONE 6 — Universality proof (the headline)

**M6 — Onboard a second project**
```
Onboard a SECOND project to EvalCore with ZERO changes to the evalcore package: pick one of
my n8n workflows (use n8n_webhook adapter) or a Voxora endpoint (http adapter). Create only
3 files: an adapter/config, a small golden dataset, and its evalcore.yaml. Run an eval and
show the report. Then write docs/universality.md proving G1 (list exactly which files were
added and confirm 0 core edits via git diff --stat on the evalcore package). Wrap M6
(MEMORY.md, commit "M6: second consumer, G1 proven"). Plan first.
```

---

## UTILITY PROMPTS (use anytime)

**Verify (if the agent forgot)**
```
Run make test && make lint. Fix any failures. Then walk REVIEW-CHECKLIST.md and tell me
which items pass and which don't.
```

**Update memory**
```
Update MEMORY.md: check off completed tasks, set the active phase/goal, and add today's
decisions to the log. Keep it short.
```

**Explain (Level A learning — use often, it's your interview prep)**
```
Before we continue, explain in plain language what we just built, why it matters for the
project, and one trade-off we made. 5 sentences max.
```

**Unstick**
```
That got complex. What's the simplest version that satisfies the current task's exit
criteria in MEMORY.md? Propose that instead.
```

**Compact before a new session**
```
Summarize what we did this session and the exact next step into MEMORY.md so a fresh
session can resume cleanly.
```
