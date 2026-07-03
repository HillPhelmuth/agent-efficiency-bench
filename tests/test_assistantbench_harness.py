from agent_efficiency_bench.harnesses.assistantbench import (
    AssistantBenchEvaluator,
    evaluator_for_assistantbench_task,
    model_config_for_assistantbench_mode,
)
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, RunResult, RunTelemetry, SuccessCriteria


def test_assistantbench_uses_raw_answer_when_available():
    task = BenchmarkTask(
        task_id="assistantbench__1",
        source="AssistantBench/AssistantBench",
        source_type="huggingface",
        category="web_research",
        instruction="Q?",
        environment={"type": "web"},
        complexity=Complexity(horizon="short"),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="structured_answer"),
        raw={"answer": "Paris"},
    )
    evaluator = evaluator_for_assistantbench_task(task)
    assert evaluator.evaluate_output({"answer": "paris"}).success is True


def test_assistantbench_exact_fallback_remains_when_expected_metadata_is_absent():
    task = BenchmarkTask(
        task_id="assistantbench__fallback",
        source="AssistantBench/AssistantBench",
        source_type="huggingface",
        category="web_research",
        instruction="Q?",
        environment={"type": "web"},
        complexity=Complexity(horizon="short"),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="structured_answer"),
        raw={"answer": "Paris"},
    )

    evaluator = evaluator_for_assistantbench_task(task)

    assert evaluator.evaluate_output({"answer": "paris"}).success is True


def test_assistantbench_web_mode_configures_native_web_search_tool():
    config = model_config_for_assistantbench_mode("openai/gpt-5.4-nano", "openrouter_web_plugin")
    assert config.model == "openai/gpt-5.4-nano"
    assert config.tools == [{"type": "openrouter:web_search", "parameters": {"engine": "native"}}]


def test_assistantbench_evaluator_dispatches_per_task():
    task = BenchmarkTask(
        task_id="assistantbench__1",
        source="AssistantBench/AssistantBench",
        source_type="huggingface",
        category="web_research",
        instruction="Q?",
        environment={"type": "web"},
        complexity=Complexity(horizon="short"),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="structured_answer"),
        raw={"answer": "Paris"},
    )
    result = RunResult(
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
        output={"answer": "paris"},
        trace_path="trace.jsonl",
    )
    assert AssistantBenchEvaluator().evaluate(task, result).success is True


def test_assistantbench_uses_structured_evaluator_when_expected_metadata_present():
    task = BenchmarkTask(
        task_id="assistantbench__structured",
        source="AssistantBench/AssistantBench",
        source_type="huggingface",
        category="web_research",
        instruction="Q?",
        environment={"type": "web"},
        complexity=Complexity(horizon="short"),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="structured_answer"),
        raw={"expected": {"text_contains": ["Potash Markets"], "requires_citation": True}},
    )
    result = RunResult(
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
        output={"answer": "Potash Markets", "citations": ["https://example.com"]},
        trace_path="trace.jsonl",
    )
    assert AssistantBenchEvaluator().evaluate(task, result).success is True
