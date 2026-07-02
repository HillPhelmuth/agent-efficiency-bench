from agent_efficiency_bench.harnesses.terminal_bench import build_terminal_bench_command


def test_terminal_bench_command_includes_model_and_task():
    cmd = build_terminal_bench_command(task_id="count-dataset-tokens", model="openai/gpt-5.4-nano", output_dir="runs/tb")
    joined = " ".join(cmd)
    assert "count-dataset-tokens" in joined
    assert "openai/gpt-5.4-nano" in joined
