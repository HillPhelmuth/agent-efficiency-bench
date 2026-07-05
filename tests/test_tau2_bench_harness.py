import json

import pytest

from agent_efficiency_bench.harnesses import tau2_bench
from agent_efficiency_bench.harnesses.tau2_bench import (
    build_tau2_command,
    parse_tau2_result,
    parse_tau2_task_id,
    run_tau2_task,
)


def test_parse_tau2_task_id_extracts_domain_and_id():
    assert parse_tau2_task_id("tau2_bench_retail__55") == ("retail", "55")


def test_build_tau2_command_marks_unresolved_runner_when_not_configured():
    cmd = build_tau2_command(domain="retail", task_id="55", model="openai/gpt-5.4-nano", output_dir="runs/tau2")

    assert cmd[0] == tau2_bench.UNRESOLVED_TAU2_RUNNER
    assert "55" in cmd


def test_run_tau2_task_dry_run_reports_unresolved_dependency(monkeypatch, tmp_path):
    monkeypatch.setattr(tau2_bench, "check_tau2_prerequisites", lambda runner_module=None, require_runner=True: {"python": True, "runner_module_configured": False, "runner_module_importable": False})

    result = run_tau2_task(task_id="tau2_bench_retail__55", model="openai/gpt-5.4-nano", output_dir=str(tmp_path))

    assert result["dry_run"] is True
    assert result["execute"] is False
    assert result["unresolved_dependency"] is True
    assert result["ready"] is False


def test_run_tau2_task_execute_requires_runner_module(monkeypatch, tmp_path):
    monkeypatch.setattr(tau2_bench, "check_tau2_prerequisites", lambda runner_module=None, require_runner=True: {"python": True, "runner_module_configured": False, "runner_module_importable": False})

    with pytest.raises(RuntimeError, match="runner module is not configured"):
        run_tau2_task(
            task_id="tau2_bench_retail__55",
            model="openai/gpt-5.4-nano",
            output_dir=str(tmp_path),
            dry_run=False,
            execute=True,
        )


def test_run_tau2_task_execute_runs_configured_runner(monkeypatch, tmp_path):
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"passed_actions": 2, "total_actions": 2, "success": True}), encoding="utf-8")
    monkeypatch.setattr(tau2_bench, "check_tau2_prerequisites", lambda runner_module=None, require_runner=True: {"python": True, "runner_module_configured": True, "runner_module_importable": True})

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    result = run_tau2_task(
        task_id="tau2_bench_retail__55",
        model="openai/gpt-5.4-nano",
        output_dir=str(tmp_path),
        runner_module="tau2.runner",
        dry_run=False,
        execute=True,
        result_path=result_path,
        subprocess_run=lambda *args, **kwargs: Completed(),
    )

    assert result["exit_code"] == 0
    assert result["parsed_result"]["success"] is True
    assert result["parsed_result"]["quality_score"] == 5.0


def test_parse_tau2_result_uses_action_ratio_when_score_missing(tmp_path):
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"summary": {"passed_actions": 1, "total_actions": 2}}), encoding="utf-8")

    parsed = parse_tau2_result(result_path)

    assert parsed["success"] is False
    assert parsed["quality_score"] == 3.0