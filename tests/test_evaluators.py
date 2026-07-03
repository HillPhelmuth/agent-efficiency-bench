from agent_efficiency_bench.evaluators.registry import OfficialHarnessResultEvaluator, RegistryEvaluator, evaluator_for_task
from agent_efficiency_bench.evaluators.simple import ExactAnswerEvaluator, NoOpEvaluator, UnevaluatedEvaluator
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, RunResult, RunTelemetry, SuccessCriteria


def test_noop_evaluator_leaves_run_unsuccessful():
    score = NoOpEvaluator().evaluate(task=None, result=None)
    assert score.evaluated is False
    assert score.success is False
    assert score.quality_score == 0.0


def test_exact_answer_evaluator_normalizes_case_and_space():
    evaluator = ExactAnswerEvaluator(expected="New York City")
    score = evaluator.evaluate_output({"answer": " new   york city "})
    assert score.success is True
    assert score.quality_score == 1.0


def make_task(task_id: str, source: str, category: str, success_type: str, raw: dict | None = None, checker: str | None = None):
    return BenchmarkTask(
        task_id=task_id,
        source=source,
        source_type="custom",
        category=category,
        instruction="Do the task.",
        environment={"type": "test"},
        complexity=Complexity(horizon="short"),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type=success_type, checker=checker),
        raw=raw or {},
    )


def make_result(task_id: str, output: dict | None = None):
    return RunResult(
        telemetry=RunTelemetry(
            run_id=f"{task_id}-run",
            task_id=task_id,
            agent="agent",
            model="model",
            success=False,
            quality_score=0.0,
            wall_clock_seconds=1.0,
            input_tokens=1,
            output_tokens=1,
            estimated_usd=0.0,
        ),
        output=output or {"answer": "Paris"},
        trace_path="trace.jsonl",
    )


def test_registry_uses_assistantbench_evaluator():
    task = make_task(
        "assistantbench__1",
        "AssistantBench/AssistantBench",
        "web_research",
        "structured_answer",
        raw={"answer": "Paris"},
    )

    score = RegistryEvaluator().evaluate(task, make_result(task.task_id, {"answer": "paris"}))

    assert score.evaluated is True
    assert score.success is True


def test_registry_uses_unevaluated_evaluator_for_missing_manual_path():
    task = make_task("manual__1", "manual", "web_research", "manual")

    evaluator = evaluator_for_task(task)

    assert isinstance(evaluator, UnevaluatedEvaluator)
    assert evaluator.evaluate(task, make_result(task.task_id)).evaluated is False


def test_registry_marks_swe_bench_unevaluated_without_harness_result():
    task = make_task(
        "swe_bench_lite__1",
        "SWE-bench/SWE-bench_Lite",
        "software_engineering",
        "unit_tests",
        checker="swebench_harness",
    )

    score = RegistryEvaluator().evaluate(task, make_result(task.task_id))

    assert score.evaluated is False
    assert score.reason == "Official harness result required for SWE-bench/SWE-bench_Lite"


def test_registry_reads_official_harness_result_when_present():
    evaluator = OfficialHarnessResultEvaluator("terminal_bench_harness", "harbor-framework/terminal-bench")

    score = evaluator.evaluate(
        make_task("terminal_bench__1", "harbor-framework/terminal-bench", "terminal_work", "container_tests"),
        make_result("terminal_bench__1", {"harness_result": {"success": True, "quality_score": 1.0, "reason": "passed"}}),
    )

    assert score.evaluated is True
    assert score.success is True
    assert score.reason == "passed"


def test_registry_marks_terminal_bench_unevaluated_without_harness_result():
    task = make_task(
        "terminal_bench__1",
        "harbor-framework/terminal-bench",
        "terminal_work",
        "container_tests",
        checker="terminal_bench_harness",
    )

    score = RegistryEvaluator().evaluate(task, make_result(task.task_id))

    assert score.evaluated is False
    assert score.reason == "Official harness result required for harbor-framework/terminal-bench"


def test_registry_marks_tau2_unevaluated_without_harness_result():
    task = make_task(
        "tau2_bench_retail__1",
        "sierra-research/tau2-bench",
        "tool_workflow",
        "tau2_actions",
        checker="tau2_harness",
    )

    score = RegistryEvaluator().evaluate(task, make_result(task.task_id))

    assert score.evaluated is False
