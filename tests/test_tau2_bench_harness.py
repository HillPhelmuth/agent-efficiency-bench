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


def test_build_tau2_command_uses_official_tau2_cli():
    cmd = build_tau2_command(domain="retail", task_id="55", model="openai/gpt-5.4-nano", output_dir="runs/tau2")

    assert cmd[:2] == ["tau2", "run"]
    assert "--domain" in cmd
    assert "retail" in cmd
    assert "55" in cmd
    assert "--agent-llm" in cmd
    assert "--user-llm" in cmd


def test_build_tau2_command_accepts_agent_and_evaluator_options():
    cmd = build_tau2_command(
        domain="retail",
        task_id="55",
        model="openai/gpt-5.4-nano",
        output_dir="runs/tau2",
        agent="aeb_agent",
        user="aeb_user",
        user_model="openai/gpt-5.4-mini",
        num_trials=2,
        max_steps=25,
        seed=123,
        tau2_save_to="aeb-tau2-smoke",
    )

    assert "aeb_agent" in cmd
    assert "aeb_user" in cmd
    assert "openai/gpt-5.4-mini" in cmd
    assert cmd[cmd.index("--num-trials") + 1] == "2"
    assert cmd[cmd.index("--max-steps") + 1] == "25"
    assert cmd[cmd.index("--seed") + 1] == "123"
    assert cmd[cmd.index("--save-to") + 1] == "aeb-tau2-smoke"


def test_run_tau2_task_dry_run_reports_missing_tau2_cli(monkeypatch, tmp_path):
    monkeypatch.setattr(tau2_bench, "check_tau2_prerequisites", lambda **kwargs: {"tau2_cli": False})

    result = run_tau2_task(task_id="tau2_bench_retail__55", model="openai/gpt-5.4-nano", output_dir=str(tmp_path))

    assert result["dry_run"] is True
    assert result["execute"] is False
    assert result["prerequisites"]["tau2_cli"] is False
    assert result["ready"] is False


def test_run_tau2_task_execute_requires_tau2_cli(monkeypatch, tmp_path):
    monkeypatch.setattr(tau2_bench, "check_tau2_prerequisites", lambda **kwargs: {"tau2_cli": False})

    with pytest.raises(RuntimeError, match="missing prerequisites: tau2_cli"):
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
    monkeypatch.setattr(tau2_bench, "check_tau2_prerequisites", lambda **kwargs: {"tau2_cli": True})
    monkeypatch.setenv("PYTHONUTF8", "0")
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    monkeypatch.setenv("NO_COLOR", "0")
    captured = {}

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_subprocess_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return Completed()

    result = run_tau2_task(
        task_id="tau2_bench_retail__55",
        model="openai/gpt-5.4-nano",
        output_dir=str(tmp_path),
        dry_run=False,
        execute=True,
        result_path=result_path,
        subprocess_run=fake_subprocess_run,
    )

    assert result["exit_code"] == 0
    assert result["parsed_result"]["success"] is True
    assert result["parsed_result"]["quality_score"] == 5.0
    assert captured["kwargs"]["encoding"] == "utf-8"
    assert captured["kwargs"]["errors"] == "replace"
    assert captured["kwargs"]["env"]["PYTHONUTF8"] == "1"
    assert captured["kwargs"]["env"]["PYTHONIOENCODING"] == "utf-8"
    assert captured["kwargs"]["env"]["NO_COLOR"] == "1"
    assert captured["kwargs"]["env"]["TERM"] == "dumb"
    assert result["subprocess_env_overrides"]["PYTHONUTF8"] == "1"
    assert result["subprocess_env_overrides"]["PYTHONIOENCODING"] == "utf-8"


def test_run_tau2_task_finds_results_in_tau2_data_dir(monkeypatch, tmp_path):
    tau2_data_dir = tmp_path / "tau2-data"
    actual_result_path = tau2_data_dir / "simulations" / "aeb-output" / "results.json"
    actual_result_path.parent.mkdir(parents=True)
    actual_result_path.write_text(
        json.dumps(
            {
                "simulations": [
                    {
                        "task_id": "55",
                        "reward_info": {"reward": 1.0, "action_checks": [{"action_match": True}]},
                        "agent_cost": 0.01,
                        "user_cost": 0.02,
                        "duration": 2.0,
                    },
                    {
                        "task_id": "55",
                        "reward_info": {"reward": 0.0, "action_checks": [{"action_match": False}]},
                        "agent_cost": 0.03,
                        "user_cost": 0.04,
                        "duration": 4.0,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TAU2_DATA_DIR", str(tau2_data_dir))
    monkeypatch.setattr(tau2_bench, "check_tau2_prerequisites", lambda **kwargs: {"tau2_cli": True})

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = f"Using data directory from environment: {tau2_data_dir}\n"

    copied_result_path = tmp_path / "aeb-output" / "results.json"
    result = run_tau2_task(
        task_id="tau2_bench_retail__55",
        model="openai/gpt-5.4-nano",
        output_dir=str(tmp_path / "aeb-output"),
        dry_run=False,
        execute=True,
        result_path=copied_result_path,
        subprocess_run=lambda *args, **kwargs: Completed(),
    )

    assert result["actual_result_path"] == str(actual_result_path)
    assert result["copied_result_path"] == str(copied_result_path)
    assert copied_result_path.exists()
    assert result["parsed_result"]["success"] is True
    assert result["parsed_result"]["quality_score"] == 3.0
    assert result["parsed_result"]["passed_actions"] == 1
    assert result["parsed_result"]["total_actions"] == 2
    assert result["parsed_result"]["details"]["pass_rate"] == 0.5
    assert result["parsed_result"]["details"]["total_cost"] == pytest.approx(0.1)


def test_parse_tau2_result_uses_action_ratio_when_score_missing(tmp_path):
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"summary": {"passed_actions": 1, "total_actions": 2}}), encoding="utf-8")

    parsed = parse_tau2_result(result_path)

    assert parsed["success"] is False
    assert parsed["quality_score"] == 3.0


def test_parse_tau2_result_reads_official_results_json(tmp_path):
    result_path = tmp_path / "results.json"
    result_path.write_text(
        json.dumps(
            {
                "simulations": [
                    {
                        "task_id": "55",
                        "trial": 0,
                        "reward_info": {
                            "reward": 0.5,
                            "partial_action_reward": {
                                "read": {"correct": 1, "count": 2},
                                "write": {"correct": 1, "count": 1},
                            },
                            "reward_breakdown": {"DB": 1.0, "COMMUNICATE": 0.5},
                        },
                        "agent_cost": 0.012,
                        "duration": 4.5,
                        "termination_reason": "agent_stop",
                    }
                ],
                "info": {"agent_info": {"implementation": "llm_agent", "llm": "openai/gpt-5.4-nano"}},
            }
        ),
        encoding="utf-8",
    )

    parsed = parse_tau2_result(result_path, task_id="55")

    assert parsed["success"] is False
    assert parsed["quality_score"] == 3.0
    assert parsed["passed_actions"] == 2
    assert parsed["total_actions"] == 3
    assert parsed["details"]["agent_cost"] == 0.012
    assert parsed["details"]["termination_reason"] == "agent_stop"
    assert parsed["details"]["harness"] == "tau2-bench"
