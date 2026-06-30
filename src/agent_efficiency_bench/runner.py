from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_efficiency_bench.agents.base import Agent
from agent_efficiency_bench.evaluators.base import Evaluator
from agent_efficiency_bench.io import write_jsonl
from agent_efficiency_bench.schemas import BenchmarkTask, RunResult


class BenchmarkRunner:
    def __init__(self, agent: Agent, evaluator: Evaluator, output_dir: str | Path):
        self.agent = agent
        self.evaluator = evaluator
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_path = self.output_dir / "run_results.jsonl"
        self.telemetry_path = self.output_dir / "run_telemetry.jsonl"

    def run_task(self, task: BenchmarkTask) -> RunResult:
        artifact_dir = self.output_dir / task.task_id
        result = self.agent.run(task, artifact_dir=artifact_dir)
        score = self.evaluator.evaluate(task, result)
        result.telemetry.success = score.success
        result.telemetry.quality_score = score.quality_score
        if result.telemetry.terminated_by == "not_evaluated":
            result.telemetry.terminated_by = "success" if score.success else "evaluated"
        result.output["evaluation"] = score.model_dump(exclude_none=True)
        self._append_result(result)
        return result

    def run_tasks(self, tasks: list[BenchmarkTask], limit: int | None = None) -> list[RunResult]:
        selected = tasks[:limit] if limit is not None else tasks
        return [self.run_task(task) for task in selected]

    def _append_result(self, result: RunResult) -> None:
        existing_results = []
        existing_telemetry = []
        if self.results_path.exists():
            existing_results = _read_existing(self.results_path)
        if self.telemetry_path.exists():
            existing_telemetry = _read_existing(self.telemetry_path)
        write_jsonl(self.results_path, [*existing_results, result])
        write_jsonl(self.telemetry_path, [*existing_telemetry, result.telemetry])


def _read_existing(path: Path) -> list[Any]:
    import json

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(_DictModel(json.loads(line)))
    return rows


class _DictModel:
    def __init__(self, data: dict[str, Any]):
        self.data = data

    def model_dump_json(self, exclude_none: bool = True) -> str:
        import json

        if exclude_none:
            return json.dumps(_drop_none(self.data))
        return json.dumps(self.data)


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _drop_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_none(v) for v in value]
    return value
