from __future__ import annotations

from agent_efficiency_bench.evaluators.structured import StructuredAnswerEvaluator
from agent_efficiency_bench.evaluators.simple import ExactAnswerEvaluator, UnevaluatedEvaluator
from agent_efficiency_bench.schemas import BenchmarkTask, ModelConfig


def native_web_search_tool(engine: str = "auto") -> dict:
    return {
        "type": "openrouter:web_search",
        "parameters": {"engine": engine},
    }


def evaluator_for_assistantbench_task(task: BenchmarkTask):
    expected = task.raw.get("expected")
    if isinstance(expected, dict):
        return StructuredAnswerEvaluator(expected)
    answer = task.raw.get("answer")
    if answer is not None and str(answer).strip():
        return ExactAnswerEvaluator(expected=str(answer))
    return UnevaluatedEvaluator(reason="AssistantBench task is missing expected metadata")


class AssistantBenchEvaluator:
    def evaluate(self, task, result):
        return evaluator_for_assistantbench_task(task).evaluate(task, result)


def model_config_for_assistantbench_mode(model: str, mode: str, max_completion_tokens: int = 2048) -> ModelConfig:
    if mode == "closed_book":
        return ModelConfig(model=model, max_completion_tokens=max_completion_tokens)
    if mode == "openrouter_web_plugin":
        return ModelConfig(
            model=model,
            max_completion_tokens=max_completion_tokens,
            tools=[native_web_search_tool()],
        )
    raise ValueError(f"unsupported AssistantBench mode: {mode}")
