from __future__ import annotations

import re
from typing import Any

from agent_efficiency_bench.evaluators.base import EvaluationScore


class NoOpEvaluator:
    def evaluate(self, task: Any, result: Any) -> EvaluationScore:
        return EvaluationScore(success=False, quality_score=0.0, reason="No evaluator configured")


class ExactAnswerEvaluator:
    def __init__(self, expected: str):
        self.expected = expected

    def evaluate(self, task: Any, result: Any) -> EvaluationScore:
        return self.evaluate_output(result.output)

    def evaluate_output(self, output: dict[str, Any]) -> EvaluationScore:
        actual = str(output.get("answer") or "")
        success = _normalize_text(actual) == _normalize_text(self.expected)
        return EvaluationScore(
            success=success,
            quality_score=1.0 if success else 0.0,
            reason="exact match" if success else "answer mismatch",
            details={"expected": self.expected, "actual": actual},
        )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())
