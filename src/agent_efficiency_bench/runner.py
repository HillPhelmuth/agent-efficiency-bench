from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from agent_efficiency_bench.agents.base import Agent
from agent_efficiency_bench.evaluators.base import Evaluator
from agent_efficiency_bench.io import write_jsonl
from agent_efficiency_bench.schemas import BenchmarkTask, RunManifest, RunResult


class BenchmarkRunner:
    def __init__(
        self,
        agent: Agent,
        evaluator: Evaluator,
        output_dir: str | Path,
        tasks_path: str | None = None,
        run_suite_id: str | None = None,
    ):
        self.agent = agent
        self.evaluator = evaluator
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results_path = self.output_dir / "run_results.jsonl"
        self.telemetry_path = self.output_dir / "run_telemetry.jsonl"
        self.manifest_path = self.output_dir / "manifest.json"
        self.tasks_path = tasks_path
        self.run_suite_id = run_suite_id or f"suite-{uuid.uuid4().hex[:12]}"
        self.task_ids: list[str] = []

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
        self.task_ids.append(task.task_id)
        self._write_manifest()
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

    def _write_manifest(self) -> None:
        config = getattr(self.agent, "config", None)
        manifest = RunManifest(
            run_suite_id=self.run_suite_id,
            agent=self.agent.name,
            model=getattr(self.agent, "model", None) or getattr(config, "model", "unknown"),
            output_dir=str(self.output_dir),
            tasks_path=self.tasks_path,
            task_ids=self.task_ids,
            tools_configured=_tool_names(getattr(config, "tools", None)),
            git_commit=_git_commit(),
        )
        self.manifest_path.write_text(manifest.model_dump_json(exclude_none=True, indent=2), encoding="utf-8")


def _read_existing(path: Path) -> list[Any]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(_DictModel(json.loads(line)))
    return rows


def _tool_names(tools: list[dict[str, Any]] | None) -> list[str]:
    names = []
    for tool in tools or []:
        if tool.get("type") == "function":
            function = tool.get("function") or {}
            names.append(function.get("name") or "function")
        else:
            names.append(str(tool.get("type") or "unknown"))
    return names


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


class _DictModel:
    def __init__(self, data: dict[str, Any]):
        self.data = data

    def model_dump_json(self, exclude_none: bool = True) -> str:
        if exclude_none:
            return json.dumps(_drop_none(self.data))
        return json.dumps(self.data)


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _drop_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_none(v) for v in value]
    return value
