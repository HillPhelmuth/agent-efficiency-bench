from agent_efficiency_bench.harnesses.swe_bench import build_swe_bench_eval_command, patch_path_for_task


def test_patch_path_for_task_is_stable(tmp_path):
    path = patch_path_for_task(tmp_path, "django__django-123")
    assert path.name == "django__django-123.patch"


def test_swe_bench_command_mentions_predictions_file():
    cmd = build_swe_bench_eval_command(predictions_path="runs/swe/predictions.jsonl", run_id="smoke")
    joined = " ".join(cmd)
    assert "predictions.jsonl" in joined
    assert "smoke" in joined
