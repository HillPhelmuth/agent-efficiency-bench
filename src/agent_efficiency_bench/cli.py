from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import time

import typer
from rich.console import Console
from rich.table import Table

from agent_efficiency_bench.agents.openrouter_answer import OpenRouterAnswerAgent
from agent_efficiency_bench.agents.openrouter_tool_loop import OpenRouterToolLoopAgent
from agent_efficiency_bench.evaluators.registry import RegistryEvaluator
from agent_efficiency_bench.harnesses.assistantbench import (
    model_config_for_assistantbench_mode,
    native_web_search_tool,
)
from agent_efficiency_bench.harnesses.swe_bench import (
    DEFAULT_SWE_BENCH_DATASET,
    build_swe_bench_eval_command,
    run_swe_bench_evaluation,
)
from agent_efficiency_bench.harnesses.tau2_bench import run_tau2_task
from agent_efficiency_bench.harnesses.terminal_bench import (
    DEFAULT_TERMINAL_BENCH_DATASET,
    build_terminal_bench_command,
    run_terminal_bench_task,
)
from agent_efficiency_bench.io import read_jsonl, write_jsonl
from agent_efficiency_bench.metrics import aggregate_runs
from agent_efficiency_bench.providers.openrouter import OpenRouterClient
from agent_efficiency_bench.reporting import summarize_by_category, summarize_by_dimensions, write_markdown_report
from agent_efficiency_bench.runner import BenchmarkRunner, SuiteBudgetConfig
from agent_efficiency_bench.schemas import BenchmarkTask, ModelConfig, RunTelemetry
from agent_efficiency_bench.sources import load_sources_from_config
from agent_efficiency_bench.task_audit import audit_tasks as audit_task_rows, format_audit_markdown

app = typer.Typer(help="Agentic efficiency benchmark tooling.")
console = Console()


def select_tasks(tasks: list[BenchmarkTask], category: str | None = None, limit: int | None = None) -> list[BenchmarkTask]:
    selected = [task for task in tasks if category is None or task.category == category]
    return selected[:limit] if limit is not None else selected


@app.command("build-subset")
def build_subset(
    config: str = typer.Option("configs/sources.yaml", help="Source config YAML."),
    output: str = typer.Option("data/tasks/public_efficiency_subset.jsonl", help="Output JSONL path."),
) -> None:
    """Extract small public benchmark subsets into the normalized task schema."""
    tasks = load_sources_from_config(config)
    count = write_jsonl(output, tasks)
    console.print(f"[green]Wrote {count} tasks[/green] to {output}")


@app.command("catalog")
def catalog(path: str) -> None:
    """Summarize a normalized task JSONL file."""
    rows = [BenchmarkTask.model_validate(row) for row in read_jsonl(path)]
    by_category = Counter(row.category for row in rows)
    by_source = Counter(row.source for row in rows)

    table = Table(title=f"Task catalog: {Path(path).name}")
    table.add_column("Dimension")
    table.add_column("Value")
    table.add_column("Count", justify="right")
    for value, count in sorted(by_category.items()):
        table.add_row("category", value, str(count))
    for value, count in sorted(by_source.items()):
        table.add_row("source", value, str(count))
    console.print(table)


@app.command("score-runs")
def score_runs(path: str) -> None:
    """Summarize run telemetry JSONL using success-gated efficiency metrics."""
    runs = [RunTelemetry.model_validate(row) for row in read_jsonl(path)]
    summary = aggregate_runs(runs)
    console.print_json(summary.model_dump_json(exclude_none=True))


@app.command("run-answer")
def run_answer(
    tasks: str = typer.Option("data/tasks/public_efficiency_subset.jsonl", help="Normalized task JSONL path."),
    model: str = typer.Option(..., help="OpenRouter model id, e.g. openai/gpt-5.4-nano."),
    category: str | None = typer.Option(None, help="Optional task category filter."),
    limit: int | None = typer.Option(None, help="Maximum tasks to run."),
    output_dir: str = typer.Option("runs/smoke", help="Output directory for traces and JSONL results."),
    max_completion_tokens: int = typer.Option(2048, help="Per-call max completion tokens."),
    enable_web_search: bool = typer.Option(False, help="Pass native web_search tool configuration to OpenRouter."),
    n_trials: int = typer.Option(1, help="Repeat each selected task this many times."),
    max_suite_usd: float | None = typer.Option(None, help="Abort before the next task after this suite spend is reached."),
    max_suite_seconds: float | None = typer.Option(None, help="Abort before the next task after this suite wall-clock time is reached."),
    max_suite_tasks: int | None = typer.Option(None, help="Maximum number of tasks to execute in this suite."),
    max_suite_failures: int | None = typer.Option(None, help="Abort before the next task after this many failed tasks."),
) -> None:
    """Run an answer-only OpenRouter baseline over normalized tasks."""
    loaded_tasks = [BenchmarkTask.model_validate(row) for row in read_jsonl(tasks)]
    selected = select_tasks(loaded_tasks, category=category, limit=limit)
    tools = [native_web_search_tool()] if enable_web_search else None
    agent = OpenRouterAnswerAgent(
        config=ModelConfig(model=model, max_completion_tokens=max_completion_tokens, tools=tools)
    )
    runner = BenchmarkRunner(
        agent=agent,
        evaluator=RegistryEvaluator(),
        output_dir=output_dir,
        tasks_path=tasks,
        suite_budget=SuiteBudgetConfig(
            max_suite_estimated_usd=max_suite_usd,
            max_suite_wall_clock_seconds=max_suite_seconds,
            max_suite_tasks=max_suite_tasks,
            max_suite_failures=max_suite_failures,
        ),
    )
    results = runner.run_tasks(selected, n_trials=n_trials)
    console.print(f"[green]Ran {len(results)} task(s)[/green]; outputs written to {output_dir}")


@app.command("run-tool-loop")
def run_tool_loop(
    tasks: str = typer.Option("data/tasks/public_efficiency_subset.jsonl", help="Normalized task JSONL path."),
    model: str = typer.Option(..., help="OpenRouter model id, e.g. openai/gpt-5.4-nano."),
    category: str | None = typer.Option(None, help="Optional task category filter."),
    limit: int | None = typer.Option(None, help="Maximum tasks to run."),
    output_dir: str = typer.Option("runs/tool-loop", help="Output directory for traces and JSONL results."),
    max_completion_tokens: int = typer.Option(2048, help="Per-call max completion tokens."),
    enable_web_search: bool = typer.Option(False, help="Pass native web_search tool configuration on the research step."),
    n_trials: int = typer.Option(1, help="Repeat each selected task this many times."),
    max_suite_usd: float | None = typer.Option(None, help="Abort before the next task after this suite spend is reached."),
    max_suite_seconds: float | None = typer.Option(None, help="Abort before the next task after this suite wall-clock time is reached."),
    max_suite_tasks: int | None = typer.Option(None, help="Maximum number of tasks to execute in this suite."),
    max_suite_failures: int | None = typer.Option(None, help="Abort before the next task after this many failed tasks."),
) -> None:
    """Run a minimal multi-step OpenRouter tool-loop scaffold."""
    loaded_tasks = [BenchmarkTask.model_validate(row) for row in read_jsonl(tasks)]
    selected = select_tasks(loaded_tasks, category=category, limit=limit)
    tools = [native_web_search_tool()] if enable_web_search else None
    agent = OpenRouterToolLoopAgent(
        config=ModelConfig(model=model, max_completion_tokens=max_completion_tokens, tools=tools)
    )
    runner = BenchmarkRunner(
        agent=agent,
        evaluator=RegistryEvaluator(),
        output_dir=output_dir,
        tasks_path=tasks,
        suite_budget=SuiteBudgetConfig(
            max_suite_estimated_usd=max_suite_usd,
            max_suite_wall_clock_seconds=max_suite_seconds,
            max_suite_tasks=max_suite_tasks,
            max_suite_failures=max_suite_failures,
        ),
    )
    results = runner.run_tasks(selected, n_trials=n_trials)
    console.print(f"[green]Ran {len(results)} task(s)[/green]; outputs written to {output_dir}")


@app.command("openrouter-smoke")
def openrouter_smoke(
    model: str = typer.Option(..., help="OpenRouter model id, e.g. openai/gpt-5.4-nano."),
) -> None:
    """Verify OpenRouter connectivity and token/cost telemetry with one tiny request."""
    try:
        client = OpenRouterClient()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    started = time.perf_counter()
    response = client.chat(
        ModelConfig(model=model, max_completion_tokens=16),
        [{"role": "user", "content": "Reply with exactly: ok"}],
    )
    latency = time.perf_counter() - started
    if response.prompt_tokens <= 0 or response.completion_tokens <= 0:
        raise typer.BadParameter("OpenRouter response did not include nonzero token usage")
    table = Table(title="OpenRouter smoke result")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("model", response.model)
    table.add_row("generation_id", response.generation_id)
    table.add_row("prompt_tokens", str(response.prompt_tokens))
    table.add_row("completion_tokens", str(response.completion_tokens))
    table.add_row("cost_usd", str(response.cost_usd))
    table.add_row("latency_seconds", f"{latency:.3f}")
    table.add_row("content", response.content)
    console.print(table)


@app.command("run-assistantbench")
def run_assistantbench(
    tasks: str = typer.Option("data/tasks/public_efficiency_subset.jsonl", help="Normalized task JSONL path."),
    model: str = typer.Option(..., help="OpenRouter model id."),
    limit: int | None = typer.Option(None, help="Maximum AssistantBench tasks to run."),
    output_dir: str = typer.Option("runs/assistantbench", help="Output directory."),
    mode: str = typer.Option("closed_book", help="closed_book or openrouter_web_plugin (native web search)."),
    n_trials: int = typer.Option(1, help="Repeat each selected task this many times."),
    max_suite_usd: float | None = typer.Option(None, help="Abort before the next task after this suite spend is reached."),
    max_suite_seconds: float | None = typer.Option(None, help="Abort before the next task after this suite wall-clock time is reached."),
    max_suite_tasks: int | None = typer.Option(None, help="Maximum number of tasks to execute in this suite."),
    max_suite_failures: int | None = typer.Option(None, help="Abort before the next task after this many failed tasks."),
) -> None:
    """Run AssistantBench web-research tasks through the OpenRouter answer agent."""
    loaded_tasks = [BenchmarkTask.model_validate(row) for row in read_jsonl(tasks)]
    selected = select_tasks(loaded_tasks, category="web_research", limit=limit)
    agent = OpenRouterAnswerAgent(config=model_config_for_assistantbench_mode(model, mode))
    runner = BenchmarkRunner(
        agent=agent,
        evaluator=RegistryEvaluator(),
        output_dir=output_dir,
        tasks_path=tasks,
        suite_budget=SuiteBudgetConfig(
            max_suite_estimated_usd=max_suite_usd,
            max_suite_wall_clock_seconds=max_suite_seconds,
            max_suite_tasks=max_suite_tasks,
            max_suite_failures=max_suite_failures,
        ),
    )
    runner.run_tasks(selected, n_trials=n_trials)
    console.print(f"[green]Ran {len(selected)} AssistantBench task(s)[/green]; outputs written to {output_dir}")


@app.command("terminal-bench-command")
def terminal_bench_command(
    task_id: str = typer.Option(..., help="Terminal-Bench task id."),
    model: str = typer.Option(..., help="OpenRouter model id."),
    output_dir: str = typer.Option("runs/terminal-bench", help="Harness output directory."),
    agent: str = typer.Option("terminus-2", help="Terminal-Bench/Harbor agent name."),
    dataset: str = typer.Option("terminal-bench/terminal-bench-2-1", help="Harbor dataset id."),
) -> None:
    """Print the official Terminal-Bench/Harbor command for a task."""
    cmd = build_terminal_bench_command(task_id=task_id, model=model, output_dir=output_dir, agent=agent, dataset=dataset)
    console.print(" ".join(cmd))


@app.command("run-terminal-bench-official")
def run_terminal_bench_official(
    task_id: str = typer.Option(..., help="Terminal-Bench task id."),
    model: str = typer.Option(..., help="OpenRouter model id."),
    output_dir: str = typer.Option("runs/terminal-bench", help="Harness output directory."),
    agent: str = typer.Option("terminus-2", help="Terminal-Bench/Harbor agent name."),
    dataset: str = typer.Option(DEFAULT_TERMINAL_BENCH_DATASET, help="Harbor dataset id."),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview the command by default; use --execute to run it."),
    max_suite_usd: float | None = typer.Option(None, help="Optional suite budget metadata to record with the planned run."),
    max_suite_seconds: float | None = typer.Option(None, help="Optional suite time-budget metadata to record with the planned run."),
    max_suite_tasks: int | None = typer.Option(None, help="Optional suite task-budget metadata to record with the planned run."),
    max_suite_failures: int | None = typer.Option(None, help="Optional suite failure-budget metadata to record with the planned run."),
) -> None:
    """Dry-run or execute the official Terminal-Bench harness behind an explicit flag."""
    result = run_terminal_bench_task(
        task_id=task_id,
        model=model,
        output_dir=output_dir,
        agent=agent,
        dataset=dataset,
        dry_run=dry_run,
        execute=not dry_run,
        suite_budget={
            "max_suite_estimated_usd": max_suite_usd,
            "max_suite_wall_clock_seconds": max_suite_seconds,
            "max_suite_tasks": max_suite_tasks,
            "max_suite_failures": max_suite_failures,
        },
    )
    console.print_json(json.dumps(result))


@app.command("swe-bench-command")
def swe_bench_command(
    predictions_path: str = typer.Option(..., help="SWE-bench predictions JSONL path."),
    run_id: str = typer.Option("aeb-smoke", help="SWE-bench run id."),
    dataset_name: str = typer.Option("SWE-bench/SWE-bench_Lite", help="SWE-bench dataset name."),
) -> None:
    """Print the official SWE-bench evaluation command for predictions."""
    cmd = build_swe_bench_eval_command(predictions_path=predictions_path, run_id=run_id, dataset_name=dataset_name)
    console.print(" ".join(cmd))


@app.command("run-swe-bench-official")
def run_swe_bench_official(
    predictions_path: str = typer.Option(..., help="SWE-bench predictions JSONL path."),
    run_id: str = typer.Option("aeb-smoke", help="SWE-bench run id."),
    dataset_name: str = typer.Option(DEFAULT_SWE_BENCH_DATASET, help="SWE-bench dataset name."),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview the evaluation command by default; use --execute to run it."),
    max_suite_usd: float | None = typer.Option(None, help="Optional suite budget metadata to record with the planned run."),
    max_suite_seconds: float | None = typer.Option(None, help="Optional suite time-budget metadata to record with the planned run."),
    max_suite_tasks: int | None = typer.Option(None, help="Optional suite task-budget metadata to record with the planned run."),
    max_suite_failures: int | None = typer.Option(None, help="Optional suite failure-budget metadata to record with the planned run."),
) -> None:
    """Dry-run or execute the official SWE-bench evaluation harness behind an explicit flag."""
    result = run_swe_bench_evaluation(
        predictions_path=predictions_path,
        run_id=run_id,
        dataset_name=dataset_name,
        dry_run=dry_run,
        execute=not dry_run,
        suite_budget={
            "max_suite_estimated_usd": max_suite_usd,
            "max_suite_wall_clock_seconds": max_suite_seconds,
            "max_suite_tasks": max_suite_tasks,
            "max_suite_failures": max_suite_failures,
        },
    )
    console.print_json(json.dumps(result))


@app.command("run-tau2-official")
def run_tau2_official(
    task_id: str = typer.Option(..., help="Normalized tau2 task id, e.g. tau2_bench_retail__55."),
    model: str = typer.Option(..., help="Model identifier passed to the external tau2 runner."),
    output_dir: str = typer.Option("runs/tau2-official", help="Harness output directory."),
    runner_module: str | None = typer.Option(None, help="Python module that knows how to run tau2 tasks. Required for --execute."),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Preview the planned run by default; use --execute to run it."),
    max_suite_usd: float | None = typer.Option(None, help="Optional suite budget metadata to record with the planned run."),
    max_suite_seconds: float | None = typer.Option(None, help="Optional suite time-budget metadata to record with the planned run."),
    max_suite_tasks: int | None = typer.Option(None, help="Optional suite task-budget metadata to record with the planned run."),
    max_suite_failures: int | None = typer.Option(None, help="Optional suite failure-budget metadata to record with the planned run."),
) -> None:
    """Dry-run or execute a tau2-style workflow when a concrete runner module is available."""
    result = run_tau2_task(
        task_id=task_id,
        model=model,
        output_dir=output_dir,
        runner_module=runner_module,
        dry_run=dry_run,
        execute=not dry_run,
        suite_budget={
            "max_suite_estimated_usd": max_suite_usd,
            "max_suite_wall_clock_seconds": max_suite_seconds,
            "max_suite_tasks": max_suite_tasks,
            "max_suite_failures": max_suite_failures,
        },
    )
    console.print_json(json.dumps(result))


@app.command("report")
def report(
    tasks: str = typer.Option("data/tasks/public_efficiency_subset.jsonl", help="Normalized task JSONL path."),
    runs: str = typer.Option(..., help="Run telemetry JSONL path."),
    output: str = typer.Option(..., help="Markdown report output path."),
    group_by: str = typer.Option("category", help="Comma-separated grouping dimensions."),
    manifest: str | None = typer.Option(None, help="Optional run manifest JSON path for tool metadata."),
) -> None:
    """Generate a Markdown efficiency report grouped by selected dimensions."""
    task_rows = [BenchmarkTask.model_validate(row) for row in read_jsonl(tasks)]
    run_rows = [RunTelemetry.model_validate(row) for row in read_jsonl(runs)]
    task_lookup = {task.task_id: task.model_dump() for task in task_rows}
    dimensions = [part.strip() for part in group_by.split(",") if part.strip()]
    if dimensions == ["category"] and manifest is None:
        summary = summarize_by_category(task_lookup, run_rows)
    else:
        manifests = _manifest_lookup(manifest, run_rows)
        summary = summarize_by_dimensions(task_lookup, run_rows, dimensions, manifests=manifests)
    write_markdown_report(output, summary)
    console.print(f"[green]Wrote report[/green] to {output}")


@app.command("audit-tasks")
def audit_tasks(
    tasks: str = typer.Argument(..., help="Normalized task JSONL path."),
    output: str | None = typer.Option(None, help="Optional Markdown output path."),
    min_instruction_chars: int = typer.Option(20, help="Warn on instructions shorter than this many characters."),
) -> None:
    """Audit a normalized task JSONL file for coverage and weak evaluator signals."""
    task_rows = [BenchmarkTask.model_validate(row) for row in read_jsonl(tasks)]
    audit = audit_task_rows(task_rows, min_instruction_chars=min_instruction_chars)
    markdown = format_audit_markdown(audit)
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(markdown, encoding="utf-8")
        console.print(f"[green]Wrote task audit[/green] to {output}")
    else:
        console.print(markdown)


def _manifest_lookup(manifest: str | None, runs: list[RunTelemetry]) -> dict[str, dict]:
    if not manifest:
        return {}
    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    return {run.run_id: data for run in runs}


if __name__ == "__main__":
    app()
