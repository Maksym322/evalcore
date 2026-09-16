# Project Brief (Persistent)

- **Product vision:** One eval framework (EvalCore) that any of Max's LLM projects plugs into with 3 files (adapter + dataset + config); TicketPilot is the reference consumer proving it on a real RAG workload. Portfolio goal: demonstrate production signals — evals, regression gating in CI, observability, honest experiment write-ups.

- **Coding conventions:** Python 3.11+, full type hints (`mypy --strict`), Pydantic v2 at every boundary, snake_case modules, prompts in versioned files, business logic never in routes/CLI entrypoints. Patterns in `agent_docs/code_patterns.md` are canonical.

- **Quality gates:** `make lint` (ruff + format + mypy) and `make test` green before any commit; pre-commit hooks enforced; REVIEW-CHECKLIST.md walked before marking a feature done; evalcore's own CI never calls real LLMs (FakeJudge).

- **Key commands:** `make dev` / `make test` / `make lint` / `make ingest` / `make eval` / `make eval-smoke` (full list + setup: `agent_docs/tech_stack.md`).

- **Scope discipline:** current phase and tasks live in `MEMORY.md`; v1 non-goals (no web UI, no online evals, no multi-turn, no fine-tuning) are binding; no abstraction until two consumers need it.

- **Update cadence:** refresh this brief and MEMORY.md at the end of every working session and at every milestone (M1–M6).
