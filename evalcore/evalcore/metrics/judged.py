"""Built-in judged metrics (TechDesign §2.3-2.4). Registered on import.

Each metric renders a grading prompt, delegates to an injected Judge, and records the judge
version in ``details["judge_version"]``. A JudgeError becomes a NaN failure with
``details["judge_error"]``; genuinely missing inputs become NaN without a judge call.
Prompts are built with f-strings + a constant JSON instruction so literal ``{`` in the
JSON contract is never treated as a format field.
"""

import json
from pathlib import Path
from typing import Any

from evalcore.judge.base import Judge, JudgeError, JudgeRequest
from evalcore.metrics.base import FAILURE_SCORE, Metric, register
from evalcore.schema import DatasetItem, MetricResult, TargetOutput

_JSON_INSTRUCTION = 'Respond with ONLY a JSON object: {"score": <number 0..1>, "reason": <string>}.'


class _JudgedMetric(Metric):
    """Shared plumbing for judged metrics: holds the Judge and standardizes result-building."""

    kind = "judged"

    def __init__(self, judge: Judge) -> None:
        super().__init__()
        self.judge = judge

    def _ok(self, item_id: str, score: float, **details: Any) -> MetricResult:
        return self._result(item_id, score, judge_version=self.judge.version, **details)

    def _fail_judged(self, item_id: str, **details: Any) -> MetricResult:
        return self._result(item_id, FAILURE_SCORE, judge_version=self.judge.version, **details)

    async def _judge_call(
        self, item_id: str, prompt: str, answer: str, context: str
    ) -> MetricResult:
        request = JudgeRequest(item_id=item_id, prompt=prompt, answer=answer, context=context)
        try:
            result = await self.judge.evaluate(request)
        except JudgeError as e:
            return self._fail_judged(item_id, judge_error=str(e))
        return self._ok(item_id, result.score, reason=result.reason)


@register
class Faithfulness(_JudgedMetric):
    name = "faithfulness"

    def __init__(self, *, judge: Judge) -> None:
        super().__init__(judge)
        self.requires = {"answer", "retrieved_context"}

    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult:
        if out.retrieved_context is None:
            return self._fail_judged(item.id, error="retrieved_context not produced")
        context = "\n\n".join(out.retrieved_context)
        prompt = (
            "You are grading whether the ANSWER is faithful to (supported by) the CONTEXT.\n\n"
            f"CONTEXT:\n{context}\n\nANSWER:\n{out.answer}\n\n"
            "Score 1.0 if every claim is supported by the context, 0.0 if contradicted or "
            "unsupported.\n" + _JSON_INSTRUCTION
        )
        return await self._judge_call(item.id, prompt, out.answer, context)


@register
class AnswerRelevance(_JudgedMetric):
    name = "answer_relevance"

    def __init__(self, *, judge: Judge) -> None:
        super().__init__(judge)
        self.requires = {"answer"}

    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult:
        question = item.input.get("question")
        if not isinstance(question, str) or not question:
            return self._fail_judged(item.id, error="input.question missing")
        prompt = (
            "You are grading whether the ANSWER is relevant to the QUESTION.\n\n"
            f"QUESTION:\n{question}\n\nANSWER:\n{out.answer}\n\n"
            "Score 1.0 if the answer directly addresses the question, 0.0 if off-topic.\n"
            + _JSON_INSTRUCTION
        )
        return await self._judge_call(item.id, prompt, out.answer, question)


@register
class CustomJudged(_JudgedMetric):
    name = "custom_judged"

    def __init__(self, *, judge: Judge, prompt_file: str, prompt_version: str = "v1") -> None:
        super().__init__(judge)
        try:
            template = Path(prompt_file).read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError(f"prompt_file not readable ({prompt_file!r}): {e}") from e
        if not template.strip():
            raise ValueError(f"prompt_file is empty: {prompt_file!r}")
        self._template = template
        self._prompt_version = prompt_version
        self.requires = {"answer"}

    async def score(self, item: DatasetItem, out: TargetOutput) -> MetricResult:
        input_str = json.dumps(item.input, ensure_ascii=False, sort_keys=True)
        reference = item.reference.answer or ""
        prompt = (
            self._template.replace("{input}", input_str)
            .replace("{answer}", out.answer)
            .replace("{reference}", reference)
            + "\n"
            + _JSON_INSTRUCTION
        )
        # Fold the template into the cache context so editing the prompt file invalidates cache.
        context = "\x1f".join([self._template, input_str, reference])
        return await self._judge_call(item.id, prompt, out.answer, context)
