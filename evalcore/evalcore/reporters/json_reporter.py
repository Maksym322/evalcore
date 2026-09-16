"""JSON reporter: serialize a full RunReport as valid JSON (TechDesign §2.5).

Per-item failure scores are NaN, which is not legal JSON, so non-finite floats are
rendered as ``null``. This makes the artifact a valid read/compare file (not a lossless
round-trip back into a RunReport); the failure reason stays in each item's ``details``.
"""

import json
import math
from typing import Any

from evalcore.schema import RunReport


def _sanitize(value: Any) -> Any:
    """Recursively replace non-finite floats (NaN, ±inf) with None."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


def render_json(report: RunReport, *, indent: int = 2) -> str:
    """Render the full RunReport as a valid JSON string (NaN scores -> null)."""
    data = _sanitize(report.model_dump(mode="json"))
    return json.dumps(data, indent=indent, allow_nan=False)
