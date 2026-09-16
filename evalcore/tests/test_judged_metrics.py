"""Tests for the judged metrics (FakeJudge + a RaisingJudge — all offline)."""

import pytest

from evalcore.config import ConfigError
from evalcore.judge.base import JudgeError, JudgeRequest, JudgeResult
from evalcore.metrics.base import build, is_failure
from evalcore.schema import DatasetItem, Reference, TargetOutput
from tests._fake_judge import FakeJudge


class RaisingJudge:
    version = "raise/raise@v0"

    async def evaluate(self, request: JudgeRequest) -> JudgeResult:
        raise JudgeError("boom")


def _item(*, question: str | None = None, ref_answer: str | None = None) -> DatasetItem:
    inp: dict[str, object] = {}
    if question is not None:
        inp["question"] = question
    return DatasetItem(id="i1", input=inp, reference=Reference(answer=ref_answer))


# ---- faithfulness ----------------------------------------------------------


async def test_faithfulness_scores_via_judge() -> None:
    m = build("faithfulness", {}, judge=FakeJudge())
    out = TargetOutput(answer="reset password", retrieved_context=["how to reset your password"])
    r = await m.score(_item(), out)
    assert r.score == 1.0  # overlap of both answer words
    assert r.details["judge_version"] == "fake/fake@v0"


async def test_faithfulness_missing_context_is_nan() -> None:
    m = build("faithfulness", {}, judge=FakeJudge())
    r = await m.score(_item(), TargetOutput(answer="x", retrieved_context=None))
    assert is_failure(r.score)
    assert "retrieved_context" in r.details["error"]


# ---- answer_relevance ------------------------------------------------------


async def test_answer_relevance_scores_via_judge() -> None:
    m = build("answer_relevance", {}, judge=FakeJudge())
    out = TargetOutput(answer="alpha beta")
    r = await m.score(_item(question="alpha only"), out)
    assert r.score == 0.5


async def test_answer_relevance_missing_question_is_nan() -> None:
    m = build("answer_relevance", {}, judge=FakeJudge())
    r = await m.score(_item(question=None), TargetOutput(answer="x"))
    assert is_failure(r.score)
    assert "question" in r.details["error"]


# ---- custom_judged ---------------------------------------------------------


async def test_custom_judged_substitutes_slots(tmp_path) -> None:  # type: ignore[no-untyped-def]
    prompt_file = tmp_path / "p.txt"
    prompt_file.write_text("Q={input} A={answer} R={reference}", encoding="utf-8")
    fake = FakeJudge()
    m = build("custom_judged", {"prompt_file": str(prompt_file)}, judge=fake)
    out = TargetOutput(answer="myanswer")
    await m.score(_item(ref_answer="goldenref"), out)

    sent = fake.calls[0].prompt
    assert "A=myanswer" in sent
    assert "R=goldenref" in sent
    assert "{answer}" not in sent and "{reference}" not in sent  # slots replaced


def test_custom_judged_missing_file_is_config_error() -> None:
    with pytest.raises(ConfigError):
        build("custom_judged", {"prompt_file": "does_not_exist.txt"}, judge=FakeJudge())


def test_custom_judged_empty_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    with pytest.raises(ConfigError):
        build("custom_judged", {"prompt_file": str(empty)}, judge=FakeJudge())


# ---- judge error + registry ------------------------------------------------


async def test_judge_error_becomes_nan_failure() -> None:
    m = build("faithfulness", {}, judge=RaisingJudge())
    out = TargetOutput(answer="x", retrieved_context=["y"])
    r = await m.score(_item(), out)
    assert is_failure(r.score)
    assert r.details["judge_error"] == "boom"
    assert r.details["judge_version"] == "raise/raise@v0"


def test_judged_without_judge_raises() -> None:
    with pytest.raises(ConfigError) as exc:
        build("faithfulness", {})
    assert "requires a judge" in str(exc.value)


def test_deterministic_build_ignores_judge() -> None:
    # Passing a judge to a deterministic metric is harmless (ignored).
    m = build("latency_budget", {"max_ms": 100}, judge=FakeJudge())
    assert m.kind == "deterministic"


def test_judged_metric_kind() -> None:
    m = build("answer_relevance", {}, judge=FakeJudge())
    assert m.kind == "judged"
