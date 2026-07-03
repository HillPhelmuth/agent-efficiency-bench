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

from agent_efficiency_bench import __version__
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
        self.completed_tasks: list[BenchmarkTask] = []
        self.provider_observations: list[dict[str, Any]] = []
        self.harness_observations: list[dict[str, Any]] = []

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
        self.completed_tasks.append(task)
        if trial_index is not None:
            self.executed_trial_indices.add(trial_index)
        self._record_provider_result(result)
        self._record_harness_result(task, result)
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
            source_revisions=_source_revision_summary(self.completed_tasks),
            evaluator=_evaluator_info(self.evaluator),
            harness=_harness_info(self.completed_tasks, self.harness_observations),
            provider=_provider_info(self.agent, self.provider_observations),
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

    def _record_provider_result(self, result: RunResult) -> None:
        provider_data = result.output.get("provider_response")
        if isinstance(provider_data, dict):
            self.provider_observations.append(provider_data)

    def _record_harness_result(self, task: BenchmarkTask, result: RunResult) -> None:
        harness_result = result.output.get("harness_result")
        if isinstance(harness_result, dict):
            observation = {
                "checker": task.success_criteria.checker or task.success_criteria.type,
                "source": task.source,
                "status": harness_result.get("status"),
            }
            details = harness_result.get("details")
            if isinstance(details, dict):
                for key in ("harness", "harness_version", "version"):
                    value = details.get(key)
                    if value is not None:
                        observation[key] = value
            raw = harness_result.get("raw")
            if isinstance(raw, dict):
                for key in ("harness", "harness_version", "version"):
                    value = raw.get(key)
                    if value is not None:
                        observation[key] = value
            self.harness_observations.append(observation)

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


def _source_revision_summary(tasks: list[BenchmarkTask]) -> dict[str, Any]:
    if not tasks:
        return {}
    summary: dict[str, dict[str, Any]] = {}
    for task in tasks:
        source_entry = summary.setdefault(
            task.source,
            {
                "source_type": task.source_type,
                "source_url": task.source_url,
                "revision": "unknown",
                "details": {},
            },
        )
        if source_entry.get("source_url") is None and task.source_url is not None:
            source_entry["source_url"] = task.source_url
        details = source_entry["details"]
        env = task.environment or {}

        split = env.get("split")
        if split:
            details["split"] = split

        if task.source == "SWE-bench/SWE-bench_Lite":
            _append_unique(details, "repos", env.get("repo"))
            _append_unique(details, "base_commits", env.get("base_commit"))
            _append_unique(details, "versions", env.get("version"))
            if details.get("base_commits") or details.get("versions"):
                source_entry["revision"] = "per_task"
        elif task.source == "AssistantBench/AssistantBench":
            source_entry["revision"] = details.get("split") or "unknown"
        elif task.source in {"harbor-framework/terminal-bench", "sierra-research/tau2-bench"}:
            repo, revision = _github_source_identity(task)
            if repo:
                details["repo"] = repo
            if revision:
                source_entry["revision"] = revision
            elif source_entry["revision"] == "unknown":
                source_entry["revision"] = "unknown"

    for entry in summary.values():
        if not entry["details"]:
            entry.pop("details")
    return summary


def _github_source_identity(task: BenchmarkTask) -> tuple[str | None, str | None]:
    source_url = task.source_url or ""
    if "raw.githubusercontent.com/" in source_url:
        parts = source_url.split("raw.githubusercontent.com/", 1)[1].split("/")
        if len(parts) >= 3:
            return f"{parts[0]}/{parts[1]}", parts[2]
    if "github.com/" in source_url and "/tree/" in source_url:
        tail = source_url.split("github.com/", 1)[1]
        repo_part, _, rest = tail.partition("/tree/")
        revision = rest.split("/", 1)[0] if rest else None
        return repo_part or None, revision or None
    repo = task.environment.get("source_repo") if isinstance(task.environment, dict) else None
    return repo, None


def _append_unique(container: dict[str, Any], key: str, value: Any) -> None:
    if value in (None, ""):
        return
    values = container.setdefault(key, [])
    if value not in values:
        values.append(value)


def _evaluator_info(evaluator: Evaluator) -> dict[str, Any]:
    info = {
        "name": evaluator.__class__.__name__,
        "package_version": __version__,
        "checker": getattr(evaluator, "checker_name", None),
        "source": getattr(evaluator, "source", None),
    }
    return {key: value for key, value in info.items() if value is not None}


def _harness_info(tasks: list[BenchmarkTask], observations: list[dict[str, Any]]) -> dict[str, Any]:
    required_checkers = sorted(
        {
            checker
            for task in tasks
            for checker in [task.success_criteria.checker or task.success_criteria.type]
            if checker in {"swebench_harness", "terminal_bench_harness", "tau2_harness"}
        }
    )
    if not required_checkers and not observations:
        return {}

    observed = []
    for observation in observations:
        observed.append(
            {
                "checker": observation.get("checker") or "unknown",
                "source": observation.get("source") or "unknown",
                "identity": observation.get("harness") or observation.get("checker") or "unknown",
                "version": observation.get("harness_version") or observation.get("version") or "unknown",
                "status": observation.get("status") or "unknown",
            }
        )

    return {
        "required_checkers": required_checkers,
        "observed": observed,
        "identity": observed[0]["identity"] if len(observed) == 1 else ("multiple" if observed else "unknown"),
        "version": observed[0]["version"] if len(observed) == 1 else ("multiple" if observed else "unknown"),
    }


def _provider_info(agent: Agent, observations: list[dict[str, Any]]) -> dict[str, Any]:
    config = getattr(agent, "config", None)
    requested_provider = getattr(config, "provider", None) or "unknown"
    requested_model = getattr(config, "model", None) or getattr(agent, "model", None) or "unknown"
    returned_models = sorted(
        {
            str(value)
            for observation in observations
            for value in [observation.get("returned_model")]
            if value
        }
    )
    upstream_providers = sorted(
        {
            str(value)
            for observation in observations
            for value in [observation.get("provider")]
            if value
        }
    )
    routes = sorted(
        {
            json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            for observation in observations
            for value in [observation.get("route") or observation.get("routing")]
            if value is not None
        }
    )
    return {
        "requested_provider": requested_provider,
        "requested_model": requested_model,
        "returned_models": returned_models,
        "upstream_providers": upstream_providers,
        "routes": routes,
    }


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
