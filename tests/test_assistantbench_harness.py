from agent_efficiency_bench.harnesses.assistantbench import (
    AssistantBenchEvaluator,
    evaluator_for_assistantbench_task,
    model_config_for_assistantbench_mode,
)
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, RunResult, RunTelemetry, SuccessCriteria


class FakeJudge:
    def __init__(self, success=True, quality_score=5.0):
        self.success = success
        self.quality_score = quality_score
        self.calls = []

    def judge(self, *, instruction, answer, citations):
        from agent_efficiency_bench.evaluators.llm_judge import LLMJudgeScore

        self.calls.append({"instruction": instruction, "answer": answer, "citations": citations})
        return LLMJudgeScore(success=self.success, quality_score=self.quality_score, reason="fake judge")


def make_task(raw=None):
    return BenchmarkTask(
        task_id="assistantbench__1",
        source="AssistantBench/AssistantBench",
        source_type="huggingface",
        category="web_research",
        instruction="Q?",
        environment={"type": "web"},
        complexity=Complexity(horizon="short"),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="structured_answer"),
        raw=raw or {},
    )


def make_result(task, answer="paris", citations=None):
    return RunResult(
        telemetry=RunTelemetry(
            run_id="r1",
            task_id=task.task_id,
            agent="a",
            model="m",
            success=False,
            quality_score=0.0,
            wall_clock_seconds=1.0,
            input_tokens=1,
            output_tokens=1,
            estimated_usd=0.0,
        ),
        output={"answer": answer, "citations": citations or []},
        trace_path="trace.jsonl",
    )


def test_assistantbench_uses_llm_judge_even_when_raw_answer_available():
    task = make_task(raw={"answer": "Paris"})
    judge = FakeJudge(success=True, quality_score=4.8)
    evaluator = evaluator_for_assistantbench_task(task, judge=judge)

    score = evaluator.evaluate(task, make_result(task, "Paris is the answer."))

    assert score.success is True
    assert score.quality_score == 4.8
    assert judge.calls[0]["instruction"] == "Q?"


def test_assistantbench_web_mode_configures_native_web_search_tool():
    config = model_config_for_assistantbench_mode("openai/gpt-5.4-nano", "openrouter_web_plugin")
    assert config.model == "openai/gpt-5.4-nano"
    assert config.tools == [{"type": "openrouter:web_search", "parameters": {"engine": "auto"}}]


def test_assistantbench_evaluator_dispatches_per_task_with_judge():
    task = make_task(raw={"answer": "Paris"})
    judge = FakeJudge(success=True)

    score = AssistantBenchEvaluator(judge=judge).evaluate(task, make_result(task, "paris"))

    assert score.success is True


def test_assistantbench_uses_llm_judge_instead_of_stale_structured_expected_metadata():
    task = make_task(raw={"expected": {"text_contains": ["Potash Markets"], "requires_citation": True}})
    result = make_result(task, "The current answer may no longer be Potash Markets.", ["https://example.com"])
    judge = FakeJudge(success=True, quality_score=4.2)

    score = AssistantBenchEvaluator(judge=judge).evaluate(task, result)

    assert score.success is True
    assert score.quality_score == 4.2
