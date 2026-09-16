# AGENTS.md — Master Plan for EvalCore + TicketPilot

> **Read this file first in every session.** Then check `MEMORY.md` for the active phase, and `agent_docs/` for details. Source-of-truth documents live in `docs/` (PRD + Tech Design).

## Project Context

**Product:** EvalCore + TicketPilot
**One-liner:** A universal, project-agnostic evaluation framework for LLM systems (EvalCore, a pip-installable Python package), shipped with its first real consumer — TicketPilot, a support-ticket resolution engine (FastAPI + RAG) — proving the framework on a real workload.
**Why it exists:** LLM systems fail silently. EvalCore gives any project regression-gated quality measurement; onboarding a new project = 1 adapter + 1 dataset + 1 config, ZERO core changes.
**Owner level:** A (vibe-coder) — explain decisions simply, propose plans, wait for approval, verify everything yourself.

## Two Repositories (inside this workspace)

```
project1/
├── evalcore/        # universal framework (PyPI package) — build FIRST
└── ticketpilot/     # reference consumer (FastAPI app)   — build SECOND
```
Exact folder layouts: see `agent_docs/tech_stack.md` and `docs/TechDesign-evalcore-ticketpilot.md` §1.

## Roadmap (from PRD §8 — do them IN ORDER)

| Phase | Scope | Exit criteria |
|---|---|---|
| **M1 (ACTIVE)** | EvalCore skeleton: schema.py, dataset loader, PythonAdapter, deterministic metrics, runner, JSON/MD reports | Eval a toy Python function end-to-end via CLI |
| M2 | Judge metrics + disk cache + pinning; HttpAdapter; gate/compare | Gate flips exit codes correctly on synthetic data |
| M3 | TicketPilot core (ingestion → classify → retrieve → generate → escalate → API) | `docker compose up` + one curl demos the full flow |
| M4 | Golden dataset (60–80 verified) + experiment grid + baseline | README results table with real numbers |
| M5 | GitHub Action, CI smoke+nightly, deploy, observability, POSTMORTEM.md | Live URL; a merged PR showing the gate in action |
| M6 | N8nWebhookAdapter + onboard ONE existing project | Second project evaluated with 0 core changes |

## How I Should Think

1. **Understand Intent First**: Before answering, identify what the user actually needs
2. **Ask If Unsure**: If critical information is missing, ask ONE specific question before proceeding
3. **Plan Before Coding**: Propose a plan, ask for approval, then implement
4. **Verify After Changes**: Run tests/linters after each change; fix failures before moving on
5. **Explain Trade-offs**: When recommending something, mention alternatives simply

## Plan → Execute → Verify (Required)

- **Plan:** Outline a brief approach and wait for approval before coding. Use Plan Mode if the tool supports it.
- **Execute:** One feature at a time. Small commits at milestones.
- **Verify:** `make test` + `make lint` after each feature. Never mark a task done with red tests.

## What NOT To Do

- Do NOT delete files without explicit confirmation
- Do NOT modify database schemas without a migration (alembic) and a note in MEMORY.md
- Do NOT add features not in the current phase (v1 non-goals: no web UI, no online evals, no multi-turn, no fine-tuning)
- Do NOT skip tests for "simple" changes
- Do NOT bypass failing tests or pre-commit hooks
- Do NOT implement entry-point plugin discovery before M6 needs it ("framework disease" rule: no abstraction until two consumers need it)
- Do NOT call real LLM APIs from evalcore's own test suite — use FakeJudge (see agent_docs/testing.md)

## Engineering Constraints

- **Type safety:** full type hints on all functions; Pydantic v2 models for all data crossing boundaries; `mypy --strict` must pass. Avoid `Any` — if unavoidable, comment why.
- **Architecture:** FastAPI routes handle request/response ONLY; business logic lives in `app/pipeline/` and `app/ingestion/` (ticketpilot) or `evalcore/` modules (framework). No DB calls from route handlers.
- **Library governance:** check `pyproject.toml` before adding dependencies; prefer stdlib/httpx over extra libs; judge calls only through `evalcore/judge/client.py`.
- **Secrets:** env vars only, never in config files or code. Config references env var NAMES (e.g. `auth_header_env`).
- **Communication:** state issues briefly and fix them; no repeated apologies or filler.

## Key Commands (see agent_docs/tech_stack.md for full list)

```bash
make dev      # run locally (docker compose for ticketpilot)
make test     # pytest
make lint     # ruff check + ruff format --check + mypy
make eval     # full eval run (ticketpilot, needs API keys)
```

## Living Docs Protocol

- `MEMORY.md` — update **Active Phase & Goal** and **Decisions Log** after every working session.
- `agent_docs/*` — update when conventions/commands change.
- Avoid restarting in empty chats mid-implementation; summarize/compact first, and re-read AGENTS.md + MEMORY.md at the start of each session.
