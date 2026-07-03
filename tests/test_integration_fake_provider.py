import json

from typer.testing import CliRunner

from agent_efficiency_bench import cli
from agent_efficiency_bench.agents.openrouter_answer import OpenRouterAnswerAgent
from agent_efficiency_bench.evaluators.simple import NoOpEvaluator
from agent_efficiency_bench.io import read_jsonl
from agent_efficiency_bench.reporting import summarize_by_category, write_markdown_report
from agent_efficiency_bench.runner import BenchmarkRunner
from agent_efficiency_bench.schemas import BenchmarkTask, Complexity, ModelConfig, RunResult, RunTelemetry, SuccessCriteria


class FakeResponse:
    content = "fake answer"
    prompt_tokens = 12
    completion_tokens = 4
    total_tokens = 16
    cost_usd = 0.002
    model = "fake/model"
    generation_id = "gen-fake"
    finish_reason = "stop"
    raw = {}


class FakeClient:
    def chat(self, config, messages, tools=None, tool_choice=None):
        return FakeResponse()


def test_fake_provider_execution_flow_writes_trace_and_report(tmp_path):
    task = BenchmarkTask.model_validate(read_jsonl("data/tasks/public_efficiency_subset.jsonl")[0])
    agent = OpenRouterAnswerAgent(config=ModelConfig(model="fake/model"), client=FakeClient())
    runner = BenchmarkRunner(agent=agent, evaluator=NoOpEvaluator(), output_dir=tmp_path / "runs")

    result = runner.run_task(task)

    assert result.telemetry.input_tokens == 12
    assert result.telemetry.output_tokens == 4
    assert result.telemetry.estimated_usd == 0.002
    assert (tmp_path / "runs" / "run_results.jsonl").exists()
    assert (tmp_path / "runs" / "run_telemetry.jsonl").exists()
    assert (tmp_path / "runs" / "manifest.json").exists()
    trace_rows = read_jsonl(result.trace_path)
    assert [row["event"] for row in trace_rows] == ["task_start", "llm_call_start", "llm_call_end", "budget_check", "task_end"]

    summary = summarize_by_category({task.task_id: task.model_dump()}, [result.telemetry])
    report_path = tmp_path / "report.md"
    write_markdown_report(report_path, summary)
    assert task.category in report_path.read_text()


def test_cli_smoke_flow_builds_audits_runs_and_reports_without_openrouter(tmp_path, monkeypatch):
    runner = CliRunner()
    subset_path = tmp_path / "subset.jsonl"
    audit_path = tmp_path / "audit.md"
    output_dir = tmp_path / "runs"
    report_path = tmp_path / "report.json"

    task = BenchmarkTask(
        task_id="assistantbench__smoke",
        source="AssistantBench/AssistantBench",
        source_type="huggingface",
        source_url="https://huggingface.co/datasets/AssistantBench/AssistantBench",
        category="web_research",
        instruction="Return the known answer.",
        environment={"type": "web", "split": "dev"},
        complexity=Complexity(horizon="short", requires_external_search=False),
        success_criteria=SuccessCriteria(type="structured_answer", checker="assistantbench_exact_or_rubric"),
        raw={"answer": "Known Answer", "expected": {"text_contains": ["Known Answer"]}},
    )

    class FakeAnswerAgent:
        name = "fake-answer-agent"
        model = "fake/model"
        scaffold = "answer-only"

        def __init__(self, config):
            self.config = config

        def run(self, task, artifact_dir):
            trace_path = output_dir / task.task_id / "trace.jsonl"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            trace_path.write_text(
                json.dumps({"event": "task_start"}) + "\n" + json.dumps({"event": "task_end"}) + "\n",
                encoding="utf-8",
            )
            telemetry = RunTelemetry(
                run_id=f"{task.task_id}__answer",
                task_id=task.task_id,
                agent=self.name,
                model=self.model,
                scaffold=self.scaffold,
                success=False,
                quality_score=0.0,
                wall_clock_seconds=0.5,
                input_tokens=5,
                output_tokens=3,
                estimated_usd=0.0,
                terminated_by="not_evaluated",
            )
            return RunResult(
                telemetry=telemetry,
                output={"answer": "Known Answer"},
                trace_path=str(trace_path),
                artifact_dir=str(trace_path.parent),
            )

    monkeypatch.setattr(cli, "load_sources_from_config", lambda path: [task])
    monkeypatch.setattr(cli, "OpenRouterAnswerAgent", FakeAnswerAgent)

    build_result = runner.invoke(
        cli.app,
        [
            "build-subset",
            "--config",
            str(tmp_path / "sources-smoke.yaml"),
            "--output",
            str(subset_path),
        ],
    )
    assert build_result.exit_code == 0
    assert subset_path.exists()

    audit_result = runner.invoke(cli.app, ["audit-tasks", str(subset_path), "--output", str(audit_path)])
    assert audit_result.exit_code == 0
    assert audit_path.exists()

    run_result = runner.invoke(
        cli.app,
        [
            "run-answer",
            "--tasks",
            str(subset_path),
            "--model",
            "fake/model",
            "--output-dir",
            str(output_dir),
        ],
    )
    assert run_result.exit_code == 0
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "run_telemetry.jsonl").exists()

    report_result = runner.invoke(
        cli.app,
        [
            "report",
            "--tasks",
            str(subset_path),
            "--runs",
            str(output_dir / "run_telemetry.jsonl"),
            "--format",
            "json",
            "--output",
            str(report_path),
        ],
    )
    assert report_result.exit_code == 0
    assert report_path.exists()

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert manifest["task_ids"] == ["assistantbench__smoke"]
    assert report["web_research"]["total_runs"] == 1
