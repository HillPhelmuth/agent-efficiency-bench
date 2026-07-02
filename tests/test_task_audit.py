from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, SuccessCriteria
from agent_efficiency_bench.task_audit import audit_tasks, format_audit_markdown


def make_task(task_id="t1", **overrides):
    data = {
        "task_id": task_id,
        "source": "manual",
        "source_type": "custom",
        "category": "web_research",
        "instruction": "Find a cited answer online.",
        "environment": {"type": "web"},
        "complexity": Complexity(horizon="short", requires_external_search=True),
        "budgets": Budget(),
        "success_criteria": SuccessCriteria(type="manual"),
    }
    data.update(overrides)
    return BenchmarkTask(**data)


def test_audit_tasks_counts_core_dimensions_and_flags_warnings():
    tasks = [
        make_task(),
        make_task(
            task_id="t2",
            source="terminal-bench",
            category="terminal_work",
            instruction="|-",
            complexity=Complexity(horizon="medium", requires_code_execution=True),
            success_criteria=SuccessCriteria(type="exact"),
        ),
    ]

    audit = audit_tasks(tasks, min_instruction_chars=10)

    assert audit.counts["source"] == {"manual": 1, "terminal-bench": 1}
    assert audit.counts["category"] == {"web_research": 1, "terminal_work": 1}
    assert audit.counts["horizon"] == {"short": 1, "medium": 1}
    assert audit.requirements["requires_external_search"] == 1
    assert audit.requirements["requires_code_execution"] == 1
    assert any(warning.task_id == "t1" and warning.code == "manual_evaluator" for warning in audit.warnings)
    assert any(warning.task_id == "t2" and warning.code == "placeholder_instruction" for warning in audit.warnings)


def test_format_audit_markdown_includes_counts_and_warnings():
    audit = audit_tasks([make_task()], min_instruction_chars=10)

    text = format_audit_markdown(audit)

    assert "# Task Audit" in text
    assert "web_research" in text
    assert "manual_evaluator" in text
