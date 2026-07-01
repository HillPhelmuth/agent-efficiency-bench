from agent_efficiency_bench.evaluators.base import EvaluationScore
from agent_efficiency_bench.runner import BenchmarkRunner
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, ModelConfig, RunResult, RunTelemetry, SuccessCriteria


class FakeAgent:
    name = "fake-agent"
    model = "fake-model"
    config = ModelConfig(model="fake-model", tools=[{"type": "openrouter:web_search"}])

    def run(self, task, artifact_dir):
        telemetry = RunTelemetry(
            run_id="r1",
            task_id=task.task_id,
            agent=self.name,
            model=self.model,
            success=False,
            quality_score=0.0,
            wall_clock_seconds=1.0,
            input_tokens=10,
            output_tokens=5,
            estimated_usd=0.01,
        )
        return RunResult(telemetry=telemetry, output={"answer": "ok"}, trace_path=str(artifact_dir / "trace.jsonl"))


class FakeEvaluator:
    def evaluate(self, task, result):
        return EvaluationScore(success=True, quality_score=1.0, reason="ok")


def make_task():
    return BenchmarkTask(
        task_id="t1",
        source="manual",
        source_type="custom",
        category="web_research",
        instruction="Say ok",
        environment={"type": "web"},
        complexity=Complexity(horizon="short"),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="exact"),
    )


def test_runner_updates_telemetry_with_evaluation(tmp_path):
    runner = BenchmarkRunner(agent=FakeAgent(), evaluator=FakeEvaluator(), output_dir=tmp_path)
    result = runner.run_task(make_task())
    assert result.telemetry.success is True
    assert result.telemetry.quality_score == 1.0
    assert (tmp_path / "run_results.jsonl").exists()
    assert (tmp_path / "run_telemetry.jsonl").exists()


def test_runner_writes_manifest_with_agent_model_tools_and_tasks(tmp_path):
    runner = BenchmarkRunner(
        agent=FakeAgent(),
        evaluator=FakeEvaluator(),
        output_dir=tmp_path,
        tasks_path="data/tasks/public_efficiency_subset.jsonl",
        run_suite_id="suite-test",
    )
    runner.run_task(make_task())

    import json

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["run_suite_id"] == "suite-test"
    assert manifest["agent"] == "fake-agent"
    assert manifest["model"] == "fake-model"
    assert manifest["tools_configured"] == ["openrouter:web_search"]
    assert manifest["task_ids"] == ["t1"]
