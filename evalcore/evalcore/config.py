"""Config loader: parse ``evalcore.yaml`` into a typed RunConfig (TechDesign §2.2-2.5, §3.5).

Unknown keys are rejected (``extra="forbid"``) and surfaced through ``load_config`` as
a ``ConfigError`` with a readable, multi-line message.
"""

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ConfigError(Exception):
    """Raised when an ``evalcore.yaml`` cannot be read or fails validation."""


class JudgeConfig(BaseModel):
    """Judge pinning for a judged metric. Parsed in M1; consumed by the judge client in M2."""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["anthropic", "openai", "gemini"]
    model: str
    prompt: str = "default"


class MetricConfig(BaseModel):
    """One selected metric: a registry name plus deterministic params and/or judge pinning."""

    model_config = ConfigDict(extra="forbid")

    name: str
    # ``Any`` by design: metric params are metric-specific (e.g. {"k": 5}, {"label": "category"}).
    params: dict[str, Any] = {}
    judge: JudgeConfig | None = None


class PythonAdapterConfig(BaseModel):
    """In-process callable adapter (dotted path ``pkg.mod:fn``)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["python"]
    callable: str


class HttpAdapterConfig(BaseModel):
    """POST-an-endpoint adapter with JSONPath response mapping.

    ``url`` may contain ``${ENV_VAR}`` references. Auth uses the env var *name* only —
    the secret never lives in config. ``map`` keys are TargetOutput fields.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["http"]
    url: str
    map: dict[str, str] = {}
    auth_header_env: str | None = None
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    timeout: float = 30.0
    max_retries: int = 3


class N8nWebhookAdapterConfig(HttpAdapterConfig):
    """HttpAdapter specialization for n8n webhooks (array-unwrap + default map presets)."""

    type: Literal["n8n_webhook"]  # type: ignore[assignment]


# Discriminated on ``type``; N8n resolves before Http because it is a subclass.
AdapterConfig = Annotated[
    PythonAdapterConfig | HttpAdapterConfig | N8nWebhookAdapterConfig,
    Field(discriminator="type"),
]


class GateRule(BaseModel):
    """A single regression rule the gate enforces vs a baseline (executed in a later milestone)."""

    model_config = ConfigDict(extra="forbid")

    metric: str
    max_drop_pct: float
    min_value: float | None = None


class GateConfig(BaseModel):
    """Baseline reference and the rules compared against it. Parsed in M1; executed later."""

    model_config = ConfigDict(extra="forbid")

    baseline: str
    rules: list[GateRule] = []


class SmokeSubset(BaseModel):
    """Filter selecting a cheap PR-time subset of the dataset."""

    model_config = ConfigDict(extra="forbid")

    tags: list[str] = []
    max_items: int


class RunSettings(BaseModel):
    """Determinism and concurrency knobs (defaults per TechDesign §3.5)."""

    model_config = ConfigDict(extra="forbid")

    concurrency: int = 8
    seed: int = 42
    temperature: float = 0.0
    smoke_subset: SmokeSubset | None = None


class RunConfig(BaseModel):
    """The per-project 'model': adapter + dataset + metrics + optional gate + run knobs."""

    model_config = ConfigDict(extra="forbid")

    project: str
    adapter: AdapterConfig
    dataset: str  # path to the JSONL dataset
    metrics: list[MetricConfig] = Field(min_length=1)
    gate: GateConfig | None = None
    run: RunSettings = Field(default_factory=RunSettings)


def _format_validation_error(path: Path, err: ValidationError) -> str:
    lines = [f"Invalid config ({path}):"]
    for e in err.errors():
        loc = ".".join(str(part) for part in e["loc"]) or "(root)"
        lines.append(f"  - {loc}: {e['msg']}")
    return "\n".join(lines)


def load_config(path: str | Path) -> RunConfig:
    """Load, parse, and validate an ``evalcore.yaml`` into a :class:`RunConfig`.

    Raises :class:`ConfigError` (never a raw ValidationError/OSError) with a clear message.
    """
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ConfigError(f"Config file not found: {p}") from e
    except OSError as e:  # pragma: no cover - unusual FS errors
        raise ConfigError(f"Could not read config ({p}): {e}") from e

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML ({p}): {e}") from e

    if data is None:
        raise ConfigError(f"Config file is empty: {p}")
    if not isinstance(data, dict):
        raise ConfigError(f"Config root must be a mapping ({p}), got {type(data).__name__}")

    try:
        return RunConfig.model_validate(data)
    except ValidationError as e:
        raise ConfigError(_format_validation_error(p, e)) from e
