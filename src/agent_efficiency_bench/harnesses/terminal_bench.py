from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_TERMINAL_BENCH_DATASET = "terminal-bench/terminal-bench-2-1"


def build_terminal_bench_command(
    task_id: str,
    model: str,
    output_dir: str,
    agent: str = "terminus-2",
    dataset: str = DEFAULT_TERMINAL_BENCH_DATASET,
) -> list[str]:
    return [
        "harbor",
        "run",
        "--dataset",
        dataset,
        "--agent",
        agent,
        "--model",
        model,
        "--task-id",
        task_id,
        "--output-dir",
        output_dir,
    ]


def check_terminal_bench_prerequisites(require_harbor: bool = True) -> dict[str, bool]:
    commands = ["docker", "uv"]
    if require_harbor:
        commands.append("harbor")
    return {command: shutil.which(command) is not None for command in commands}


def run_terminal_bench_task(
    task_id: str,
    model: str,
    output_dir: str,
    agent: str = "terminus-2",
    dataset: str = DEFAULT_TERMINAL_BENCH_DATASET,
    dry_run: bool = True,
    execute: bool = False,
    result_path: str | Path | None = None,
    suite_budget: dict[str, Any] | None = None,
    subprocess_run=subprocess.run,
) -> dict[str, Any]:
    prerequisites = check_terminal_bench_prerequisites(require_harbor=execute)
    command = build_terminal_bench_command(task_id=task_id, model=model, output_dir=output_dir, agent=agent, dataset=dataset)
    result_file = Path(result_path) if result_path is not None else Path(output_dir) / "result.json"
    payload = {
        "task_id": task_id,
        "model": model,
        "agent": agent,
        "dataset": dataset,
        "output_dir": output_dir,
        "command": command,
        "prerequisites": prerequisites,
        "dry_run": dry_run,
        "execute": execute,
        "result_path": str(result_file),
        "suite_budget": suite_budget or {},
    }

    if dry_run and not execute:
        payload["ready"] = all(prerequisites.values())
        return payload

    if not execute:
        raise ValueError("Terminal-Bench execution requires explicit execute=True")

    missing = [name for name, available in prerequisites.items() if not available]
    if missing:
        raise RuntimeError(f"Missing Terminal-Bench prerequisites: {', '.join(missing)}")

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
        payload["parsed_result"] = parse_terminal_bench_result(result_file)
    return payload


def parse_terminal_bench_result(path: str | Path) -> dict[str, Any]:
    result_path = Path(path)
    with result_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    success = _first_present(raw, "success", "passed", "resolved")
    quality_score = _first_present(raw, "quality_score", "score")
    status = _first_present(raw, "status", "result")
    details = raw.get("details") if isinstance(raw, dict) else None
    return {
        "success": bool(success) if success is not None else False,
        "quality_score": float(quality_score) if quality_score is not None else (1.0 if success else 0.0),
        "status": str(status) if status is not None else None,
        "details": details if isinstance(details, dict) else {},
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
