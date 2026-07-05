import json

import pytest

from agent_efficiency_bench.harnesses import terminal_bench
from agent_efficiency_bench.harnesses.terminal_bench import (
    build_terminal_bench_command,
    parse_terminal_bench_result,
    run_terminal_bench_task,
)


def test_terminal_bench_command_includes_model_and_task():
    cmd = build_terminal_bench_command(task_id="count-dataset-tokens", model="openai/gpt-5.4-nano", output_dir="runs/tb")
    joined = " ".join(cmd)
    assert "count-dataset-tokens" in joined
    assert "openai/gpt-5.4-nano" in joined


def test_run_terminal_bench_task_dry_run_reports_prerequisites(monkeypatch, tmp_path):
    monkeypatch.setattr(terminal_bench, "check_terminal_bench_prerequisites", lambda require_harbor=True: {"docker": True, "uv": True, "harbor": False})

    result = run_terminal_bench_task(task_id="count-dataset-tokens", model="openai/gpt-5.4-nano", output_dir=str(tmp_path))

    assert result["dry_run"] is True
    assert result["execute"] is False
    assert result["ready"] is False
    assert result["prerequisites"]["harbor"] is False


def test_run_terminal_bench_task_execute_requires_prerequisites(monkeypatch, tmp_path):
    monkeypatch.setattr(terminal_bench, "check_terminal_bench_prerequisites", lambda require_harbor=True: {"docker": True, "uv": False, "harbor": True})

    with pytest.raises(RuntimeError, match="Missing Terminal-Bench prerequisites: uv"):
        run_terminal_bench_task(
            task_id="count-dataset-tokens",
            model="openai/gpt-5.4-nano",
            output_dir=str(tmp_path),
            dry_run=False,
            execute=True,
        )


def test_run_terminal_bench_task_execute_runs_command_and_parses_result(monkeypatch, tmp_path):
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"success": True, "quality_score": 1.0, "status": "passed"}), encoding="utf-8")
    monkeypatch.setattr(terminal_bench, "check_terminal_bench_prerequisites", lambda require_harbor=True: {"docker": True, "uv": True, "harbor": True})

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    result = run_terminal_bench_task(
        task_id="count-dataset-tokens",
        model="openai/gpt-5.4-nano",
        output_dir=str(tmp_path),
        dry_run=False,
        execute=True,
        result_path=result_path,
        subprocess_run=lambda *args, **kwargs: Completed(),
    )

    assert result["exit_code"] == 0
    assert result["stdout"] == "ok"
    assert result["parsed_result"]["success"] is True
    assert result["parsed_result"]["status"] == "passed"


def test_parse_terminal_bench_result_reads_nested_summary(tmp_path):
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"summary": {"resolved": True, "score": 0.75, "status": "resolved"}}), encoding="utf-8")

    parsed = parse_terminal_bench_result(result_path)

    assert parsed["success"] is True
    assert parsed["quality_score"] == 4.0
    assert parsed["status"] == "resolved"
