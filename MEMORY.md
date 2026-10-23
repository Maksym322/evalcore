## 2026-10-23 EC-001 offline CI foundation (completed)

- **Outcome**: Implemented bounded offline PR/main CI and genuine deterministic regression gates for EvalCore and TicketPilot monorepo.
- **Workflow**: Added `.github/workflows/offline-ci.yml` running on `pull_request` and `push` to `main`. Read-only `contents: read` permissions, 15-minute job timeouts, short-lived artifacts (`reports/`, retention <= 7 days), zero access to secrets, and all actions pinned to full 40-char commit SHAs (`actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803`, `actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1`, `actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f`).
- **Compatibility Fix**: Fixed strict mypy error in `evalcore/evalcore/adapters/http_adapter.py` by importing directly from `jsonpath_ng.parser import parse as jsonpath_parse`, removing obsolete ignore and satisfying strict attr-defined checks with zero API/schema changes.
- **Regression Gate Tests**: Added `evalcore/tests/test_ci_gate.py` executing genuine gate configs: synthetic pass (exit code 0), deliberate regression drop (exit code 1 with violations), missing gate/baseline error handling (exit code 2), strict hash mismatch failure, and deterministic toy evaluation generating real JSON reports.
- **Documentation**: Documented supported (>=3.11) and actual tested Python versions (3.12 locally, 3.14 baseline) in `docs/ci.md` and updated `agent_docs/testing.md`.
- **Local Verification Results** (Fleet Run ID: `9fcc8009-330f-4037-8863-b0084e6ca28f`, base SHA `88e4402baa8046e0a0fbbccb2eaff0cf1fcbe7e8`):
  - `eval-unit`: 146 passed (0 failures)
  - `eval-lint`: Ruff check + format clean (45 files)
  - `eval-types`: Mypy strict clean (22 source files)
  - `ticket-unit`: 34 passed (0 failures)
  - `ticket-lint`: Ruff check + format clean (42 files)
  - `ticket-types`: Mypy strict clean (30 source files)
  - `offline-gates`: 22 passed gate/CLI tests + toy evaluation JSON report generated
  - `workflow`: Bounded workflow structure, permissions, and pinned action SHAs verified
- **Limitations**: Remote CI runs, remote GitHub Actions artifacts, and future main-push runs remain pending coordinator branch push, PR creation, and billing allowance checks. No remote runs occurred overnight; no provider credentials or live database calls used.

## 2026-10-22 orchestrator integration planning (current)

- Planning only: see docs/orchestrator-integration.md for product boundaries, CI, behavioral test authoring and offline retrieval evaluation.
- Canonical EvalCore project registered in local operator database; TicketPilot remains its reference component. EC-001 is draft; ORC-014/015/016 are blocked backlog requests with API readback, no execution dispatched.
- Local source inspected at 40115f0; remote main observed at 2ec635e. Neither inspected commit has tracked GitHub workflows. Git transport works; Actions API access/settings/billing were not inspected.
- No application code, dependency, provider or database schema change. No fresh application test suite run in this planning session. M3/M4 completion is not asserted.
- Older phase and two-repository notes below are historical; use the newer dated entries plus actual source.
# MEMORY.md — Artifact-First Memory

> The agent updates this file at the end of every working session. Keep entries short and factual.

## 2026-09-30 deployment preparation (current state)

- The folders `evalcore/` and `ticketpilot/` are in **one Git repository** (`project1`), despite older notes below describing separate repositories. Work is in isolated branch `prep-ticketpilot-deploy` under `voice-fleet-dev/artifacts/project1-deploy-work`; original checkout was clean and left untouched.
- Added a Gemini structured-output client (one repair retry), Gemini query/document embeddings at 1536 dimensions, Postgres vector/full-text retrieval, fixed 512/50-character Markdown ingestion, and API bearer auth. Model defaults are `gemini-3.5-flash-lite` and `gemini-embedding-2`; no schema migration was needed because embedding dimension remains 1536.
- Compose now runs migration before API, keeps Postgres internal, and binds API to loopback. README and `.env.example` describe local setup. 34 TicketPilot offline tests pass, Ruff and mypy pass; runtime-only package import also passes. **No real provider call or live DB/Compose end-to-end test yet.** Docker Desktop Linux engine was unavailable during this session.
- EvalCore runner now wires configured judge metrics, records judge versions, and can use the Gemini judge; 140 offline EvalCore tests pass. `judge.provider` is now required in configs that use judged metrics (config contract change, no DB migration). A two-question TicketPilot smoke config exists, but has not been run against live API and is not a validated golden dataset.
- Still open in M3: GitHub issues loader, heading-aware chunking, retrieval/DB integration tests, metrics/rate limiting/tracing. M4 verified golden dataset/baseline and M5 CI/public deployment are not done.
- Need user choice of deployment host, fresh local `GEMINI_API_KEY`, and API/Eval tokens before live demo. Do not paste credentials in chat. Old exposed Gemini/Supabase keys mentioned below must be rotated before reuse.

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
