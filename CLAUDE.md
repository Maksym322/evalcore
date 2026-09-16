# CLAUDE.md — Claude Code Configuration for EvalCore + TicketPilot

## Project Context
**App:** EvalCore (universal LLM eval framework, PyPI package) + TicketPilot (FastAPI RAG support-ticket engine, reference consumer)
**Stack:** Python 3.11+, Pydantic v2, FastAPI, Postgres 16 + pgvector, typer, httpx, structlog, Docker, GitHub Actions
**Stage:** MVP Development (active phase: see MEMORY.md)
**User Level:** A (vibe-coder) — explain simply, propose plans, verify everything yourself

## Directives
1. **Master Plan:** Always read `AGENTS.md` first, then `MEMORY.md` for the active phase and task list.
2. **Documentation:** `agent_docs/` for tech stack, code patterns, testing rules; `docs/` for PRD + Tech Design (source of truth).
3. **Plan-First:** Propose a brief plan and wait for approval before coding.
4. **Incremental Build:** One feature at a time; commit at milestones; update MEMORY.md after each session.
5. **Verify:** `make test && make lint` after each feature; walk REVIEW-CHECKLIST.md before marking done. Never bypass failing hooks.
6. **Scope:** v1 non-goals are binding (no web UI, no online evals, no multi-turn). No abstraction until two consumers need it.
7. **Testing rule:** evalcore's own tests never call real LLMs — use FakeJudge (agent_docs/testing.md).
8. **Communication:** Be concise. If context is missing, ask ONE specific question.

## Commands
- `make dev` — run locally (docker compose for ticketpilot)
- `make test` — pytest
- `make lint` — ruff check + ruff format --check + mypy --strict
- `make ingest` — build ticketpilot index
- `make eval` / `make eval-smoke` — eval runs (need API keys in env)
