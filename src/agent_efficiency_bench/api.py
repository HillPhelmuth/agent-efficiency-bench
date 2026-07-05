from __future__ import annotations

from collections import Counter
from itertools import product
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent_efficiency_bench.agents.openrouter_answer import OpenRouterAnswerAgent
from agent_efficiency_bench.agents.openrouter_tool_loop import OpenRouterToolLoopAgent
from agent_efficiency_bench.evaluators.registry import RegistryEvaluator
from agent_efficiency_bench.harnesses.assistantbench import native_web_search_tool
from agent_efficiency_bench.io import read_jsonl
from agent_efficiency_bench.reporting import summarize_by_dimensions
from agent_efficiency_bench.runner import BenchmarkRunner, SuiteBudgetConfig
from agent_efficiency_bench.scoring import coerce_persisted_quality_score
from agent_efficiency_bench.schemas import BenchmarkTask, ModelConfig, RunResult, RunTelemetry

DEFAULT_TASKS_PATH = "data/tasks/public_efficiency_subset.jsonl"
DEFAULT_OUTPUT_ROOT = "runs/api"
SUPPORTED_SCAFFOLDS = ["answer-only", "react-tool-loop"]
SUPPORTED_GROUP_BY = [
    "category",
    "source",
    "model",
    "agent",
    "scaffold",
    "horizon",
    "requires_external_search",
    "tools_enabled",
    "trial_index",
]
CHART_METRICS = [
    "total_runs",
    "success_rate",
    "mean_quality",
    "total_cost",
    "p50_latency_seconds",
    "total_tokens",
    "cost_per_success",
]


class RunRequest(BaseModel):
    tasks_path: str = DEFAULT_TASKS_PATH
    output_root: str = DEFAULT_OUTPUT_ROOT
    models: list[str] = Field(min_length=1)
    scaffolds: list[Literal["answer-only", "react-tool-loop"]] = Field(default_factory=lambda: ["answer-only"])
    categories: list[str | None] = Field(default_factory=lambda: [None])
    web_search: list[bool] = Field(default_factory=lambda: [False])
    limit: int | None = Field(default=None, ge=1)
    n_trials: int = Field(default=1, ge=1)
    max_completion_tokens: int = Field(default=2048, ge=1)
    max_suite_usd: float | None = Field(default=None, ge=0)
    max_suite_seconds: float | None = Field(default=None, ge=0)
    max_suite_tasks: int | None = Field(default=None, ge=1)
    max_suite_failures: int | None = Field(default=None, ge=1)
    group_by: list[str] = Field(default_factory=lambda: ["category", "model", "scaffold"])
    dry_run: bool = False


class SuiteBudgetConfigModel(BaseModel):
    max_suite_estimated_usd: float | None = None
    max_suite_wall_clock_seconds: float | None = None
    max_suite_tasks: int | None = None
    max_suite_failures: int | None = None

    def to_runner_config(self) -> SuiteBudgetConfig:
        return SuiteBudgetConfig(
            max_suite_estimated_usd=self.max_suite_estimated_usd,
            max_suite_wall_clock_seconds=self.max_suite_wall_clock_seconds,
            max_suite_tasks=self.max_suite_tasks,
            max_suite_failures=self.max_suite_failures,
        )


class BenchmarkCombination(BaseModel):
    job_id: str
    index: int
    run_id_prefix: str
    tasks_path: str
    output_dir: str
    model: str
    scaffold: Literal["answer-only", "react-tool-loop"]
    category: str | None = None
    enable_web_search: bool = False
    limit: int | None = None
    n_trials: int = 1
    max_completion_tokens: int = 2048
    suite_budget: SuiteBudgetConfigModel = Field(default_factory=SuiteBudgetConfigModel)


class JobRecord(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed", "dry_run"]
    request: RunRequest
    combinations: list[BenchmarkCombination]
    completed_combinations: int = 0
    total_combinations: int
    telemetry: list[RunTelemetry] = Field(default_factory=list)
    telemetry_paths: list[str] = Field(default_factory=list)
    error: str | None = None


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create(self, record: JobRecord) -> JobRecord:
        with self._lock:
            self._jobs[record.job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=f"Unknown run job: {job_id}") from exc

    def list(self) -> list[JobRecord]:
        with self._lock:
            return list(self._jobs.values())

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        with self._lock:
            record = self._jobs[job_id]
            data = record.model_dump()
            data.update(changes)
            updated = JobRecord.model_validate(data)
            self._jobs[job_id] = updated
            return updated


def create_app(*, run_async: bool = True) -> FastAPI:
    app = FastAPI(title="Agent Efficiency Bench API")
    app.state.registry = JobRegistry()
    web_dir = Path(__file__).with_name("web")
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.get("/")
    def ui() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    @app.get("/api/options")
    def options() -> dict[str, Any]:
        return {
            "default_tasks_path": DEFAULT_TASKS_PATH,
            "default_output_root": DEFAULT_OUTPUT_ROOT,
            "scaffolds": SUPPORTED_SCAFFOLDS,
            "web_search": [False, True],
            "group_by_dimensions": SUPPORTED_GROUP_BY,
            "example_models": ["openai/gpt-5.4-nano"],
        }

    @app.get("/api/catalog")
    def catalog(tasks_path: str = Query(DEFAULT_TASKS_PATH)) -> dict[str, Any]:
        tasks = load_tasks(tasks_path)
        return task_catalog(tasks, tasks_path=tasks_path)

    @app.get("/api/runs")
    def list_runs() -> list[dict[str, Any]]:
        return [_job_public(record) for record in app.state.registry.list()]

    @app.post("/api/runs")
    def create_run(request: RunRequest) -> dict[str, Any]:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        combinations = expand_run_request(request, job_id=job_id)
        status = "dry_run" if request.dry_run else "queued"
        record = JobRecord(
            job_id=job_id,
            status=status,
            request=request,
            combinations=combinations,
            total_combinations=len(combinations),
        )
        app.state.registry.create(record)
        if not request.dry_run:
            if run_async:
                thread = threading.Thread(target=_run_job, args=(app.state.registry, job_id), daemon=True)
                thread.start()
            else:
                _run_job(app.state.registry, job_id)
            record = app.state.registry.get(job_id)
        return _job_public(record)

    @app.get("/api/runs/{job_id}")
    def get_run(job_id: str) -> dict[str, Any]:
        return _job_public(app.state.registry.get(job_id))

    @app.get("/api/runs/{job_id}/results")
    def get_results(job_id: str) -> dict[str, Any]:
        record = app.state.registry.get(job_id)
        task_path = record.request.tasks_path
        if record.telemetry_paths:
            payload = chart_summary_for_runs(task_path, record.telemetry_paths, record.request.group_by)
        else:
            payload = chart_summary_for_telemetry(task_path, record.telemetry, record.request.group_by)
        payload["job"] = _job_public(record)
        return payload

    return app


def _job_public(record: JobRecord) -> dict[str, Any]:
    return {
        "job_id": record.job_id,
        "status": record.status,
        "completed_combinations": record.completed_combinations,
        "total_combinations": record.total_combinations,
        "combinations": [combo.model_dump() for combo in record.combinations],
        "telemetry_paths": record.telemetry_paths,
        "error": record.error,
    }


def _run_job(registry: JobRegistry, job_id: str) -> None:
    record = registry.update(job_id, status="running")
    telemetry: list[RunTelemetry] = []
    telemetry_paths: list[str] = []
    try:
        for index, combination in enumerate(record.combinations, start=1):
            telemetry.extend(execute_benchmark_combination(combination))
            telemetry_path = str(Path(combination.output_dir) / "run_telemetry.jsonl")
            if telemetry_path not in telemetry_paths and Path(telemetry_path).exists():
                telemetry_paths.append(telemetry_path)
            registry.update(
                job_id,
                completed_combinations=index,
                telemetry=telemetry,
                telemetry_paths=telemetry_paths,
            )
        registry.update(job_id, status="completed", telemetry=telemetry, telemetry_paths=telemetry_paths)
    except Exception:  # pragma: no cover - failure details are reported through the API
        registry.update(job_id, status="failed", error=traceback.format_exc(), telemetry=telemetry, telemetry_paths=telemetry_paths)


def load_tasks(tasks_path: str) -> list[BenchmarkTask]:
    return [BenchmarkTask.model_validate(row) for row in read_jsonl(tasks_path)]


def task_catalog(tasks: list[BenchmarkTask], *, tasks_path: str) -> dict[str, Any]:
    categories = Counter(task.category for task in tasks)
    sources = Counter(task.source for task in tasks)
    horizons = Counter(task.complexity.horizon for task in tasks)
    return {
        "tasks_path": tasks_path,
        "total_tasks": len(tasks),
        "categories": dict(sorted(categories.items())),
        "sources": dict(sorted(sources.items())),
        "horizons": dict(sorted(horizons.items())),
        "requires_external_search": sum(1 for task in tasks if task.complexity.requires_external_search),
    }


def expand_run_request(request: RunRequest, *, job_id: str) -> list[BenchmarkCombination]:
    combinations = []
    suite_budget = SuiteBudgetConfigModel(
        max_suite_estimated_usd=request.max_suite_usd,
        max_suite_wall_clock_seconds=request.max_suite_seconds,
        max_suite_tasks=request.max_suite_tasks,
        max_suite_failures=request.max_suite_failures,
    )
    for index, (model, scaffold, category, enable_web_search) in enumerate(
        product(request.models, request.scaffolds, request.categories, request.web_search),
        start=1,
    ):
        limit, n_trials = _normalize_task_count_and_trials(request.limit, request.n_trials)
        safe_model = _safe_path_part(model)
        safe_category = _safe_path_part(category or "all")
        search_part = "web-search" if enable_web_search else "no-web-search"
        output_dir = str(Path(request.output_root) / job_id / f"{index:03d}-{safe_model}-{scaffold}-{safe_category}-{search_part}")
        combinations.append(
            BenchmarkCombination(
                job_id=job_id,
                index=index,
                run_id_prefix=f"{job_id}-{index:03d}",
                tasks_path=request.tasks_path,
                output_dir=output_dir,
                model=model,
                scaffold=scaffold,
                category=category,
                enable_web_search=enable_web_search,
                limit=limit,
                n_trials=n_trials,
                max_completion_tokens=request.max_completion_tokens,
                suite_budget=suite_budget,
            )
        )
    return combinations


def _normalize_task_count_and_trials(limit: int | None, n_trials: int) -> tuple[int | None, int]:
    """Treat the legacy UI Trials field as task count, not repeated trials.

    The dashboard originally exposed both a default ``limit=1`` and a visible
    ``n_trials`` field. Users reasonably interpreted that field as "run N
    tasks", but the runner interpreted it as "repeat each selected task N
    times", causing the first benchmark task to be run repeatedly. Preserve the
    wire field for backwards compatibility while normalizing API/UI requests to
    single-trial runs over the first N tasks.
    """
    if n_trials > 1:
        if limit is None or limit <= 1:
            return n_trials, 1
        return limit, 1
    return limit, 1


def execute_benchmark_combination(combination: BenchmarkCombination) -> list[RunTelemetry]:
    tasks = load_tasks(combination.tasks_path)
    selected = [task for task in tasks if combination.category is None or task.category == combination.category]
    if combination.limit is not None:
        selected = selected[: combination.limit]
    tools = [native_web_search_tool()] if combination.enable_web_search else None
    config = ModelConfig(model=combination.model, max_completion_tokens=combination.max_completion_tokens, tools=tools)
    if combination.scaffold == "answer-only":
        agent = OpenRouterAnswerAgent(config=config)
    elif combination.scaffold == "react-tool-loop":
        agent = OpenRouterToolLoopAgent(config=config)
    else:  # pragma: no cover - guarded by pydantic literal validation
        raise ValueError(f"Unsupported scaffold: {combination.scaffold}")
    runner = BenchmarkRunner(
        agent=agent,
        evaluator=RegistryEvaluator(),
        output_dir=combination.output_dir,
        tasks_path=combination.tasks_path,
        run_suite_id=combination.run_id_prefix,
        suite_budget=combination.suite_budget.to_runner_config(),
    )
    results = runner.run_tasks(selected, n_trials=combination.n_trials)
    return [result.telemetry for result in results]


def chart_summary_for_runs(tasks_path: str, telemetry_paths: list[str], group_by: list[str]) -> dict[str, Any]:
    tasks = {task.task_id: task for task in load_tasks(tasks_path)}
    runs = []
    for telemetry_path in telemetry_paths:
        result_path = Path(telemetry_path).with_name("run_results.jsonl")
        if result_path.exists():
            runs.extend(_reevaluated_telemetry(result_path, tasks))
        else:
            runs.extend(_telemetry_from_row(row) for row in read_jsonl(telemetry_path))
    task_rows = {task_id: task.model_dump() for task_id, task in tasks.items()}
    summary = summarize_by_dimensions(task_rows, runs, _validated_group_by(group_by))
    return {"summary": summary, "chart_rows": _chart_rows(summary)}


def chart_summary_for_telemetry(tasks_path: str, runs: list[RunTelemetry], group_by: list[str]) -> dict[str, Any]:
    tasks = {task.task_id: task.model_dump() for task in load_tasks(tasks_path)}
    summary = summarize_by_dimensions(tasks, runs, _validated_group_by(group_by))
    return {"summary": summary, "chart_rows": _chart_rows(summary)}


def _reevaluated_telemetry(result_path: Path, tasks: dict[str, BenchmarkTask]) -> list[RunTelemetry]:
    evaluator = RegistryEvaluator()
    telemetry = []
    for row in read_jsonl(result_path):
        result = RunResult.model_validate(row)
        task = tasks.get(result.telemetry.task_id)
        if _has_stored_llm_evaluation(result):
            result.telemetry = _coerced_telemetry(result.telemetry)
            telemetry.append(result.telemetry)
            continue
        if task is not None:
            score = evaluator.evaluate(task, result)
            result.telemetry.success = score.success
            result.telemetry.quality_score = score.quality_score
            if not score.evaluated and result.telemetry.terminated_by is None:
                result.telemetry.terminated_by = "not_evaluated"
            elif score.evaluated and result.telemetry.terminated_by == "not_evaluated":
                result.telemetry.terminated_by = "success" if score.success else "evaluated"
        telemetry.append(_coerced_telemetry(result.telemetry))
    return telemetry


def _telemetry_from_row(row: dict[str, Any]) -> RunTelemetry:
    return _coerced_telemetry(RunTelemetry.model_validate(row))


def _coerced_telemetry(telemetry: RunTelemetry) -> RunTelemetry:
    telemetry.quality_score = coerce_persisted_quality_score(
        telemetry.quality_score,
        success=telemetry.success,
        terminated_by=telemetry.terminated_by,
    )
    return telemetry


def _has_stored_llm_evaluation(result: RunResult) -> bool:
    evaluation = result.output.get("evaluation")
    if not isinstance(evaluation, dict):
        return False
    details = evaluation.get("details")
    return isinstance(details, dict) and details.get("judge") == "llm"


def _validated_group_by(group_by: list[str]) -> list[str]:
    invalid = [dimension for dimension in group_by if dimension not in SUPPORTED_GROUP_BY]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unsupported group_by dimensions: {', '.join(invalid)}")
    return group_by or ["category", "model", "scaffold"]


def _chart_rows(summary: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for group, values in sorted(summary.items()):
        row = {"group": group}
        for metric in CHART_METRICS:
            row[metric] = values.get(metric)
        rows.append(row)
    return rows


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in value).strip("-") or "value"


def main() -> None:
    import uvicorn

    uvicorn.run("agent_efficiency_bench.api:app", host="127.0.0.1", port=8000, reload=False)


app = create_app()
