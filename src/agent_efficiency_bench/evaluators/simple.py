from __future__ import annotations

import re
from typing import Any

from agent_efficiency_bench.evaluators.base import EvaluationScore
from agent_efficiency_bench.scoring import UNEVALUATED_QUALITY_SCORE, likert_score


class UnevaluatedEvaluator:
    def __init__(self, reason: str = "No evaluator configured", details: dict[str, Any] | None = None):
        self.reason = reason
        self.details = details or {}

    def evaluate(self, task: Any, result: Any) -> EvaluationScore:
        return EvaluationScore(
            evaluated=False,
            success=False,
            quality_score=UNEVALUATED_QUALITY_SCORE,
            reason=self.reason,
            details=self.details,
        )


class NoOpEvaluator(UnevaluatedEvaluator):
    def evaluate(self, task: Any, result: Any) -> EvaluationScore:
        return super().evaluate(task=task, result=result)


class ExactAnswerEvaluator:
    def __init__(self, expected: str):
        self.expected = expected

    def evaluate(self, task: Any, result: Any) -> EvaluationScore:
        return self.evaluate_output(result.output)

    def evaluate_output(self, output: dict[str, Any]) -> EvaluationScore:
        actual = str(output.get("answer") or "")
        success = _normalize_text(actual) == _normalize_text(self.expected)
        return EvaluationScore(
            evaluated=True,
            success=success,
            quality_score=likert_score(success),
            reason="exact match" if success else "answer mismatch",
            details={"expected": self.expected, "actual": actual},
        )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())
