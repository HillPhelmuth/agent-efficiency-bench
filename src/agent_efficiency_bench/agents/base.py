from __future__ import annotations

from pathlib import Path
from typing import Protocol

from agent_efficiency_bench.schemas import BenchmarkTask, RunResult


class Agent(Protocol):
    name: str
    model: str

    def run(self, task: BenchmarkTask, artifact_dir: str | Path) -> RunResult: ...
