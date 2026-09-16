"""FakeJudge: a deterministic, offline judge for tests (agent_docs/testing.md golden rule).

Scores by keyword overlap between the answer and the context — no network, no cost.
Underscore prefix => pytest won't collect this module.
"""

from evalcore.judge.base import JudgeRequest, JudgeResult


class FakeJudge:
    """Implements the Judge protocol structurally. Deterministic and free."""

    def __init__(self, version: str = "fake/fake@v0") -> None:
        self._version = version
        self.calls: list[JudgeRequest] = []

    @property
    def version(self) -> str:
        return self._version

    async def evaluate(self, request: JudgeRequest) -> JudgeResult:
        self.calls.append(request)
        answer_words = set(request.answer.lower().split())
        context_words = set(request.context.lower().split())
        if not answer_words:
            return JudgeResult(score=0.0, reason="empty answer")
        overlap = len(answer_words & context_words)
        score = overlap / len(answer_words)
        return JudgeResult(score=score, reason=f"keyword overlap {overlap}/{len(answer_words)}")
