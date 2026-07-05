from agent_efficiency_bench.metrics import aggregate_runs, score_run
from agent_efficiency_bench.schemas import RunTelemetry


def test_score_run_penalizes_cost_time_and_tokens():
    cheap = RunTelemetry(
        run_id="cheap",
        task_id="task-1",
        agent="agent-a",
        model="model-x",
        success=True,
        quality_score=5.0,
        wall_clock_seconds=60,
        input_tokens=1000,
        output_tokens=500,
        estimated_usd=0.01,
        num_llm_calls=2,
        num_tool_calls=4,
    )
    expensive = cheap.model_copy(update={
        "run_id": "expensive",
        "wall_clock_seconds": 600,
        "input_tokens": 100_000,
        "output_tokens": 10_000,
        "estimated_usd": 1.0,
    })

    assert score_run(cheap).quality_per_dollar > score_run(expensive).quality_per_dollar
    assert score_run(cheap).quality_per_minute > score_run(expensive).quality_per_minute
    assert score_run(cheap).quality_per_1k_tokens > score_run(expensive).quality_per_1k_tokens


def test_aggregate_runs_reports_cost_per_success():
    runs = [
        RunTelemetry(run_id="r1", task_id="t1", agent="a", model="m", success=True, quality_score=5, wall_clock_seconds=10, input_tokens=100, output_tokens=10, estimated_usd=0.10),
        RunTelemetry(run_id="r2", task_id="t2", agent="a", model="m", success=False, quality_score=1, wall_clock_seconds=20, input_tokens=200, output_tokens=20, estimated_usd=0.20),
    ]

    summary = aggregate_runs(runs)

    assert summary.total_runs == 2
    assert summary.successful_runs == 1
    assert summary.success_rate == 0.5
    assert summary.cost_per_success == 0.30
