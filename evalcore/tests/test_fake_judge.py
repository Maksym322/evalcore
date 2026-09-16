"""Tests for the FakeJudge test double (deterministic, offline)."""

from evalcore.judge.base import Judge, JudgeRequest
from tests._fake_judge import FakeJudge


async def test_fake_judge_scores_by_overlap() -> None:
    judge = FakeJudge()
    req = JudgeRequest(
        item_id="i1",
        prompt="p",
        answer="reset password",
        context="how to reset your password",
    )
    result = await judge.evaluate(req)
    assert result.score == 1.0  # both answer words appear in context


async def test_fake_judge_partial_overlap() -> None:
    judge = FakeJudge()
    req = JudgeRequest(item_id="i1", prompt="p", answer="alpha beta", context="alpha only")
    result = await judge.evaluate(req)
    assert result.score == 0.5


async def test_fake_judge_empty_answer() -> None:
    judge = FakeJudge()
    result = await judge.evaluate(JudgeRequest(item_id="i1", prompt="p", answer="", context="x"))
    assert result.score == 0.0


async def test_fake_judge_records_calls_and_version() -> None:
    judge: Judge = FakeJudge(version="fake/test@v1")  # structural protocol conformance
    assert judge.version == "fake/test@v1"
    await judge.evaluate(JudgeRequest(item_id="i9", prompt="p", answer="a", context="c"))
    assert isinstance(judge, FakeJudge)
    assert judge.calls[0].item_id == "i9"
