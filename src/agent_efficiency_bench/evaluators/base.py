from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from agent_efficiency_bench.scoring import LIKERT_SCORE_MAX, UNEVALUATED_QUALITY_SCORE
from agent_efficiency_bench.schemas import BenchmarkTask, RunResult


class EvaluationScore(BaseModel):
    evaluated: bool = True
    success: bool
    quality_score: float = Field(ge=UNEVALUATED_QUALITY_SCORE, le=LIKERT_SCORE_MAX)
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Evaluator(Protocol):
    def evaluate(self, task: BenchmarkTask, result: RunResult) -> EvaluationScore: ...
