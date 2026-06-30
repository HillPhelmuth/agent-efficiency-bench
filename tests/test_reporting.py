from agent_efficiency_bench.reporting import summarize_by_category, write_markdown_report
from agent_efficiency_bench.schemas import RunTelemetry


def test_summarize_by_category_joins_tasks_and_runs():
    tasks = {"t1": {"category": "web_research"}}
    runs = [
        RunTelemetry(
            run_id="r1",
            task_id="t1",
            agent="a",
            model="m",
            success=True,
            quality_score=1.0,
            wall_clock_seconds=60,
            input_tokens=100,
            output_tokens=20,
            estimated_usd=0.10,
        )
    ]
    summary = summarize_by_category(tasks, runs)
    assert summary["web_research"]["cost_per_success"] == 0.10


def test_write_markdown_report_contains_category(tmp_path):
    output = tmp_path / "report.md"
    write_markdown_report(output, {"web_research": {"total_runs": 1, "success_rate": 1.0, "cost_per_success": 0.10}})
    text = output.read_text()
    assert "web_research" in text
    assert "cost_per_success" in text
