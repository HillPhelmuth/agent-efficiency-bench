from agent_efficiency_bench.schemas import ModelConfig, RunManifest, RunResult, RunTelemetry, TraceEvent


def test_model_config_defaults_to_openrouter():
    cfg = ModelConfig(model="openai/gpt-5.4-nano")
    assert cfg.provider == "openrouter"
    assert cfg.temperature == 0.0
    assert cfg.max_completion_tokens == 2048


def test_model_config_can_carry_tools_and_tool_choice():
    tool = {"type": "function", "function": {"name": "web_search", "parameters": {"type": "object"}}}
    cfg = ModelConfig(model="openai/gpt-5.4-nano", tools=[tool], tool_choice="auto")
    assert cfg.tools == [tool]
    assert cfg.tool_choice == "auto"


def test_trace_event_carries_structured_data():
    event = TraceEvent(t_rel_seconds=0.1, event="llm_call_end", data={"cost": 0.01})
    assert event.data["cost"] == 0.01


def test_run_manifest_records_reproducibility_context():
    manifest = RunManifest(
        run_suite_id="suite-1",
        agent="openrouter-answer",
        model="openai/gpt-5.4-nano",
        tasks_path="data/tasks/public_efficiency_subset.jsonl",
        output_dir="runs/calibration",
        tools_configured=["openrouter:web_search"],
        task_ids=["t1"],
        git_commit="abc123",
        budget={"max_total_tokens": 200000},
        source_revisions={"AssistantBench/AssistantBench": {"revision": "dev"}},
        evaluator={"name": "RegistryEvaluator", "package_version": "0.1.0"},
        harness={"identity": "unknown", "version": "unknown"},
        provider={"requested_provider": "openrouter", "requested_model": "openai/gpt-5.4-nano"},
        environment={"python_version": "3.13.0", "platform": "test"},
    )
    assert manifest.tools_configured == ["openrouter:web_search"]
    assert manifest.task_ids == ["t1"]
    assert manifest.budget["max_total_tokens"] == 200000
    assert manifest.source_revisions["AssistantBench/AssistantBench"]["revision"] == "dev"
    assert manifest.evaluator["name"] == "RegistryEvaluator"
    assert manifest.harness["identity"] == "unknown"
    assert manifest.provider["requested_provider"] == "openrouter"
    assert manifest.environment["python_version"] == "3.13.0"


def test_run_result_wraps_existing_telemetry():
    telemetry = RunTelemetry(
        run_id="r1",
        task_id="t1",
        agent="a",
        model="m",
        success=True,
        quality_score=5.0,
        wall_clock_seconds=1.0,
        input_tokens=10,
        output_tokens=5,
        estimated_usd=0.001,
    )
    result = RunResult(telemetry=telemetry, trace_path="traces/r1.jsonl")
    assert result.telemetry.total_tokens == 15
