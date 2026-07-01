from __future__ import annotations

from agent_efficiency_bench.evaluators.simple import ExactAnswerEvaluator, NoOpEvaluator
from agent_efficiency_bench.schemas import BenchmarkTask, ModelConfig


def native_web_search_tool(engine: str = "native") -> dict:
    return {
        "type": "openrouter:web_search",
        "parameters": {"engine": engine},
    }


def evaluator_for_assistantbench_task(task: BenchmarkTask):
    answer = task.raw.get("answer")
    if answer is not None and str(answer).strip():
        return ExactAnswerEvaluator(expected=str(answer))
    return NoOpEvaluator()


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
