from agent_efficiency_bench.schemas import ModelConfig, RunResult, RunTelemetry, TraceEvent


def test_model_config_defaults_to_openrouter():
    cfg = ModelConfig(model="openai/gpt-4o-mini")
    assert cfg.provider == "openrouter"
    assert cfg.temperature == 0.0
    assert cfg.max_completion_tokens == 2048


def test_trace_event_carries_structured_data():
    event = TraceEvent(t_rel_seconds=0.1, event="llm_call_end", data={"cost": 0.01})
    assert event.data["cost"] == 0.01


def test_run_result_wraps_existing_telemetry():
    telemetry = RunTelemetry(
        run_id="r1",
        task_id="t1",
        agent="a",
        model="m",
        success=True,
        quality_score=1.0,
        wall_clock_seconds=1.0,
        input_tokens=10,
        output_tokens=5,
        estimated_usd=0.001,
    )
    result = RunResult(telemetry=telemetry, trace_path="traces/r1.jsonl")
    assert result.telemetry.total_tokens == 15
