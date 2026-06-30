from __future__ import annotations

import json
import shutil
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


def parse_terminal_bench_result(path: str | Path) -> dict[str, Any]:
    result_path = Path(path)
    with result_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)
