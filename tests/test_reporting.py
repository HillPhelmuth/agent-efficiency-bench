from agent_efficiency_bench.reporting import summarize_by_category, summarize_by_dimensions, write_markdown_report
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


def test_summarize_by_dimensions_groups_by_category_model_and_tools_enabled():
    tasks = {"t1": {"category": "web_research", "source": "AssistantBench", "complexity": {"horizon": "short"}}}
    runs = [
        RunTelemetry(
            run_id="r1",
            task_id="t1",
            agent="openrouter-answer",
            model="openai/gpt-5.4-nano",
            success=True,
            quality_score=1.0,
            wall_clock_seconds=10,
            input_tokens=100,
            output_tokens=20,
            estimated_usd=0.10,
        )
    ]
    manifests = {"r1": {"tools_configured": ["openrouter:web_search"]}}

    summary = summarize_by_dimensions(tasks, runs, ["category", "model", "tools_enabled"], manifests=manifests)

    key = "category=web_research | model=openai/gpt-5.4-nano | tools_enabled=true"
    assert summary[key]["total_runs"] == 1
    assert summary[key]["cost_per_success"] == 0.10


def test_summarize_by_dimensions_falls_back_to_server_tools_without_manifest():
    tasks = {"t1": {"category": "web_research", "source": "AssistantBench", "complexity": {"horizon": "short"}}}
    runs = [
        RunTelemetry(
            run_id="r1",
            task_id="t1",
            agent="openrouter-answer",
            model="openai/gpt-5.4-nano",
            server_tools_configured=["openrouter:web_search"],
            success=False,
            quality_score=0.0,
            wall_clock_seconds=10,
            input_tokens=100,
            output_tokens=20,
            estimated_usd=0.10,
        )
    ]

    summary = summarize_by_dimensions(tasks, runs, ["tools_enabled"])

    assert "tools_enabled=true" in summary


def test_summarize_by_dimensions_groups_by_scaffold():
    tasks = {"t1": {"category": "web_research", "complexity": {"horizon": "short"}}}
    runs = [
        RunTelemetry(
            run_id="r1",
            task_id="t1",
            agent="openrouter-answer",
            model="openai/gpt-5.4-nano",
            scaffold="web-search-answer",
            success=True,
            quality_score=1.0,
            wall_clock_seconds=10,
            input_tokens=100,
            output_tokens=20,
            estimated_usd=0.10,
        )
    ]

    summary = summarize_by_dimensions(tasks, runs, ["scaffold"])

    assert "scaffold=web-search-answer" in summary


def test_summarize_by_dimensions_groups_by_trial_index_and_reports_variance():
    tasks = {"t1": {"category": "web_research", "complexity": {"horizon": "short"}}}
    runs = [
        RunTelemetry(
            run_id="r1__trial_000",
            task_id="t1",
            agent="openrouter-answer",
            model="openai/gpt-5.4-nano",
            trial_index=0,
            success=True,
            quality_score=1.0,
            wall_clock_seconds=10,
            input_tokens=100,
            output_tokens=20,
            estimated_usd=0.10,
        ),
        RunTelemetry(
            run_id="r1__trial_001",
            task_id="t1",
            agent="openrouter-answer",
            model="openai/gpt-5.4-nano",
            trial_index=1,
            success=True,
            quality_score=0.5,
            wall_clock_seconds=14,
            input_tokens=110,
            output_tokens=30,
            estimated_usd=0.14,
        ),
    ]

    grouped = summarize_by_dimensions(tasks, runs, ["trial_index"])
    overall = summarize_by_dimensions(tasks, runs, ["category"])

    assert "trial_index=0" in grouped
    assert "trial_index=1" in grouped
    assert overall["category=web_research"]["stdev_cost_usd"] > 0.0
    assert overall["category=web_research"]["stdev_latency_seconds"] > 0.0
    assert overall["category=web_research"]["stdev_total_tokens"] > 0.0
    assert overall["category=web_research"]["stdev_quality"] > 0.0


def test_summarize_by_dimensions_includes_citation_and_annotation_totals():
    tasks = {"t1": {"category": "web_research", "source": "AssistantBench", "complexity": {"horizon": "short"}}}
    runs = [
        RunTelemetry(
            run_id="r1",
            task_id="t1",
            agent="openrouter-answer",
            model="openai/gpt-5.4-nano",
            server_tools_configured=["openrouter:web_search"],
            success=True,
            quality_score=1.0,
            wall_clock_seconds=10,
            input_tokens=100,
            output_tokens=20,
            estimated_usd=0.10,
            num_citations=2,
            num_annotations=3,
        )
    ]

    summary = summarize_by_dimensions(tasks, runs, ["category"])

    assert summary["category=web_research"]["total_citations"] == 2
    assert summary["category=web_research"]["total_annotations"] == 3
