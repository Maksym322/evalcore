"""Unit tests for the pure RRF merge."""

from app.pipeline.retrieve import RRF_K, rrf_merge


def test_rrf_single_list_ranks_by_position() -> None:
    fused = rrf_merge([["a", "b", "c"]])
    assert fused["a"] > fused["b"] > fused["c"]
    assert fused["a"] == 1.0 / (RRF_K + 1)


def test_rrf_overlap_boosts_score() -> None:
    # "b" appears in both lists -> should outrank items appearing in only one.
    fused = rrf_merge([["a", "b"], ["b", "c"]])
    assert fused["b"] > fused["a"]
    assert fused["b"] > fused["c"]


def test_rrf_empty() -> None:
    assert rrf_merge([[], []]) == {}
