# EvalCore

Universal, project-agnostic evaluation framework for LLM systems.

> **Status:** M1 — skeleton in progress. See `../AGENTS.md` for the roadmap and
> `../MEMORY.md` for the active phase and task list.

## Development

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
make dev                                          # pip install -e ".[dev]"
make test                                         # pytest
make lint                                         # ruff + mypy --strict
```
