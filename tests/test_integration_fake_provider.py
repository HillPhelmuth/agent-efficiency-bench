from agent_efficiency_bench.agents.openrouter_answer import OpenRouterAnswerAgent
from agent_efficiency_bench.evaluators.simple import NoOpEvaluator
from agent_efficiency_bench.io import read_jsonl
from agent_efficiency_bench.reporting import summarize_by_category, write_markdown_report
from agent_efficiency_bench.runner import BenchmarkRunner
from agent_efficiency_bench.schemas import BenchmarkTask, ModelConfig


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
