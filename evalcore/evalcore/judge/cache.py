"""Content-hash disk cache for judge verdicts (TechDesign §2.4).

Cache key = sha256(model + prompt_version + item_id + answer + context_digest). Because the
model and prompt_version are in the key, changing either invalidates automatically. Safe
because judging runs at temperature 0 and inputs are content-addressed.
"""

import hashlib
from pathlib import Path

from evalcore.judge.base import JudgeResult

_SEP = "\x1f"  # unit separator: avoids field-boundary collisions


def context_digest(context: str) -> str:
    return hashlib.sha256(context.encode("utf-8")).hexdigest()


def cache_key(
    *, model: str, prompt_version: str, item_id: str, answer: str, ctx_digest: str
) -> str:
    raw = _SEP.join([model, prompt_version, item_id, answer, ctx_digest])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class JudgeCache:
    """Read/write JudgeResults as ``{dir}/{key}.json``. Missing or corrupt file => miss."""

    def __init__(self, directory: str | Path = ".evalcore_cache") -> None:
        self.dir = Path(directory)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> JudgeResult | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return JudgeResult.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # corrupt/unreadable => treat as a miss

    def set(self, key: str, result: JudgeResult) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self._path(key).write_text(result.model_dump_json(), encoding="utf-8")
