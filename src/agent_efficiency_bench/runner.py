from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_efficiency_bench.agents.base import Agent
from agent_efficiency_bench.evaluators.base import Evaluator
from agent_efficiency_bench.io import write_jsonl
from agent_efficiency_bench.schemas import BenchmarkTask, RunManifest, RunResult


@dataclass
class SuiteBudgetConfig:
    max_suite_estimated_usd: float | None = None
    max_suite_wall_clock_seconds: float | None = None
    max_suite_tasks: int | None = None
    max_suite_failures: int | None = None


class BenchmarkRunner:
    def __init__(
        self,
        agent: Agent,
        evaluator: Evaluator,
        output_dir: str | Path,
        tasks_path: str | None = None,
        run_suite_id: str | None = None,
        suite_budget: SuiteBudgetConfig | None = None,
        time_fn: Callable[[], float] | None = None,
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
        self.budgets: list[dict[str, Any]] = []
        self.suite_budget = suite_budget or SuiteBudgetConfig()
        self.time_fn = time_fn or time.perf_counter
        self.suite_started_at = self.time_fn()
        self.suite_tasks_completed = 0
        self.suite_failures = 0
        self.suite_estimated_usd = 0.0
        self.suite_terminated_by: str | None = None
        self.requested_trial_count = 1
        self.executed_trial_indices: set[int] = set()

    def run_task(self, task: BenchmarkTask, trial_index: int | None = None) -> RunResult:
        artifact_dir = self.output_dir / task.task_id
        if trial_index is not None and self.requested_trial_count > 1:
            artifact_dir = artifact_dir / f"trial-{trial_index:03d}"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        result = self.agent.run(task, artifact_dir=artifact_dir)
        if trial_index is not None:
            result.telemetry.trial_index = trial_index
            result.telemetry.run_id = f"{result.telemetry.run_id}__trial_{trial_index:03d}"
        score = self.evaluator.evaluate(task, result)
        result.telemetry.success = score.success
        result.telemetry.quality_score = score.quality_score
        if not score.evaluated and result.telemetry.terminated_by is None:
            result.telemetry.terminated_by = "not_evaluated"
        elif result.telemetry.terminated_by == "not_evaluated" and score.evaluated:
            result.telemetry.terminated_by = "success" if score.success else "evaluated"
        result.output["evaluation"] = score.model_dump(exclude_none=True)
        self._append_result(result)
        self.task_ids.append(task.task_id)
        self.budgets.append(task.budgets.model_dump())
        if trial_index is not None:
            self.executed_trial_indices.add(trial_index)
        self._record_suite_result(result)
        self._write_manifest()
        return result

    def run_tasks(self, tasks: list[BenchmarkTask], limit: int | None = None, n_trials: int = 1) -> list[RunResult]:
        selected = tasks[:limit] if limit is not None else tasks
        self.requested_trial_count = max(n_trials, 1)
        results: list[RunResult] = []
        for task in selected:
            for trial_index in range(self.requested_trial_count):
                reason = self._suite_limit_reason()
                if reason is not None:
                    self.suite_terminated_by = reason
                    break
                results.append(self.run_task(task, trial_index=trial_index if self.requested_trial_count > 1 else None))
                if self.suite_terminated_by is not None:
                    break
            if self.suite_terminated_by is not None:
                break
        self._write_manifest()
        return results

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
            trial_count=self.requested_trial_count,
            trial_indices=sorted(self.executed_trial_indices),
            scaffold=getattr(self.agent, "scaffold", None),
            tools_configured=_tool_names(getattr(config, "tools", None)),
            budget=_budget_summary(self.budgets),
            suite_budget=self._suite_budget_summary(),
            git_commit=_git_commit(),
            environment=_environment_info(),
        )
        self.manifest_path.write_text(manifest.model_dump_json(exclude_none=True, indent=2), encoding="utf-8")

    def _record_suite_result(self, result: RunResult) -> None:
        self.suite_tasks_completed += 1
        self.suite_estimated_usd += result.telemetry.estimated_usd
        if not result.telemetry.success:
            self.suite_failures += 1
        reason = self._suite_limit_reason()
        if reason is not None:
            self.suite_terminated_by = reason

    def _suite_elapsed_seconds(self) -> float:
        return self.time_fn() - self.suite_started_at

    def _suite_limit_reason(self) -> str | None:
        if self.suite_terminated_by is not None:
            return self.suite_terminated_by
        if self.suite_budget.max_suite_tasks is not None and self.suite_tasks_completed >= self.suite_budget.max_suite_tasks:
            return "suite_budget_tasks"
        if self.suite_budget.max_suite_failures is not None and self.suite_failures >= self.suite_budget.max_suite_failures:
            return "suite_budget_failures"
        if self.suite_budget.max_suite_estimated_usd is not None and self.suite_estimated_usd >= self.suite_budget.max_suite_estimated_usd:
            return "suite_budget_cost"
        if (
            self.suite_budget.max_suite_wall_clock_seconds is not None
            and self._suite_elapsed_seconds() >= self.suite_budget.max_suite_wall_clock_seconds
        ):
            return "suite_budget_time"
        return None

    def _suite_budget_summary(self) -> dict[str, Any]:
        limits = {key: value for key, value in asdict(self.suite_budget).items() if value is not None}
        if not limits and self.suite_tasks_completed == 0 and self.suite_failures == 0 and self.suite_estimated_usd == 0.0:
            return {}
        return {
            "limits": limits,
            "observed": {
                "tasks_completed": self.suite_tasks_completed,
                "failures": self.suite_failures,
                "estimated_usd": self.suite_estimated_usd,
                "wall_clock_seconds": self._suite_elapsed_seconds(),
            },
            "terminated_by": self.suite_terminated_by,
            "aborted": self.suite_terminated_by is not None,
        }


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


def _budget_summary(budgets: list[dict[str, Any]]) -> dict[str, Any]:
    if not budgets:
        return {}
    if all(budget == budgets[0] for budget in budgets):
        return budgets[0]
    keys = sorted({key for budget in budgets for key in budget})
    summary: dict[str, Any] = {"task_count": len(budgets), "per_field": {}}
    for key in keys:
        values = [budget.get(key) for budget in budgets if key in budget]
        if values and all(isinstance(value, (int, float)) for value in values):
            summary["per_field"][key] = {"min": min(values), "max": max(values)}
        else:
            summary["per_field"][key] = {"values": sorted({str(value) for value in values})}
    return summary


def _environment_info() -> dict[str, Any]:
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "git_commit": _git_commit(),
        "command": " ".join(sys.argv) if sys.argv else None,
    }


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
