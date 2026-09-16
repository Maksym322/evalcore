"""Tests for the judge disk cache and cache-key semantics (TechDesign §2.4)."""

from pathlib import Path

from evalcore.judge.base import JudgeResult
from evalcore.judge.cache import JudgeCache, cache_key, context_digest


def _key(**overrides: str) -> str:
    args = {
        "model": "m1",
        "prompt_version": "v1",
        "item_id": "i1",
        "answer": "hello world",
        "ctx_digest": context_digest("some context"),
    }
    args.update(overrides)
    return cache_key(**args)  # type: ignore[arg-type]


def test_cache_miss_returns_none(tmp_path: Path) -> None:
    cache = JudgeCache(tmp_path)
    assert cache.get("nope") is None


def test_cache_set_then_get(tmp_path: Path) -> None:
    cache = JudgeCache(tmp_path)
    result = JudgeResult(score=0.8, reason="good")
    cache.set("k1", result)
    got = cache.get("k1")
    assert got == result


def test_cache_key_changes_with_model() -> None:
    assert _key(model="m1") != _key(model="m2")


def test_cache_key_changes_with_prompt_version() -> None:
    assert _key(prompt_version="v1") != _key(prompt_version="v2")


def test_cache_key_stable_for_same_inputs() -> None:
    assert _key() == _key()


def test_context_digest_deterministic() -> None:
    assert context_digest("abc") == context_digest("abc")
    assert context_digest("abc") != context_digest("abd")


def test_corrupt_cache_file_is_a_miss(tmp_path: Path) -> None:
    cache = JudgeCache(tmp_path)
    (tmp_path / "bad.json").write_text("{ not json", encoding="utf-8")
    assert cache.get("bad") is None
