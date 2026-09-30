# EvalCore

Universal, project-agnostic evaluation framework for LLM systems.

**Status:** M1/M2 framework and offline tests are implemented. The runner supports
Python/HTTP adapters, deterministic and judged metrics, reports, resumable journals,
and regression gates. TicketPilot is the first consumer, but no verified golden dataset,
baseline, or CI gate has been published yet.

## Development

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
make dev                                          # pip install -e ".[dev]"
make test                                         # pytest
make lint                                         # ruff + mypy --strict
```

Run a config from its project working directory with
`python -m evalcore.cli run --config evalcore.yaml --out-dir runs/latest`.
Judged metrics require an explicit `judge` pin, for example:

```yaml
- name: faithfulness
  judge: {provider: gemini, model: gemini-3.5-flash-lite, prompt: v1}
```

The runner records `judge_versions` in the report and caches verdicts under the run
directory. Set `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` in the shell
for the selected provider. Offline tests inject `FakeJudge` and never call real APIs.
Using the same model family for target and judge is suitable for smoke testing, but
human-reviewed examples and an independent judge are needed for a trustworthy gate.
