# TicketPilot

Support-ticket resolution engine (RAG) — EvalCore's reference consumer.

> **Status:** M3.1 — app skeleton + DB schema. Pipeline (ingest/classify/retrieve/
> generate/escalate) and API routes arrive in later M3 sub-tasks.

## Local development

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -e ".[dev]"
make test      # pytest (offline)
make lint      # ruff + mypy --strict on app/
make dev       # uvicorn (needs a reachable DATABASE_URL for DB routes)
```

## Database

The app talks to Postgres over a plain SQLAlchemy async URL (`DATABASE_URL`). Two options:

**Managed (Supabase / Neon):** copy `.env.example` to `.env` and set `DATABASE_URL` to your
connection string + DB password (not the JWT/API keys). Then, once:

```sql
create extension if not exists vector;
```

**Local (Docker):** `docker compose up db` starts `pgvector/pgvector:pg16`.

Apply the schema (creates documents/chunks/tickets + HNSW/GIN indexes):

```bash
make migrate      # alembic upgrade head
```

## Configuration

All knobs are environment-driven (`app/settings.py`): `DATABASE_URL`, `ACTIVE_STRATEGY`,
`ACTIVE_EMBED_MODEL`, `TOP_K`, `CONF_THRESHOLD`, `LLM_MODEL`, and API keys. See `.env.example`.
Secrets never live in the repo.
