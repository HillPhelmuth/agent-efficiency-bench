from __future__ import annotations

from agent_efficiency_bench.evaluators.llm_judge import LLMAnswerJudgeEvaluator
from agent_efficiency_bench.schemas import BenchmarkTask, ModelConfig


def native_web_search_tool(engine: str = "auto") -> dict:
    return {
        "type": "openrouter:web_search",
        "parameters": {"engine": engine},
    }


def evaluator_for_assistantbench_task(task: BenchmarkTask, *, judge=None):
    return LLMAnswerJudgeEvaluator(judge=judge)


class AssistantBenchEvaluator:
    def __init__(self, judge=None):
        self.judge = judge

    def evaluate(self, task, result):
        return evaluator_for_assistantbench_task(task, judge=self.judge).evaluate(task, result)


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
