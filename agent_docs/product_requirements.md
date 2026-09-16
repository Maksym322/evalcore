# Product Requirements (extracted from docs/PRD-evalcore-ticketpilot.md v1.0)

**Product:** EvalCore + TicketPilot
**One-liner:** Universal, project-agnostic evaluation framework for LLM systems, shipped with its first production consumer — a support-ticket resolution engine — proving the framework on a real workload.

## Primary user story
As the maintainer of several LLM projects (ticket engine, voice agent, n8n automations, multi-tenant SaaS), I want one shared eval toolkit so that adding quality measurement to any project takes an adapter, a dataset, and a config — not a rebuild.

Core scenario that must stay this simple:
```bash
pip install evalcore
evalcore init
# write adapters/my_project.py (≤ 30 lines), fill datasets/golden.jsonl
evalcore run --config evalcore.yaml
evalcore compare --baseline baselines/main.json   # exit 1 on regression
```

## Goals (must-have)
- **G1 Universality:** onboarding a new project requires ZERO core changes — only adapter + dataset + config
- **G2 Regression gating:** consumer repos block PR merges on quality drops via a reusable GitHub Action
- **G3 Reference proof:** TicketPilot runs the full loop with published before/after numbers (chunking, embeddings, top-k)
- **G4 Cost control:** full 80-item run < $1; PR smoke run < $0.10
- **G5 Reproducibility:** same dataset + config + pinned models ⇒ deterministic deltas within documented tolerance

## Must-have features
EvalCore: dataset loader (open JSONL schema) · Target protocol + PythonAdapter, HttpAdapter, N8nWebhookAdapter · metric registry (deterministic: recall@k, precision@k, exact_label_match, json_schema_valid, latency_budget; judged: faithfulness, answer_relevance, custom_judged with per-project prompt) · judge client with pinned model + content-hash cache · runner with concurrency, journal, resume · gate (`compare`, baseline, max_drop_pct / min_value rules, config-hash guard) · reporters (json, markdown, github-comment) · CLI (init/run/compare/baseline) · composite GitHub Action (smoke on PR, full nightly).

TicketPilot (FR-T1…T11): docs+issues ingestion (`make ingest` idempotent) · two chunkers (fixed 512/50, heading-aware) · pgvector index, configurable embedder · structured-output classification · hybrid retrieval (vector + fulltext, RRF) · grounded generation with citations + abstention (`grounded:false`) · escalation gate (confidence / groundedness / weak retrieval) · API: POST /tickets, GET /tickets/{id}, POST /tickets/{id}/resolve, POST /tickets/eval (sync, auth, eval-shaped response) · observability (structlog JSON + request_id, Langfuse, /metrics, rate limiting) · experiment grid 2 chunkers × 2 embedders × k∈{3,5,8} with README table incl. negative results · POSTMORTEM.md of one real failure.

## Nice-to-have (v2 backlog — DO NOT build in v1)
Multi-turn evals · Langfuse trace ingestion (online evals) · results web dashboard (Next.js) · pairwise A/B judge mode · dataset synthesis assistant · voice-specific latency metrics.

## NOT in MVP (binding non-goals)
No web UI for results · no online/production evals · no fine-tuning/training · no multi-turn in v1 · EvalCore never hosts/runs the target system.

## Success metrics
- G1 verified: 2nd project onboarded with ≤ 3 new files, 0 core edits (Milestone M6)
- ≥ 1 PR in ticketpilot blocked/flagged by the gate, then fixed (visible in CI logs)
- README experiment table with ≥ 12 runs incl. at least one honest null/negative result
- EvalCore on PyPI; TicketPilot deployed with a public URL
- Full-run cost < $1 (receipt in docs)

## Constraints & performance
Full 80-item eval < 10 min at concurrency 8 · TicketPilot p95 answer latency < 8 s · judge retries with backoff, partial runs resumable · secrets via env only · `evalcore init` → first successful run in < 15 min for a new project.

## Timeline (milestones — details in AGENTS.md roadmap)
M1 skeleton (1 wk) → M2 judge+gate (1 wk) → M3 TicketPilot core (1.5 wk) → M4 golden dataset + experiments (1 wk) → M5 CI+deploy+observability (1 wk) → M6 universality proof (3–4 d).
