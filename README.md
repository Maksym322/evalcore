# 🦅 EvalCore + TicketPilot

> **Universal LLM Evaluation Framework & Reference RAG Application**

EvalCore is a project-agnostic, regression-gated evaluation framework for LLM systems (pip-installable package). It is shipped alongside **TicketPilot** — a 4-stage RAG support-ticket resolution engine — as its first reference consumer.

---

## 📐 Architecture Overview

```
project1/
├── evalcore/        # Universal evaluation framework (PyPI package)
└── ticketpilot/     # Reference RAG consumer (FastAPI + pgvector)
```

### 1. EvalCore Framework (`/evalcore`)
- **Deterministic & Judged Metrics**: Retrieval recall/precision, exact label match, JSON schema validation, latency budget, LLM-as-a-judge (faithfulness & relevance).
- **Adapters**: Flexible target protocols supporting Python callables, HTTP endpoints, and webhooks (n8n).
- **CI Regression Gating**: Automated baseline comparison (`max_drop_pct`, `min_value`) returning non-zero exit codes on quality degradation.
- **Production Resilience**: Bounded async concurrency, journal + resume, content-hash disk caching for judge calls.

### 2. TicketPilot Engine (`/ticketpilot`)
- **4-Stage Pipeline**: `Classify` → `Retrieve` (hybrid vector + full-text w/ Reciprocal Rank Fusion) → `Generate` (grounded citations) → `Escalate`.
- **Async Tech Stack**: FastAPI, SQLAlchemy 2.0 async, PostgreSQL 16 + pgvector (HNSW & GIN indexes), Docker Compose.
- **Eval Integration**: Native `POST /tickets/eval` endpoint shaped directly for EvalCore's HTTP adapter.

---

## 🚀 Quick Start

### Running EvalCore Tests & CLI

```bash
cd evalcore
pip install -e .[dev]

# Run tests & linter
pytest
mypy --strict evalcore

# Run example evaluation
evalcore run examples/toy/evalcore.yaml
```

### Running TicketPilot Locally

```bash
cd ticketpilot
pip install -e .[dev]

# Start Postgres + pgvector
docker compose up -d

# Run API & Pipeline tests
pytest
```

---

## 🛠️ Tech Stack

- **Core & API**: Python 3.11+, Pydantic v2, FastAPI, Typer CLI
- **Database**: PostgreSQL 16 + pgvector (asyncpg, Alembic)
- **Tooling**: Ruff, MyPy (`--strict`), Pytest (asyncio), Docker Compose

---

## 📜 License

MIT License
