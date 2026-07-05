import json

from agent_efficiency_bench.evaluators.base import EvaluationScore
from agent_efficiency_bench.evaluators.simple import UnevaluatedEvaluator
from agent_efficiency_bench.runner import BenchmarkRunner, SuiteBudgetConfig
from agent_efficiency_bench.schemas import BenchmarkTask, Budget, Complexity, ModelConfig, RunResult, RunTelemetry, SuccessCriteria


class FakeAgent:
    name = "fake-agent"
    model = "fake-model"
    scaffold = "fake-scaffold"
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


class FakeHarnessAgent(FakeAgent):
    def run(self, task, artifact_dir):
        result = super().run(task, artifact_dir)
        result.output["harness_result"] = {
            "success": True,
            "status": "passed",
            "details": {"harness": "fake-harness", "harness_version": "1.2.3"},
        }
        return result


class FakeEvaluator:
    def evaluate(self, task, result):
        return EvaluationScore(success=True, quality_score=5.0, reason="ok")


class TaskOutcomeEvaluator:
    def __init__(self, outcomes):
        self.outcomes = outcomes

    def evaluate(self, task, result):
        success = self.outcomes[task.task_id]
        return EvaluationScore(success=success, quality_score=5.0 if success else 1.0, reason="ok")


def make_task(task_id: str = "t1"):
    return BenchmarkTask(
        task_id=task_id,
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
    assert result.telemetry.quality_score == 5.0
    assert (tmp_path / "run_results.jsonl").exists()
    assert (tmp_path / "run_telemetry.jsonl").exists()


def test_runner_preserves_not_evaluated_for_unevaluated_scores(tmp_path):
    runner = BenchmarkRunner(agent=FakeAgent(), evaluator=UnevaluatedEvaluator(reason="No harness result"), output_dir=tmp_path)

    result = runner.run_task(make_task())

    assert result.telemetry.terminated_by == "not_evaluated"
    assert result.output["evaluation"]["evaluated"] is False


def test_runner_writes_manifest_with_agent_model_tools_and_tasks(tmp_path):
    runner = BenchmarkRunner(
        agent=FakeAgent(),
        evaluator=FakeEvaluator(),
        output_dir=tmp_path,
        tasks_path="data/tasks/public_efficiency_subset.jsonl",
        run_suite_id="suite-test",
    )
    runner.run_task(make_task())

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["run_suite_id"] == "suite-test"
    assert manifest["agent"] == "fake-agent"
    assert manifest["model"] == "fake-model"
    assert manifest["scaffold"] == "fake-scaffold"
    assert manifest["tools_configured"] == ["openrouter:web_search"]
    assert manifest["task_ids"] == ["t1"]
    assert manifest["trial_count"] == 1
    assert manifest["trial_indices"] == []
    assert manifest["budget"] == {
        "max_wall_clock_seconds": 900,
        "max_total_tokens": 200000,
        "max_estimated_usd": 2.0,
        "max_tool_calls": 80,
        "max_llm_calls": 40,
    }
    assert manifest["suite_budget"] == {
        "limits": {},
        "observed": {
            "tasks_completed": 1,
            "failures": 0,
            "estimated_usd": 0.01,
            "wall_clock_seconds": manifest["suite_budget"]["observed"]["wall_clock_seconds"],
        },
        "terminated_by": None,
        "aborted": False,
    }
    assert manifest["source_revisions"] == {
        "manual": {
            "source_type": "custom",
            "source_url": None,
            "revision": "unknown",
        }
    }
    assert manifest["evaluator"]["name"] == "FakeEvaluator"
    assert manifest["evaluator"]["package_version"]
    assert manifest["harness"] == {}
    assert manifest["provider"] == {
        "requested_provider": "openrouter",
        "requested_model": "fake-model",
        "returned_models": [],
        "upstream_providers": [],
        "routes": [],
    }
    assert manifest["environment"]["python_version"]
    assert manifest["environment"]["platform"]
    assert manifest["environment"]["cwd"]
    assert "git_commit" in manifest["environment"]
    assert "command" in manifest["environment"]


def test_runner_writes_source_evaluator_harness_and_provider_provenance(tmp_path):
    class OpenRouterLikeAgent(FakeHarnessAgent):
        def run(self, task, artifact_dir):
            result = super().run(task, artifact_dir)
            result.output["provider_response"] = {
                "generation_id": "gen-1",
                "returned_model": "openai/gpt-5.4-nano-2026-06-01",
                "provider": "OpenAI",
                "route": "primary",
            }
            return result

    task = BenchmarkTask(
        task_id="swe_bench_lite__demo",
        source="SWE-bench/SWE-bench_Lite",
        source_type="huggingface",
        source_url="https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite",
        category="software_engineering",
        instruction="Fix the bug",
        environment={"type": "terminal", "repo": "pallets/flask", "base_commit": "abc123", "version": "1.0"},
        complexity=Complexity(horizon="long"),
        budgets=Budget(),
        success_criteria=SuccessCriteria(type="unit_tests", checker="swebench_harness"),
    )

    runner = BenchmarkRunner(agent=OpenRouterLikeAgent(), evaluator=FakeEvaluator(), output_dir=tmp_path)
    runner.run_task(task)

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["source_revisions"]["SWE-bench/SWE-bench_Lite"] == {
        "source_type": "huggingface",
        "source_url": "https://huggingface.co/datasets/SWE-bench/SWE-bench_Lite",
        "revision": "per_task",
        "details": {
            "repos": ["pallets/flask"],
            "base_commits": ["abc123"],
            "versions": ["1.0"],
        },
    }
    assert manifest["harness"] == {
        "required_checkers": ["swebench_harness"],
        "observed": [
            {
                "checker": "swebench_harness",
                "source": "SWE-bench/SWE-bench_Lite",
                "identity": "fake-harness",
                "version": "1.2.3",
                "status": "passed",
            }
        ],
        "identity": "fake-harness",
        "version": "1.2.3",
    }
    assert manifest["provider"] == {
        "requested_provider": "openrouter",
        "requested_model": "fake-model",
        "returned_models": ["openai/gpt-5.4-nano-2026-06-01"],
        "upstream_providers": ["OpenAI"],
        "routes": ["primary"],
    }


def test_runner_repeats_trials_with_distinct_run_ids_and_artifacts(tmp_path):
    runner = BenchmarkRunner(agent=FakeAgent(), evaluator=FakeEvaluator(), output_dir=tmp_path)

    results = runner.run_tasks([make_task("t1")], n_trials=2)

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert [result.telemetry.trial_index for result in results] == [0, 1]
    assert [result.telemetry.run_id for result in results] == ["r1__trial_000", "r1__trial_001"]
    assert (tmp_path / "t1" / "trial-000").exists()
    assert (tmp_path / "t1" / "trial-001").exists()
    assert manifest["trial_count"] == 2
    assert manifest["trial_indices"] == [0, 1]


def test_runner_stops_after_max_suite_tasks(tmp_path):
    runner = BenchmarkRunner(
        agent=FakeAgent(),
        evaluator=FakeEvaluator(),
        output_dir=tmp_path,
        suite_budget=SuiteBudgetConfig(max_suite_tasks=1),
    )

    results = runner.run_tasks([make_task("t1"), make_task("t2")])

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert [result.telemetry.task_id for result in results] == ["t1"]
    assert manifest["suite_budget"]["limits"]["max_suite_tasks"] == 1
    assert manifest["suite_budget"]["terminated_by"] == "suite_budget_tasks"
    assert manifest["suite_budget"]["aborted"] is True


def test_runner_stops_after_max_suite_failures(tmp_path):
    runner = BenchmarkRunner(
        agent=FakeAgent(),
        evaluator=TaskOutcomeEvaluator({"t1": False, "t2": True}),
        output_dir=tmp_path,
        suite_budget=SuiteBudgetConfig(max_suite_failures=1),
    )

    results = runner.run_tasks([make_task("t1"), make_task("t2")])

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert [result.telemetry.task_id for result in results] == ["t1"]
    assert manifest["suite_budget"]["terminated_by"] == "suite_budget_failures"
    assert manifest["suite_budget"]["observed"]["failures"] == 1


def test_runner_stops_after_max_suite_cost(tmp_path):
    runner = BenchmarkRunner(
        agent=FakeAgent(),
        evaluator=FakeEvaluator(),
        output_dir=tmp_path,
        suite_budget=SuiteBudgetConfig(max_suite_estimated_usd=0.01),
    )

    results = runner.run_tasks([make_task("t1"), make_task("t2")])

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert [result.telemetry.task_id for result in results] == ["t1"]
    assert manifest["suite_budget"]["terminated_by"] == "suite_budget_cost"
    assert manifest["suite_budget"]["observed"]["estimated_usd"] == 0.01


def test_runner_stops_after_max_suite_time(tmp_path):
    times = iter([0.0, 0.0, 2.0, 2.0, 2.0, 2.0])
    runner = BenchmarkRunner(
        agent=FakeAgent(),
        evaluator=FakeEvaluator(),
        output_dir=tmp_path,
        suite_budget=SuiteBudgetConfig(max_suite_wall_clock_seconds=1.0),
        time_fn=lambda: next(times),
    )

    results = runner.run_tasks([make_task("t1"), make_task("t2")])

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert [result.telemetry.task_id for result in results] == ["t1"]
    assert manifest["suite_budget"]["terminated_by"] == "suite_budget_time"
    assert manifest["suite_budget"]["observed"]["wall_clock_seconds"] == 2.0
