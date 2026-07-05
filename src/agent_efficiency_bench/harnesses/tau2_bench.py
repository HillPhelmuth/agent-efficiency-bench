from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agent_efficiency_bench.scoring import coerce_quality_score


UNRESOLVED_TAU2_RUNNER = "<tau2-runner-module-required>"


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
    runner_module: str | None = None,
) -> list[str]:
    if not runner_module:
        return [
            UNRESOLVED_TAU2_RUNNER,
            "--domain",
            domain,
            "--task-id",
            task_id,
            "--model",
            model,
            "--output-dir",
            output_dir,
        ]
    return [
        "python",
        "-m",
        runner_module,
        "--domain",
        domain,
        "--task-id",
        task_id,
        "--model",
        model,
        "--output-dir",
        output_dir,
    ]


def check_tau2_prerequisites(runner_module: str | None = None, require_runner: bool = True) -> dict[str, bool]:
    prerequisites = {"python": shutil.which("python") is not None}
    if require_runner:
        prerequisites["runner_module_configured"] = runner_module is not None
        if runner_module:
            prerequisites["runner_module_importable"] = importlib.util.find_spec(runner_module) is not None
        else:
            prerequisites["runner_module_importable"] = False
    return prerequisites


def run_tau2_task(
    task_id: str,
    model: str,
    output_dir: str,
    runner_module: str | None = None,
    dry_run: bool = True,
    execute: bool = False,
    result_path: str | Path | None = None,
    suite_budget: dict[str, Any] | None = None,
    subprocess_run=subprocess.run,
) -> dict[str, Any]:
    domain, raw_task_id = parse_tau2_task_id(task_id)
    prerequisites = check_tau2_prerequisites(runner_module=runner_module, require_runner=True)
    command = build_tau2_command(domain=domain, task_id=raw_task_id, model=model, output_dir=output_dir, runner_module=runner_module)
    result_file = Path(result_path) if result_path is not None else Path(output_dir) / "result.json"
    unresolved_dependency = runner_module is None
    payload = {
        "task_id": task_id,
        "domain": domain,
        "raw_task_id": raw_task_id,
        "model": model,
        "output_dir": output_dir,
        "runner_module": runner_module,
        "command": command,
        "prerequisites": prerequisites,
        "dry_run": dry_run,
        "execute": execute,
        "result_path": str(result_file),
        "suite_budget": suite_budget or {},
        "unresolved_dependency": unresolved_dependency,
    }

    if dry_run and not execute:
        payload["ready"] = all(prerequisites.values()) and not unresolved_dependency
        return payload

    if not execute:
        raise ValueError("tau2 execution requires explicit execute=True")

    missing = [name for name, available in prerequisites.items() if not available]
    if unresolved_dependency or missing:
        detail = "runner module is not configured" if unresolved_dependency else f"missing prerequisites: {', '.join(missing)}"
        raise RuntimeError(f"Cannot execute tau2 task: {detail}")

    completed = subprocess_run(command, capture_output=True, text=True, check=False)
    payload.update(
        {
            "ready": True,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    )
    if result_file.exists():
        payload["parsed_result"] = parse_tau2_result(result_file)
    return payload


def parse_tau2_result(path: str | Path) -> dict[str, Any]:
    result_path = Path(path)
    with result_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

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