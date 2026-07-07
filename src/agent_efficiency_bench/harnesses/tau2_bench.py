from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agent_efficiency_bench.scoring import coerce_quality_score


TAU2_CLI = "tau2"


def parse_tau2_task_id(task_id: str) -> tuple[str, str]:
    prefix = "tau2_bench_"
    if not task_id.startswith(prefix) or "__" not in task_id:
        raise ValueError(f"Invalid tau2 task id: {task_id}")
    domain_and_prefix, raw_id = task_id.split("__", 1)
    domain = domain_and_prefix.removeprefix(prefix)
    if not domain or not raw_id:
        raise ValueError(f"Invalid tau2 task id: {task_id}")
    return domain, raw_id


def build_tau2_command(
    domain: str,
    task_id: str,
    model: str,
    output_dir: str,
    *,
    agent: str = "llm_agent",
    user: str = "user_simulator",
    user_model: str | None = None,
    agent_llm_args: dict[str, Any] | None = None,
    user_llm_args: dict[str, Any] | None = None,
    num_trials: int = 1,
    max_steps: int | None = None,
    max_errors: int | None = None,
    max_concurrency: int | None = 1,
    seed: int | None = None,
    task_split_name: str | None = None,
    task_set_name: str | None = None,
    tau2_save_to: str | None = None,
    verbose_logs: bool = False,
    auto_resume: bool = True,
    runner_module: str | None = None,
) -> list[str]:
    """Build the official tau2 CLI command for an agent/evaluator run.

    `runner_module` is accepted for backward-compatible callers but the supported
    harness path is now the upstream `tau2 run` CLI. tau2 performs both the agent
    interaction and official evaluator pass, then writes a `results.json` file.
    """
    del runner_module
    save_to = tau2_save_to or _tau2_save_to_from_output_dir(output_dir)
    cmd = [
        TAU2_CLI,
        "run",
        "--domain",
        domain,
        "--agent",
        agent,
        "--user",
        user,
        "--agent-llm",
        model,
        "--user-llm",
        user_model or model,
        "--num-trials",
        str(num_trials),
        "--task-ids",
        str(task_id),
        "--save-to",
        save_to,
    ]
    if agent_llm_args:
        cmd.extend(["--agent-llm-args", json.dumps(agent_llm_args, sort_keys=True)])
    if user_llm_args:
        cmd.extend(["--user-llm-args", json.dumps(user_llm_args, sort_keys=True)])
    if max_steps is not None:
        cmd.extend(["--max-steps", str(max_steps)])
    if max_errors is not None:
        cmd.extend(["--max-errors", str(max_errors)])
    if max_concurrency is not None:
        cmd.extend(["--max-concurrency", str(max_concurrency)])
    if seed is not None:
        cmd.extend(["--seed", str(seed)])
    if task_split_name:
        cmd.extend(["--task-split-name", task_split_name])
    if task_set_name:
        cmd.extend(["--task-set-name", task_set_name])
    if verbose_logs:
        cmd.append("--verbose-logs")
    if auto_resume:
        cmd.append("--auto-resume")
    return cmd


def check_tau2_prerequisites(*, cli_name: str = TAU2_CLI, require_runner: bool | None = None, runner_module: str | None = None) -> dict[str, bool]:
    del require_runner, runner_module
    return {"tau2_cli": shutil.which(cli_name) is not None}


def run_tau2_task(
    task_id: str,
    model: str,
    output_dir: str,
    *,
    agent: str = "llm_agent",
    user: str = "user_simulator",
    user_model: str | None = None,
    agent_llm_args: dict[str, Any] | None = None,
    user_llm_args: dict[str, Any] | None = None,
    num_trials: int = 1,
    max_steps: int | None = None,
    max_errors: int | None = None,
    max_concurrency: int | None = 1,
    seed: int | None = None,
    task_split_name: str | None = None,
    task_set_name: str | None = None,
    tau2_save_to: str | None = None,
    verbose_logs: bool = False,
    auto_resume: bool = True,
    runner_module: str | None = None,
    dry_run: bool = True,
    execute: bool = False,
    result_path: str | Path | None = None,
    suite_budget: dict[str, Any] | None = None,
    subprocess_run=subprocess.run,
) -> dict[str, Any]:
    domain, raw_task_id = parse_tau2_task_id(task_id)
    prerequisites = check_tau2_prerequisites(runner_module=runner_module)
    command = build_tau2_command(
        domain=domain,
        task_id=raw_task_id,
        model=model,
        output_dir=output_dir,
        agent=agent,
        user=user,
        user_model=user_model,
        agent_llm_args=agent_llm_args,
        user_llm_args=user_llm_args,
        num_trials=num_trials,
        max_steps=max_steps,
        max_errors=max_errors,
        max_concurrency=max_concurrency,
        seed=seed,
        task_split_name=task_split_name,
        task_set_name=task_set_name,
        tau2_save_to=tau2_save_to,
        verbose_logs=verbose_logs,
        auto_resume=auto_resume,
        runner_module=runner_module,
    )
    result_file = Path(result_path) if result_path is not None else Path(output_dir) / "results.json"
    payload = {
        "task_id": task_id,
        "domain": domain,
        "raw_task_id": raw_task_id,
        "model": model,
        "user_model": user_model or model,
        "agent": agent,
        "user": user,
        "output_dir": output_dir,
        "command": command,
        "prerequisites": prerequisites,
        "dry_run": dry_run,
        "execute": execute,
        "result_path": str(result_file),
        "suite_budget": suite_budget or {},
        "harness": "tau2-bench",
    }

    if dry_run and not execute:
        payload["ready"] = all(prerequisites.values())
        return payload

    if not execute:
        raise ValueError("tau2 execution requires explicit execute=True")

    missing = [name for name, available in prerequisites.items() if not available]
    if missing:
        raise RuntimeError(f"Cannot execute tau2 task: missing prerequisites: {', '.join(missing)}")

    subprocess_env = _tau2_subprocess_env()
    payload["subprocess_env_overrides"] = _tau2_safe_env_overrides(subprocess_env)
    completed = subprocess_run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=subprocess_env,
    )
    payload.update(
        {
            "ready": True,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    )
    actual_result_file = _resolve_tau2_result_file(
        preferred_result_file=result_file,
        command=command,
        stderr=completed.stderr,
        subprocess_env=subprocess_env,
    )
    payload["actual_result_path"] = str(actual_result_file) if actual_result_file is not None else None
    if actual_result_file is not None:
        if actual_result_file.resolve() != result_file.resolve():
            result_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(actual_result_file, result_file)
            payload["copied_result_path"] = str(result_file)
        payload["parsed_result"] = parse_tau2_result(actual_result_file, task_id=raw_task_id)
    return payload


def parse_tau2_result(path: str | Path, task_id: str | None = None) -> dict[str, Any]:
    result_path = Path(path)
    with result_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    if isinstance(raw, dict) and isinstance(raw.get("simulations"), list):
        return _parse_official_results(raw, task_id=task_id)
    return _parse_flat_result(raw)


def _parse_flat_result(raw: dict[str, Any]) -> dict[str, Any]:
    passed_actions = int(_first_present(raw, "passed_actions", "actions_passed") or 0)
    total_actions = int(_first_present(raw, "total_actions", "actions_total") or 0)
    quality_score = _first_present(raw, "quality_score", "score")
    if quality_score is None and total_actions > 0:
        quality_score = passed_actions / total_actions
    success = _first_present(raw, "success", "passed")
    if success is None:
        success = bool(total_actions > 0 and passed_actions == total_actions)
    return {
        "success": bool(success),
        "quality_score": coerce_quality_score(quality_score, success=bool(success)),
        "passed_actions": passed_actions,
        "total_actions": total_actions,
        "details": raw.get("details") if isinstance(raw.get("details"), dict) else {},
        "raw": raw,
    }


def _parse_official_results(raw: dict[str, Any], task_id: str | None = None) -> dict[str, Any]:
    simulations = raw.get("simulations") or []
    selected_simulations = _select_simulations(simulations, task_id=task_id)
    selected = selected_simulations[0] if selected_simulations else {}
    aggregate = _aggregate_simulations(selected_simulations)
    reward_info = selected.get("reward_info") if isinstance(selected.get("reward_info"), dict) else {}
    reward = aggregate.get("mean_reward")
    success = bool((aggregate.get("pass_rate") or 0.0) > 0.0)
    passed_actions = int(aggregate.get("passed_actions") or 0)
    total_actions = int(aggregate.get("total_actions") or 0)
    quality_source = reward if reward is not None else (passed_actions / total_actions if total_actions else None)
    info = raw.get("info") if isinstance(raw.get("info"), dict) else {}
    details = {
        "harness": "tau2-bench",
        "harness_version": raw.get("version") or raw.get("format_version") or "unknown",
        "task_id": selected.get("task_id"),
        "trial": selected.get("trial"),
        "reward": reward,
        "pass_rate": aggregate.get("pass_rate"),
        "num_simulations": aggregate.get("num_simulations"),
        "total_agent_cost": aggregate.get("total_agent_cost"),
        "total_user_cost": aggregate.get("total_user_cost"),
        "total_cost": aggregate.get("total_cost"),
        "total_duration": aggregate.get("total_duration"),
        "mean_duration": aggregate.get("mean_duration"),
        "reward_breakdown": reward_info.get("reward_breakdown") or {},
        "partial_action_reward": reward_info.get("partial_action_reward") or {},
        "agent_cost": selected.get("agent_cost"),
        "user_cost": selected.get("user_cost"),
        "duration": selected.get("duration"),
        "termination_reason": selected.get("termination_reason"),
        "info": info,
    }
    return {
        "success": success,
        "quality_score": coerce_quality_score(quality_source, success=success),
        "passed_actions": passed_actions,
        "total_actions": total_actions,
        "details": details,
        "raw": {"simulation": selected, "simulations": selected_simulations, "info": info},
    }


def _select_simulations(simulations: list[Any], task_id: str | None = None) -> list[dict[str, Any]]:
    dict_sims = [sim for sim in simulations if isinstance(sim, dict)]
    if task_id is None:
        return dict_sims
    matching = [sim for sim in dict_sims if str(sim.get("task_id")) == str(task_id)]
    return matching or dict_sims[:1]


def _select_simulation(simulations: list[Any], task_id: str | None = None) -> dict[str, Any]:
    selected = _select_simulations(simulations, task_id=task_id)
    return selected[0] if selected else {}


def _aggregate_simulations(simulations: list[dict[str, Any]]) -> dict[str, Any]:
    rewards: list[float] = []
    passed_actions = 0
    total_actions = 0
    total_agent_cost = 0.0
    total_user_cost = 0.0
    total_duration = 0.0
    for simulation in simulations:
        reward_info = simulation.get("reward_info") if isinstance(simulation.get("reward_info"), dict) else {}
        reward = reward_info.get("reward")
        if reward is not None:
            rewards.append(float(reward))
        action_passed, action_total = _action_counts(reward_info)
        passed_actions += action_passed
        total_actions += action_total
        total_agent_cost += float(simulation.get("agent_cost") or 0.0)
        total_user_cost += float(simulation.get("user_cost") or 0.0)
        total_duration += float(simulation.get("duration") or 0.0)
    num_simulations = len(simulations)
    pass_count = sum(1 for reward in rewards if _is_successful_reward(reward))
    return {
        "num_simulations": num_simulations,
        "mean_reward": sum(rewards) / len(rewards) if rewards else None,
        "pass_rate": pass_count / len(rewards) if rewards else None,
        "passed_actions": passed_actions,
        "total_actions": total_actions,
        "total_agent_cost": total_agent_cost,
        "total_user_cost": total_user_cost,
        "total_cost": total_agent_cost + total_user_cost,
        "total_duration": total_duration,
        "mean_duration": total_duration / num_simulations if num_simulations else None,
    }


def _action_counts(reward_info: dict[str, Any]) -> tuple[int, int]:
    passed_actions, total_actions = _partial_action_counts(reward_info.get("partial_action_reward"))
    if total_actions:
        return passed_actions, total_actions
    action_checks = reward_info.get("action_checks")
    if not isinstance(action_checks, list):
        return 0, 0
    passed = 0
    total = 0
    for action_check in action_checks:
        if not isinstance(action_check, dict):
            continue
        total += 1
        passed += 1 if action_check.get("action_match") or _is_successful_reward(action_check.get("action_reward")) else 0
    return passed, total


def _partial_action_counts(partial_action_reward: Any) -> tuple[int, int]:
    if not isinstance(partial_action_reward, dict):
        return 0, 0
    passed = 0
    total = 0
    for value in partial_action_reward.values():
        if isinstance(value, dict):
            passed += int(value.get("correct") or value.get("passed") or 0)
            total += int(value.get("count") or value.get("total") or 0)
    return passed, total


def _is_successful_reward(reward: Any) -> bool:
    if reward is None:
        return False
    return 1 - 1e-6 <= float(reward) <= 1 + 1e-6


def _first_present(raw: Any, *keys: str) -> Any:
    if not isinstance(raw, dict):
        return None
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    summary = raw.get("summary")
    if isinstance(summary, dict):
        for key in keys:
            if key in summary and summary[key] is not None:
                return summary[key]
    return None


def _tau2_save_to_from_output_dir(output_dir: str) -> str:
    path = Path(output_dir)
    return path.name or "aeb-tau2-run"


def _resolve_tau2_result_file(
    *,
    preferred_result_file: Path,
    command: list[str],
    stderr: str,
    subprocess_env: dict[str, str],
) -> Path | None:
    if preferred_result_file.exists():
        return preferred_result_file
    save_to = _command_value(command, "--save-to")
    if not save_to:
        return None
    candidates: list[Path] = []
    save_to_path = Path(save_to)
    if save_to_path.is_absolute():
        candidates.append(save_to_path / "results.json" if save_to_path.suffix != ".json" else save_to_path)
    for data_dir in _candidate_tau2_data_dirs(command=command, stderr=stderr, subprocess_env=subprocess_env):
        candidates.append(data_dir / "simulations" / save_to / "results.json")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _candidate_tau2_data_dirs(*, command: list[str], stderr: str, subprocess_env: dict[str, str]) -> list[Path]:
    candidates: list[Path] = []
    env_data_dir = subprocess_env.get("TAU2_DATA_DIR")
    if env_data_dir:
        candidates.append(Path(env_data_dir))
    match = re.search(r"Using data directory from (?:source|environment):\s*(.+)", stderr)
    if match:
        candidates.append(Path(match.group(1).strip()))
    tau2_exe = shutil.which(command[0]) if command else None
    if tau2_exe:
        exe_path = Path(tau2_exe).resolve()
        for parent in exe_path.parents:
            data_dir = parent / "data"
            if data_dir.exists():
                candidates.append(data_dir)
                break
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def _command_value(command: list[str], flag: str) -> str | None:
    try:
        index = command.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(command):
        return None
    return command[index + 1]


def _tau2_subprocess_env() -> dict[str, str]:
    """Environment for tau2 subprocesses.

    tau2 uses Rich for console output. On Windows, Rich/colorama can fall back to
    a legacy cp1252 console path and crash on Unicode glyphs such as ``→`` before
    any benchmark result is written. Force UTF-8 mode for the child process and
    disable color/control output so captured stdout/stderr stay parseable.
    """
    env = dict(os.environ)
    env.update(
        {
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONLEGACYWINDOWSSTDIO": "0",
            "PYTHONUNBUFFERED": "1",
            "NO_COLOR": "1",
            "CLICOLOR": "0",
            "FORCE_COLOR": "0",
            "TERM": "dumb",
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
    )
    return env


def _tau2_safe_env_overrides(env: dict[str, str]) -> dict[str, str]:
    keys = [
        "PYTHONUTF8",
        "PYTHONIOENCODING",
        "PYTHONLEGACYWINDOWSSTDIO",
        "PYTHONUNBUFFERED",
        "NO_COLOR",
        "CLICOLOR",
        "FORCE_COLOR",
        "TERM",
        "LC_ALL",
        "LANG",
    ]
    return {key: env[key] for key in keys if key in env}
