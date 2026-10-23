# EC-001 independent morning review

Reviewed head: `484cf0d7e67d865ade27ee97761e4debb3ca7317`.
Execution review base: `6db6f46baf3ceff50496fa7d2067b72c2e966bef`.
Earlier planning/source base in the frozen specification: `88e4402baa8046e0a0fbbccb2eaff0cf1fcbe7e8`.
Worktree: `C:/Users/Maks/.prada-orchestrator/local-dev/night-20261023/EC-001/worker-state/attempts/72106e2288f54ec19d3a21c177daefb4/worktree`.
Reviewer: independent read-only Codex session, following the prada-dev fleet-review skill. Source was clean at review start; no source changes were made.

## Verdict

Changes requested for one bounded provenance gap. Functional offline behavior and the narrow typing correction look sound. This is not owner acceptance. Remote workflow execution, allowance/billing confirmation, PR artifacts, and a future main-push run remain unverified.

## Finding P2: uploaded artifacts do not identify the revision actually tested

Location: `.github/workflows/offline-ci.yml:55` and `:99`; supporting documentation `docs/ci.md:12` and `:81`.

Trigger: execute the configured pull_request workflow and download either component artifact. Checkout has no explicit ref, so GitHub checks out its PR merge ref by default. The EvalCore artifact contains the ordinary toy RunReport; TicketPilot uploads ordinary JUnit. Neither upload has a provenance manifest recording the checked-out Git SHA, event/ref, repository, run ID/attempt, or PR head/base identity. The static artifact names do not encode these either. The docs describe branch-head-against-base behavior without identifying the merge-ref SHA distinction.

Reproduction: independently ran the real toy CLI in a disposable directory on this exact head. It exited0 and produced a3295-byte JSON report for5items. Its keys are project, run_id, started_at, config_hash, judge_versions, items, aggregates, per_item. No Git revision is present. Source inspection confirms no workflow step adds a provenance file to either artifact.

Impact: a downloaded report cannot independently establish the code revision it measured. Treating a PR run's branch head as the tested checkout can attach evidence to the wrong SHA. Frozen EC001 criteria explicitly require report/tested-SHA provenance. This gap is separate from the explicitly deferred remote-run demonstration.

Bounded correction: add a small provenance manifest under each uploaded report directory, obtaining the actual checkout via git rev-parse HEAD; record event/ref and run identity, and distinguish PR head/base from tested merge SHA. Document the distinction and add an offline workflow/provenance regression. Do not infer the tested revision solely from the PR head. A later authorized remote run must verify the downloaded manifest against its real checkout/run.

Authoritative behavior reference: [GitHub pull_request event and checkout semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request).

## Evidence/documentation gap

`docs/ci.md:84` and the new MEMORY entry cite fleet run9fcc8009-330f-4037-8863-b0084e6ca28f. That is precommit evidence at head6db6f46 with a different content fingerprint. A valid newer exact-head report exists at `.fleet/runs/EC-001/275a611b-9048-4f03-a07f-3b677b6482dc.json`: head484cf0d7, all8checks passed. Preserve the historical run, but distinguish it from final exact-head evidence in the durable coordinator handoff. This review did not reinterpret a dirty run as final-head evidence.

## Checks independently performed

Owned interpreter: `C:/Users/Maks/.prada-orchestrator/local-dev/night-20261023/ec-env/Scripts/python.exe`, Python3.12.1.

From the submitted worktree's evalcore directory:

- Verified evalcore and http_adapter module paths resolve inside this exact worktree.
- Verified jsonpath_ng.parse is jsonpath_ng.parser.parse. The import correction selects the same runtime function, without changing API/schema behavior.
- `python -m pytest tests/test_ci_gate.py tests/test_gate.py tests/test_cli.py tests/test_http_adapter.py -q -p no:cacheprovider`:33passed in3.62seconds.
- `python -m mypy --no-incremental --cache-dir <temporary-cache> evalcore`:passed,22source files.
- `python -m evalcore.cli run --config examples/toy/evalcore.yaml --out-dir <temporary-directory>`:exit0; real bounded JSON/Markdown reports produced; JSON3295bytes/5items; temporary outputs removed automatically.
- Inspected the actual six-file diff, frozen criteria, project check runner, all five retained fleet reports, workflow, fixtures, docs, and MEMORY. Existing assertions and frozen task/check metadata were not changed by this diff.

I did not rerun both complete component suites or all8checks. The exact-head author's fleet report records146EvalCore tests,34TicketPilot tests, both Ruff lint/format checks, both strict type checks,22gate/CLI tests plus toy execution, and workflow structure passing. Those are inspected author results, separate from my independently executed checks above.

## Criteria coverage and workflow assessment

- Actual pass/fail fixtures execute the real CLI compare path with a genuine gate config and explicit0/1exit assertions. Missing gate/baseline exits2 and strict config mismatch are exercised. Embedded deterministic fixture expectations are versioned source; no checked-in baseline was promoted.
- The toy-flow test's baseline update only writes a disposable temporary fixture, so it does not constitute automatic reviewed-baseline promotion.
- Component directories, pytest, Ruff check/format and strict mypy commands match the component projects. Python>=3.11 remains declared; actual local3.12 and earlier coordinator3.14 runs are distinguished. No fresh3.11/3.13 verification is claimed.
- Workflow triggers are pull_request and push to main; top-level and both job permissions are contents:read. Both jobs have15-minute timeouts; both uploads use reports/ paths and7-day retention. There is no pull_request_target, explicit provider secret use, baseline promotion, merge or deployment step.
- All three external actions have full40-character pins that resolve in the official action repositories: [checkout commit](https://github.com/actions/checkout/commit/d23441a48e516b6c34aea4fa41551a30e30af803), [setup-python pinned source](https://raw.githubusercontent.com/actions/setup-python/ece7cb06caefa5fff74198d8649806c4678c61a1/src/cache-distributions/pip-cache.ts), [upload-artifact commit](https://github.com/actions/upload-artifact/commit/b7c566a772e6b6bfb58ed0dc250532a479d7789f).
- The pinned setup-python cache implementation has a pyproject.toml fallback, so the lack of requirements.txt is not a demonstrated cache blocker. [Pinned fallback constant](https://raw.githubusercontent.com/actions/setup-python/ece7cb06caefa5fff74198d8649806c4678c61a1/src/cache-distributions/constants.ts).
- Uploads currently use default success conditions. Failed jobs may therefore retain no downloadable diagnostic artifact. This is a limitation, not an additional frozen-criteria blocker identified here.
- No real provider/database calls, key access, .env reads, source edits, queue decisions, push, workflow enabling, merge or deployment were performed by this review. Ordinary public official-source HTTP reads verified action pins and GitHub semantics.

## Next coordinator action

Prepare one bounded provenance correction from this pinned result, retain the original result/history and exact-head check report, then independently verify the corrected manifest/fixture behavior. Until that correction is reviewed, do not call EC001 fully accepted or remote-CI verified. Remote execution remains a separate authorized step after allowance checks; main-push evidence remains deferred to an authorized merge.
