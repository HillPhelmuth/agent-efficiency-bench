import pytest
from pydantic import ValidationError

from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, SuccessCriteria


def test_task_schema_computes_default_budgets_and_preserves_source():
    task = BenchmarkTask(
        task_id="swe_lite__abc",
        source="SWE-bench/SWE-bench_Lite",
        source_type="huggingface",
        category="software_engineering",
        instruction="Fix the failing behavior described in the issue.",
        environment={"type": "terminal", "repo": "owner/repo"},
        complexity=Complexity(horizon="medium", expected_tool_calls_typical=20),
        success_criteria=SuccessCriteria(type="unit_tests"),
    )

    assert task.budgets.max_wall_clock_seconds == 900
    assert task.source_type == "huggingface"


def test_task_schema_rejects_empty_instruction():
    with pytest.raises(ValidationError):
        BenchmarkTask(
            task_id="bad",
            source="manual",
            source_type="custom",
            category="research",
            instruction="   ",
            environment={"type": "browser"},
            complexity=Complexity(horizon="short"),
            budgets=Budget(),
            success_criteria=SuccessCriteria(type="rubric"),
        )
