# REVIEW-CHECKLIST.md — run before marking any feature DONE

## Code
- [ ] Full type hints; `mypy --strict` passes
- [ ] Pydantic models validate all external data (config, dataset, adapter responses)
- [ ] No business logic in route handlers / CLI entrypoints
- [ ] No new dependency without checking pyproject.toml and stating why
- [ ] No secrets in code or config files (env var names only)

## Tests
- [ ] New/changed logic has unit tests
- [ ] `make test` green locally
- [ ] evalcore tests use FakeJudge / mock transport — zero real LLM calls
- [ ] Failure paths tested (timeouts, bad JSON, missing fields), not only happy path

## Quality gates
- [ ] `make lint` green (ruff + format + mypy)
- [ ] Pre-commit hooks pass (never bypass without asking)
- [ ] Logs are structured JSON with request/run id where applicable

## Eval discipline (from M2 onward)
- [ ] Metric preconditions validated at config load
- [ ] Judge model + prompt version pinned and recorded in report
- [ ] Failures counted separately, never averaged in as zeros
- [ ] Baseline changes go through `evalcore baseline update` and are reviewed like code

## Docs & memory
- [ ] MEMORY.md updated (phase progress, decisions, next steps)
- [ ] README/agent_docs updated if commands or conventions changed
- [ ] Commit created at the milestone with a clear message
