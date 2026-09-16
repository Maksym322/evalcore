# Code Patterns

> The three load-bearing patterns of this codebase. Copy them; don't invent parallel ones.

## 1. Adapter pattern (universality core)

Any system we want to evaluate is a `Target`. EvalCore never knows what's behind it.

```python
# evalcore/adapters/base.py
class Target(Protocol):
    async def respond(self, item: DatasetItem) -> TargetOutput: ...

# evalcore/adapters/http_adapter.py — config-driven, JSONPath mapping
class HttpAdapter:
    def __init__(self, url: str, map: dict[str, str], auth_header_env: str | None = None,
                 timeout: float = 30.0):
        self._client = httpx.AsyncClient(timeout=timeout)
        ...
    async def respond(self, item: DatasetItem) -> TargetOutput:
        t0 = time.perf_counter()
        r = await self._post_with_retry({"id": item.id, "input": item.input})
        out = apply_jsonpath_map(r.json(), self.map)          # -> answer, retrieved_*
        out.metadata["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return out
```

Rules: new target types = new adapter file, nothing else changes. Auth = env var NAME in config, value read at runtime. Latency measured by the adapter, always.

## 2. Registry pattern (metrics)

```python
# evalcore/metrics/base.py
_REGISTRY: dict[str, type[Metric]] = {}

def register(cls: type[Metric]) -> type[Metric]:
    _REGISTRY[cls.name] = cls
    return cls

def build(name: str, params: dict) -> Metric:
    if name not in _REGISTRY:
        raise ConfigError(f"Unknown metric '{name}'. Available: {sorted(_REGISTRY)}")
    return _REGISTRY[name](**params)
```

Config selects by string name; `build()` fails loudly with the available list. Precondition check right after: every `metric.requires` field must be producible by the adapter+dataset, else abort BEFORE any API spend. (Entry-point discovery for third-party metrics: NOT until M6.)

## 3. Journal / resumability pattern (runner)

```python
# append-only; one JSON line per completed item
journal.write_line({"item_id": item.id, "output": out.model_dump(),
                    "results": [r.model_dump() for r in results]})
# --resume {run_id}: load journal, skip completed ids, continue
```

Never buffer a whole run in memory only. A rate-limit death at item 70/80 must cost 10 items, not 80.

## TicketPilot pipeline stage pattern

Each stage is a pure-ish async function: input model → output model, logs its own duration, raises typed errors.

```python
async def classify(body: str, *, llm: LLM, log: BoundLogger) -> TicketClass:
    with stage_timer(log, "classify"):
        raw = await llm.structured(CLASSIFY_PROMPT, body, schema=TicketClass)
        return raw  # already validated by Pydantic; repair-retry inside llm.structured
```

Routes only orchestrate: `classify → retrieve → generate → escalate`, persist, return DTO. No SQL, no prompts in route files.

## Prompt handling
- Prompts live in `prompts/*.md` files, versioned; never inline f-strings in logic modules.
- Every judged metric records `provider/model@prompt_version` into the report.

## Anti-patterns (reject on sight)
- `except Exception: pass`
- Averaging failed items as 0.0 into metric means
- Comparing runs with different config hashes without a warning
- Adding a "small helper framework" around the framework
