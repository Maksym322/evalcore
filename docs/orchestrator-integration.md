# EvalCore integration with Prada Orchestrator

Planning snapshot: 2026-10-22. This document is not execution evidence.

## Verified starting point

`project1` is one repository, `Maksym322/evalcore`, containing the EvalCore
library and its TicketPilot reference application. Local base is
`40115f030426fc25ee78686c6a820c3955ba1000`; the remote main branch observed today
is `2ec635eb7af3950c0baacfe953f6a62ffca8e285`. Neither inspected commit tracks
`.github` workflows. Git transport works. GitHub Actions settings, billing,
branch protection and historical remote runs have not been inspected.

EvalCore has Python/HTTP target adapters, deterministic and judge metrics,
reports, and a baseline comparison CLI. It evaluates outputs; it does not
currently generate application tests. TicketPilot is unfinished M3, with no
verified golden dataset or live deployment acceptance. The newer dated MEMORY
entry supersedes older claims about separate repositories and missing clients.
Historical test counts are not a fresh verification run.

## Responsibilities and user flow

Register one canonical product, `evalcore`, with TicketPilot as a component.
Worktrees are execution locations, not additional products. Registration alone
does not authorize execution or modify the worker workspace registry.

1. Owner submits a request and acceptance criteria to the orchestrator.
2. Preparation fixes scope, repository, base commit and required checks.
3. A worker uses an isolated branch/worktree to implement code and meaningful
   tests. Included provider quota only; no automatic paid fallback.
4. Local checks run against the final commit. The coordinator reviews and pushes
   the finished branch; workers do not push, merge or deploy themselves.
5. GitHub Actions runs on PRs and pushes to main. A PR run and a main push run
   may test different SHAs; each result retains its actual tested SHA.
6. The panel presents local evidence and separately verified remote CI evidence.
   Failed, pending, missing and stale checks cannot count as passing.
7. Owner accepts or requests changes. Acceptance, merge and deployment remain
   distinct actions; baseline promotion also requires explicit review.

The orchestrator coordinates work and evidence. GitHub Actions executes CI.
EvalCore measures AI behavior. Do not build another CI scheduler or make the
unfinished TicketPilot service a dependency of ordinary development.

## Bounded implementation tasks

### EC-001: Offline CI foundation (EvalCore repository)

Add PR and main-push workflows for both Python components using declared dev
dependencies. Determine and document supported Python versions before choosing
the matrix. Run pytest, Ruff check/format and mypy from the correct component
directories. Run the toy deterministic evaluation without provider keys. Add a
synthetic regression-gate fixture proving both pass and deliberate fail, without
replacing a reviewed baseline automatically. Existing Makefiles describe the
checks; establish actual current results before changing implementation.

Acceptance: a branch PR produces checks and downloadable bounded reports for its
tested SHA; a deliberately broken fixture fails; main push is covered in workflow
configuration and verified on a future authorized merge. Tests require no live
Gemini, Supabase or TicketPilot service. Set read-only workflow permissions,
timeouts, action SHA pins and safe artifact paths. Never use privileged
pull_request_target to execute changed code. Account allowance/billing must be
checked before enabling jobs that might incur additional spending. No deployment.

### ORC-014: Behavioral test authoring in worker tasks

Use the accepted worker/materialization foundation, re-pinned after review.
The preparation step records why tests are needed and their behavioral oracle.
A worker may author unit, integration or browser tests appropriate to the task;
cosmetic changes may record a justified no-new-test decision. A regression fix
must demonstrate that its regression test fails against the unfixed base and
passes against the final head, or document why a different reproducible oracle
is necessary. Failures due only to missing dependencies are not bug reproduction.

Acceptance: synthetic faulty browser polling is caught by executed browser code;
a static source-string assertion cannot substitute for that behavior. Reviewer
checks assertions and negative cases independently; generated tests cannot
silently weaken existing checks or update baselines to bless a regression.
Preserve exact base/head, test commands, logs and provider usage in evidence.
Tests alone do not establish production correctness or owner acceptance.

### ORC-015: First offline EvalCore consumer

Depends on reviewed EC-001 and ORC-013 integration. Pin an immutable EvalCore
revision. Adapt ORC-013's real context retrieval output through the existing
Python adapter contract; use synthetic, project-scoped, versioned questions and
known source IDs. Measure retrieval recall/precision and prohibited cross-project
hits with deterministic metrics. Do not pass real secrets or customer transcripts.

Acceptance: valid retrieval passes the reviewed threshold, removed relevant
sources fail it, and a cross-project leak fails regardless of average score.
Reports identify source commit, EvalCore revision, dataset/config hashes, check
command and gate result. Rebuilding indexes must not rewrite the expected
answers. No judge/API/key is required. Baseline promotion is a reviewed code
change. Voice Fleet transcript evaluation and live judges are separate future
tasks; do not build them here.

### ORC-016: GitHub CI evidence in the operator panel

Depends on reviewed EC-001 and ORC-011; re-pin the accepted operator integration
before coding. Prefer read-only polling/reconciliation initially, avoiding a
public webhook endpoint or inbound router ports. Specify repository allowlists
and a minimal read-only GitHub credential only if existing authenticated access
cannot provide the necessary API reads. Git push access alone does not prove
Actions API access.

Acceptance: display repository, workflow/check identity, run URL, actual tested
SHA and status. A successful old SHA, unrelated repository, cancelled/skipped
required job, missing artifact, or fork without authorized provenance does not
satisfy current-head checks. Account for PR merge-ref SHA explicitly. Offline
mock tests cover delayed/duplicate results, outages, rate limiting and restart
reconciliation; no automatic acceptance/merge/deployment follows CI success.

## Execution order, services and rollout

EC-001 and ORC-014 can be developed independently once their own pinned bases are
prepared. ORC-015 and ORC-016 follow their stated reviewed dependencies. These
are backlog requests, not runnable fleet specs; materialize exact bases, scopes,
commands and available provider model IDs before dispatch. Do not invent a model
name or assume GitHub-hosted runners have the owner's desktop OAuth session.

No new service or key is required for the first offline implementation. Optional
future live judge runs need a separately authorized, bounded provider route;
personal OAuth caches must never be uploaded to GitHub. PostgreSQL, Redis and a
new vector database are unnecessary for this integration. TicketPilot's DB and
live RAG validation remain separate unfinished product work.

First owner demonstration: submit a small real change, inspect generated tests,
observe a deliberately introduced regression fail CI, observe the fix pass at
the correct SHA, restart the panel and verify evidence remains attributable.
This demonstration does not merge or deploy anything automatically.
