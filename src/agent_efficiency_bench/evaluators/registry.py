from __future__ import annotations

from agent_efficiency_bench.evaluators.base import EvaluationScore
from agent_efficiency_bench.evaluators.simple import ExactAnswerEvaluator, UnevaluatedEvaluator
from agent_efficiency_bench.evaluators.structured import StructuredAnswerEvaluator
from agent_efficiency_bench.harnesses.assistantbench import AssistantBenchEvaluator
from agent_efficiency_bench.scoring import coerce_quality_score
from agent_efficiency_bench.schemas import BenchmarkTask, RunResult


class OfficialHarnessResultEvaluator:
    def __init__(self, checker_name: str, source: str):
        self.checker_name = checker_name
        self.source = source

    def evaluate(self, task: BenchmarkTask, result: RunResult) -> EvaluationScore:
        harness_result = result.output.get("harness_result")
        if not isinstance(harness_result, dict):
            return UnevaluatedEvaluator(
                reason=f"Official harness result required for {self.source}",
                details={"checker": self.checker_name, "task_id": task.task_id},
            ).evaluate(task, result)

        success = _harness_success(harness_result)
        quality_score = coerce_quality_score(harness_result.get("quality_score"), success=success)
        details = dict(harness_result.get("details") or {})
        if "raw" in harness_result:
            details.setdefault("raw", harness_result["raw"])
        return EvaluationScore(
            evaluated=True,
            success=success,
            quality_score=quality_score,
            reason=str(harness_result.get("reason") or f"{self.checker_name} harness result"),
            details=details,
        )


class RegistryEvaluator:
    def evaluate(self, task: BenchmarkTask, result: RunResult) -> EvaluationScore:
        return evaluator_for_task(task).evaluate(task, result)


def evaluator_for_task(task: BenchmarkTask):
    if task.source == "AssistantBench/AssistantBench":
        return AssistantBenchEvaluator()

    if task.success_criteria.type == "structured_answer":
        expected = task.raw.get("expected")
        if isinstance(expected, dict):
            return StructuredAnswerEvaluator(expected)
        answer = task.raw.get("answer")
        if answer is not None and str(answer).strip():
            return ExactAnswerEvaluator(expected=str(answer))
        return UnevaluatedEvaluator(
            reason="Structured-answer task is missing expected metadata",
            details={"task_id": task.task_id, "source": task.source},
        )

    if task.success_criteria.type == "exact":
        answer = task.raw.get("answer")
        if answer is not None and str(answer).strip():
            return ExactAnswerEvaluator(expected=str(answer))
        return UnevaluatedEvaluator(
            reason="Exact-answer task is missing answer metadata",
            details={"task_id": task.task_id, "source": task.source},
        )

    if _requires_official_harness(task):
        return OfficialHarnessResultEvaluator(
            checker_name=task.success_criteria.checker or task.success_criteria.type,
            source=task.source,
        )

    return UnevaluatedEvaluator(
        reason="No evaluator available for task",
        details={
            "task_id": task.task_id,
            "source": task.source,
            "success_criteria_type": task.success_criteria.type,
        },
    )


def _requires_official_harness(task: BenchmarkTask) -> bool:
    return (
        task.source in {"SWE-bench/SWE-bench_Lite", "harbor-framework/terminal-bench", "sierra-research/tau2-bench"}
        or task.success_criteria.type in {"unit_tests", "container_tests", "tau2_actions"}
        or task.success_criteria.checker in {"swebench_harness", "terminal_bench_harness", "tau2_harness"}
    )


def _harness_success(harness_result: dict) -> bool:
    if "success" in harness_result:
        return bool(harness_result["success"])
    if "resolved" in harness_result:
        return bool(harness_result["resolved"])
    status = str(harness_result.get("status") or "").strip().lower()
    return status in {"success", "passed", "resolved"}