from agent_efficiency_bench.harnesses.assistantbench import evaluator_for_assistantbench_task
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, SuccessCriteria


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
