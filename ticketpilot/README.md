# TicketPilot

TicketPilot is the FastAPI RAG consumer for EvalCore. It classifies a support question,
retrieves Markdown chunks from Postgres using vector and full-text search, generates an
answer with citations, and escalates when confidence or grounding is weak.

**Status:** M3 is in progress. The Gemini LLM and 1536-dimensional embedding clients,
Postgres retrieval, fixed-size Markdown ingestion, and bearer-protected routes are implemented.
Offline tests pass. A real Gemini call, live Postgres search, and the complete Compose flow
still need integration testing. GitHub issue ingestion, heading-aware chunking, metrics,
and a real EvalCore baseline are not yet implemented. Do not expose this stack publicly.

## Local Compose demo (PowerShell)

1. Copy `.env.example` to `.env`. Set `POSTGRES_PASSWORD`, `GEMINI_API_KEY`, `API_TOKEN`,
   and `EVAL_TOKEN`. Use a **new** Gemini key if an earlier key was shared in chat.
   Keep `.env` untracked. For a password in the database URL, URL-encode reserved characters.
2. Run `docker.exe compose up -d --build`. The `migrate` service applies migration
   `0001_initial` before `api` starts. API listens only on `127.0.0.1:18000` by default;
   the database is internal to Compose.
3. Index Markdown from a local directory, for example this repository's `docs` folder:

   ```powershell
   docker.exe compose run --rm --volume "${PWD}/../docs:/source:ro" api python -m app.ingestion.cli /source
   ```

4. Send a ticket (replace token with your local `API_TOKEN`):

   ```powershell
   $headers = @{ Authorization = "Bearer $env:API_TOKEN" }
   $body = @{ body = "What does EvalCore evaluate?" } | ConvertTo-Json
   Invoke-RestMethod http://127.0.0.1:18000/tickets -Method Post -Headers $headers -ContentType 'application/json' -Body $body
   ```

`GET /health` is process liveness only. It does not prove Gemini, database access,
or ingestion. `POST /tickets/eval` accepts a separate `EVAL_TOKEN` and returns
`{answer, retrieved_context, retrieved_ids, metadata}` for EvalCore's HttpAdapter.
Both ticket endpoints require a nonempty body of at most 10,000 characters.

The `eval/evalcore.smoke.yaml` config targets this endpoint. With the stack running,
set `TICKETPILOT_EVAL_URL=http://127.0.0.1:18000/tickets/eval`, `EVAL_TOKEN`, and
`GEMINI_API_KEY` in the shell, then from `ticketpilot/` run:

```powershell
../evalcore/.venv/Scripts/python.exe -m evalcore.cli run --config eval/evalcore.smoke.yaml --out-dir runs/smoke
```

This two-question smoke set checks connectivity and report generation only. It is not
a verified golden dataset or a regression baseline. The judge currently uses Gemini,
the same provider as the target, so its scores need independent human review.

## Local Python development

```powershell
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -e '.[dev]'
.venv/Scripts/python.exe -m pytest
.venv/Scripts/ruff.exe check .
.venv/Scripts/mypy.exe app
```

The `DATABASE_URL` setting is an async SQLAlchemy URL. For managed Postgres, use a
Postgres connection string and password, not a Supabase API key. Schema changes require
an Alembic migration; existing migration `0001_initial` creates the pgvector extension,
tables, and indexes. The current chunk strategy is `fixed_512_50` (characters). Chunk
IDs include source path, strategy, and embedding model so re-indexing is idempotent per
variant. The same Gemini embedding model and dimension must be used for indexing and
queries.
