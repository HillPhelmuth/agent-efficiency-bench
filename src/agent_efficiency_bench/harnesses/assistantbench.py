from __future__ import annotations

from agent_efficiency_bench.evaluators.simple import ExactAnswerEvaluator, NoOpEvaluator
from agent_efficiency_bench.schemas import BenchmarkTask


def evaluator_for_assistantbench_task(task: BenchmarkTask):
    answer = task.raw.get("answer")
    if answer is not None and str(answer).strip():
        return ExactAnswerEvaluator(expected=str(answer))
    return NoOpEvaluator()


def openrouter_extra_for_mode(mode: str) -> dict:
    if mode == "closed_book":
        return {}
    if mode == "openrouter_web_plugin":
        return {"plugins": [{"id": "web"}]}
    raise ValueError(f"unsupported AssistantBench mode: {mode}")
