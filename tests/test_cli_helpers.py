from agent_efficiency_bench.cli import select_tasks
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, SuccessCriteria


def make_task(task_id, category):
    return BenchmarkTask(
        task_id=task_id,
        source="manual",
        source_type="custom",
        category=category,
        instruction="Do it",
        environment={"type": "web"},
        complexity=Complexity(horizon="short"),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="manual"),
    )


def test_select_tasks_filters_category_and_limit():
    tasks = [make_task("t1", "web_research"), make_task("t2", "terminal_work"), make_task("t3", "web_research")]
    selected = select_tasks(tasks, category="web_research", limit=1)
    assert [task.task_id for task in selected] == ["t1"]
