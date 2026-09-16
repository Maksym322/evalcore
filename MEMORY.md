# MEMORY.md — Artifact-First Memory

> The agent updates this file at the end of every working session. Keep entries short and factual.

## 🏗️ Active Phase & Goal

**Phase:** M3 — TicketPilot (RAG ticket-answering service; EvalCore's first real consumer)
**Goal:** ingest → pgvector index → pipeline (classify/retrieve/generate/escalate) → `POST /tickets/eval` returning `{answer, retrieved_context, retrieved_ids, metadata}` shaped for the HttpAdapter.
**Roadmap after:** M4 golden dataset+baseline+experiments · M5 GitHub Action/CI/deploy · M6 N8nWebhookAdapter onboard.

**M3 sub-task breakdown (user drove numbering):**
1. [x] M3.1 — skeleton + DB: app factory, settings, docker-compose, alembic + §3.1 schema
2. [x] M3.3 — pipeline stages (classify/retrieve/generate/escalate) vs injected protocols + fakes
3. [x] M3.4 — API routes (POST /tickets, GET, resolve, POST /tickets/eval) + orchestrator + repository
4. [ ] ingestion: docs_loader, chunkers (FixedSize 512/50, HeadingAware), issues_loader; `make ingest`
5. [ ] REAL impls: Gemini LLM client (httpx), Embedder, PgRetrievalStore — integration-tested vs live DB
6. [ ] observability (structlog JSON, /metrics, rate limit) + eval/ wiring to EvalCore
(FR-T10 experiments + FR-T11 → M4.)

**⚠️ M3 IS NOT COMPLETE.** Routes + pipeline are offline-tested against FAKES. TicketPilot cannot answer a real ticket yet: no real LLM/embedder/store, schema not applied to Supabase, no ingested data. A real end-to-end curl needs: rotate keys → pick embedder → build real impls → apply schema → ingest a repo.

**Providers:** LLM = **Google Gemini** (user provided a key — TOLD TO ROTATE; use httpx generateContent, GEMINI_API_KEY from env). Embedder STILL UNDECIDED: OpenAI text-embedding-3-small (keeps vector(1536)) vs a Gemini/other embedder (would need dim change in models.py + migration 0001). DB = **Supabase** (project ref `mujudqrbhiyngmrttlca`; Supabase MCP connector available in-session for schema apply / integration tests, on user request).
**⚠️ SECURITY:** user pasted Supabase service_role/secret keys AND a Gemini key in chat (2026-07-03). Told to ROTATE all. NEVER stored. Secrets → untracked .env only.

**M1 ✅ · M2 ✅** (EvalCore; committed `evalcore/` @ eae7fbb). **OPEN GAP (EvalCore):** judge not wired into runner; JudgeConfig has no `provider`; RunReport.judge_versions unpopulated.

## 📒 Decisions Log

- Foundational: PRD v1.0 + TechDesign v1.0; pgvector over Pinecone; no-abstraction-until-2-consumers.
- M1/M2 (evalcore): full deterministic+judged eval + regression gate. Judge/HttpAdapter over httpx (no SDKs). AdapterConfig discriminated union. gate exit 0/1/2.
- 2026-07-03 — M3.1 skeleton + DB (SQLAlchemy 2.0 async models, pydantic-settings, FastAPI factory + /health, alembic hand-written migration 0001: vector/pgcrypto ext + tsv generated col + HNSW/GIN indexes; dim 1536). asyncpg on py3.14.
- 2026-07-03 — M3.3 pipeline: 4 stages as functions (classify→'other' on LLMError; retrieve = embed + vector/fulltext via RetrievalStore protocol + rrf_merge pure k=60 + top_k; generate numbered-[n] context, ungrounded fallback; escalate PURE). Protocols LLM/Embedder/RetrievalStore + fakes. structlog + observability/logging (get_logger, stage_timer). Prompts in app/prompts/*.md + load_prompt. rrf_threshold=0.01 added to settings.
- 2026-07-03 — M3.4 API done. `orchestrator.answer_ticket` (classify→retrieve→generate→escalate + latency). `app/repository.py`: TicketRepository protocol + SqlTicketRepository (ORM CRUD; integration-tested later). `app/api/schemas.py`: TicketCreate/TicketOut/AnswerOut + EvalRequest (matches HttpAdapter body `{id,input}`, pulls input.body|question) + EvalOut.from_result (answer/retrieved_context/retrieved_ids/metadata{latency_ms,category,confidence,grounded,status,reasons}). `deps.py`: get_llm/embedder/store RAISE 503 until real impls wired (tests override); get_repository=SqlTicketRepository(session); require_eval_token bearer from settings.eval_token. Routes orchestrate only. GOTCHA fixed: overriding a dep with a CLASS that has __init__ params leaks them into the request body schema (422) → override with `lambda: FakeEmbedder()`. 25 offline tests (httpx ASGITransport + dependency_overrides). Green (mypy 24 files, pytest 25).

## ⏭️ Next Steps

- Blocked on user: (1) ROTATE keys, (2) pick embedder (OpenAI-1536 vs Gemini+dim-change). Then real-impl track: Gemini LLM client (offline MockTransport-testable NOW, no key needed) → Embedder → PgRetrievalStore (needs live Supabase). Parallel offline track: chunkers (pure). Recommend: build Gemini client next (offline). Also can apply schema to Supabase via connector on request.

## 🧯 Known Issues / Blockers

- CONNECTION: Windows-MCP (FileSystem/PowerShell) dropped mid-session once; came back after user reconnected. If tools vanish, ask user to restart the Windows-MCP connector. Supabase + Notion connectors are separate and stayed up.
- git: `evalcore/` is its own repo (@eae7fbb). `ticketpilot/` — committing as its own repo too (mirrors evalcore). Not a monorepo.
- FileSystem write emits CRLF. Use FileSystem write with overwrite=true for full rewrites; for targeted edits use `[System.IO.File]::WriteAllText` matching substrings WITHOUT newline anchors. Never `Set-Content -Encoding utf8` (BOM).
- Overriding FastAPI deps: use zero-arg callables, never a class with __init__ params (leaks into request schema → 422).
- StarletteDeprecationWarning (httpx/testclient) — cosmetic.
